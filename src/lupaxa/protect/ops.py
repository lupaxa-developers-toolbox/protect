"""Sidecar backup, restore, and delete."""

from __future__ import annotations

import glob
import os
import shutil
import sys
import tempfile
from pathlib import Path

from lupaxa.protect.ignore import is_hidden, iter_files, should_ignore


def atomic_copy_overwrite(src: Path, dst: Path) -> None:
    """Replace ``dst`` with a copy of ``src`` via a temporary file."""
    parent = dst.parent
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".tmp_", dir=parent, delete=False) as handle:
            tmp_path = Path(handle.name)
        shutil.copy2(src, tmp_path)
        os.replace(tmp_path, dst)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def expand_user_glob(path_str: str) -> list[Path]:
    """Expand ``~`` and globs. A non-match is returned as a single path."""
    expanded = glob.glob(os.path.expanduser(path_str), recursive=True)
    if not expanded:
        return [Path(os.path.expanduser(path_str))]
    return [Path(item) for item in expanded]


def collect_sources(
    *,
    base: Path,
    paths: list[str],
    recursive: bool,
    include_hidden: bool,
    ext: str,
    ignores: list[str],
) -> list[Path]:
    """Return source files to back up, excluding existing sidecars."""
    if not paths:
        return [
            path
            for path in iter_files(
                base, recursive=recursive, ignores=ignores, include_hidden=include_hidden
            )
            if not path.name.endswith(ext)
        ]

    candidates: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        for path in expand_user_glob(raw):
            resolved = path.resolve()
            if resolved in seen or should_ignore(resolved, base, ignores):
                continue
            seen.add(resolved)
            if resolved.is_file():
                if (include_hidden or not is_hidden(resolved)) and not resolved.name.endswith(ext):
                    candidates.append(resolved)
            elif resolved.is_dir():
                for found in iter_files(
                    resolved,
                    recursive=recursive,
                    ignores=ignores,
                    include_hidden=include_hidden,
                ):
                    if not found.name.endswith(ext):
                        candidates.append(found)
            else:
                print(f"WARNING: path not found (skipped): '{resolved}'", file=sys.stderr)
    return candidates


def collect_backups(
    *,
    base: Path,
    paths: list[str],
    recursive: bool,
    include_hidden: bool,
    ext: str,
    ignores: list[str],
) -> list[tuple[Path, Path]]:
    """Return ``(sidecar, original)`` pairs."""
    pairs: list[tuple[Path, Path]] = []

    def add_backup(backup: Path) -> None:
        if should_ignore(backup, base, ignores):
            return
        try:
            if not backup.is_file():
                return
        except OSError:
            return
        hidden_parent = any(is_hidden(parent) for parent in backup.parents if parent != base)
        if not include_hidden and (is_hidden(backup) or hidden_parent):
            return
        original = backup.with_name(backup.name[: -len(ext)])
        pairs.append((backup, original))

    if not paths:
        for found in iter_files(
            base, recursive=recursive, ignores=ignores, include_hidden=include_hidden
        ):
            if found.name.endswith(ext):
                add_backup(found)
        return pairs

    seen: set[Path] = set()
    for raw in paths:
        for path in expand_user_glob(raw):
            resolved = path.resolve()
            if resolved in seen or should_ignore(resolved, base, ignores):
                continue
            seen.add(resolved)
            if resolved.is_file():
                if resolved.name.endswith(ext):
                    add_backup(resolved)
                else:
                    sidecar = resolved.with_name(resolved.name + ext)
                    if sidecar.exists():
                        add_backup(sidecar)
                    else:
                        print(f"WARNING: no backup found for '{resolved}'", file=sys.stderr)
            elif resolved.is_dir():
                for found in iter_files(
                    resolved,
                    recursive=recursive,
                    ignores=ignores,
                    include_hidden=include_hidden,
                ):
                    if found.name.endswith(ext):
                        add_backup(found)
            else:
                print(f"WARNING: path not found (skipped): '{resolved}'", file=sys.stderr)
    return pairs


def protect(
    *,
    files: list[Path],
    ext: str,
    dry: bool,
    quiet: bool,
    force: bool,
    update: bool = False,
) -> int:
    """Copy each source to a sidecar. Return 1 when any copy fails."""
    code = 0
    for source in files:
        if source.name.endswith(ext):
            continue
        sidecar = source.with_name(source.name + ext)
        try:
            if sidecar.exists() and not _should_replace(source, sidecar, force, update, quiet):
                continue
            _log(f"BACKUP: {source} -> {sidecar}", quiet)
            if not dry:
                shutil.copy2(source, sidecar)
        except PermissionError as exc:
            code = 1
            print(f"ERROR backing up '{source}': permission denied: {exc}", file=sys.stderr)
        except FileNotFoundError as exc:
            code = 1
            print(f"ERROR backing up '{source}': not found: {exc}", file=sys.stderr)
        except OSError as exc:
            code = 1
            print(f"ERROR backing up '{source}': {exc}", file=sys.stderr)
    return code


def _should_replace(source: Path, sidecar: Path, force: bool, update: bool, quiet: bool) -> bool:
    """Decide whether an existing sidecar should be copied over."""
    if force:
        return True
    try:
        source_newer = source.stat().st_mtime > sidecar.stat().st_mtime
    except OSError as exc:
        print(f"WARNING: stat failed on '{source}' or '{sidecar}': {exc}", file=sys.stderr)
        return True
    if not source_newer:
        _log(f"SKIP (existing or up-to-date backup): {source}", quiet)
        return False
    if update:
        return True
    print(
        f"WARNING: backup exists for '{source}' and the original is newer. "
        "Use --update to refresh it, or --force to overwrite.",
        file=sys.stderr,
    )
    return False


def status(*, files: list[Path], ext: str, check: bool = False) -> int:
    """Print the sidecar state of each source.

    Return 1 when a stat fails. With ``check``, also return 1 when a sidecar
    is missing or the original is newer.
    """
    if not files:
        print("No files to report.")
        return 0
    code = 0
    for source in files:
        sidecar = source.with_name(source.name + ext)
        try:
            if not sidecar.exists():
                state = "missing"
            elif source.stat().st_mtime > sidecar.stat().st_mtime:
                state = "stale"
            elif source.stat().st_mtime < sidecar.stat().st_mtime:
                state = "newer"
            else:
                state = "current"
        except OSError as exc:
            code = 1
            print(f"ERROR: could not stat '{source}': {exc}", file=sys.stderr)
            continue
        if check and state in ("missing", "stale"):
            code = 1
        print(f"{state} {source}")
    return code


def revert(
    *,
    pairs: list[tuple[Path, Path]],
    dry: bool,
    quiet: bool,
    remove_backups: bool,
    yes: bool,
) -> int:
    """Restore originals from sidecars. Return 2 when the user cancels."""
    if not pairs:
        _log("No backup files found to revert.", quiet)
        return 0
    if not dry and not confirm("REVERT files from backups", yes):
        print("Cancelled.", file=sys.stderr)
        return 2

    code = 0
    for sidecar, original in pairs:
        if not sidecar.exists():
            code = 1
            print(f"ERROR: backup missing '{sidecar}'", file=sys.stderr)
            continue
        _log(f"REVERT: {sidecar} -> {original}", quiet)
        if dry:
            continue
        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            atomic_copy_overwrite(sidecar, original)
            if remove_backups:
                sidecar.unlink(missing_ok=True)
        except PermissionError as exc:
            code = 1
            print(
                f"ERROR reverting '{original}' from '{sidecar}': permission denied: {exc}",
                file=sys.stderr,
            )
        except FileNotFoundError as exc:
            code = 1
            print(
                f"ERROR reverting '{original}' from '{sidecar}': not found: {exc}",
                file=sys.stderr,
            )
        except OSError as exc:
            code = 1
            print(f"ERROR reverting '{original}' from '{sidecar}': {exc}", file=sys.stderr)
    return code


def clean(*, pairs: list[tuple[Path, Path]], dry: bool, quiet: bool, yes: bool) -> int:
    """Delete sidecar files. Return 2 when the user cancels."""
    if not pairs:
        _log("No backup files found to delete.", quiet)
        return 0
    if not dry and not confirm("DELETE backup files", yes):
        print("Cancelled.", file=sys.stderr)
        return 2

    code = 0
    for sidecar, _original in pairs:
        _log(f"DELETE BACKUP: {sidecar}", quiet)
        if dry:
            continue
        try:
            sidecar.unlink(missing_ok=True)
        except PermissionError as exc:
            code = 1
            print(f"ERROR deleting backup '{sidecar}': permission denied: {exc}", file=sys.stderr)
        except OSError as exc:
            code = 1
            print(f"ERROR deleting backup '{sidecar}': {exc}", file=sys.stderr)
    return code


def confirm(action: str, yes: bool) -> bool:
    """Ask before a destructive action. ``yes`` skips the prompt."""
    if yes:
        return True
    try:
        answer = input(f"About to {action}. Proceed? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.", file=sys.stderr)
        return False
    return answer in ("y", "yes")


def _log(message: str, quiet: bool) -> None:
    if not quiet:
        print(message)
