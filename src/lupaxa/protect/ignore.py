"""Ignore patterns and directory walks."""

from __future__ import annotations

import fnmatch
import os
import sys
from collections.abc import Iterator
from pathlib import Path

from lupaxa.protect.config import walk_up_to_home
from lupaxa.protect.constants import BUILTIN_IGNORES, IGNORE_FILENAMES, USER_IGNORE_PATH


def find_ignore_file(start_dir: Path) -> Path | None:
    """Find ``.protectignore`` above ``start_dir``, then the user file."""
    for parent in walk_up_to_home(start_dir):
        for name in IGNORE_FILENAMES:
            candidate = parent / name
            if candidate.is_file():
                return candidate
    if USER_IGNORE_PATH.is_file():
        return USER_IGNORE_PATH
    return None


def load_ignore_file(path: Path) -> list[str]:
    """Load ignore patterns, dropping blanks and ``#`` comments."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"WARNING: could not read ignore file '{path}': {exc}", file=sys.stderr)
        return []
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def compile_ignores(*groups: list[str]) -> list[str]:
    """Merge ignore patterns in order, keeping the first copy of each."""
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for pattern in group:
            cleaned = str(pattern).strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            merged.append(cleaned)
    return merged


def effective_ignores(config_ignores: list[str], extra_ignores: list[str]) -> list[str]:
    """Built-ins, then config patterns, then files and CLI patterns."""
    return compile_ignores(BUILTIN_IGNORES, config_ignores, extra_ignores)


def should_ignore(path: Path, base: Path, patterns: list[str]) -> bool:
    """Return true when ``path`` matches a pattern by name or relative path."""
    try:
        relative = path.relative_to(base)
    except ValueError:
        relative = path
    relative_text = relative.as_posix()
    for pattern in patterns:
        if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(relative_text, pattern):
            return True
    return False


def is_hidden(path: Path) -> bool:
    """Return true when any path segment is a dotfile name."""
    return any(part.startswith(".") for part in path.parts if part not in (".",))


def iter_files(
    base: Path,
    *,
    recursive: bool,
    ignores: list[str],
    include_hidden: bool,
) -> Iterator[Path]:
    """Yield files under ``base``, pruning ignored and unreadable directories."""
    if not recursive:
        yield from _iter_flat(base, ignores, include_hidden)
        return
    yield from _iter_recursive(base, ignores, include_hidden)


def _iter_flat(base: Path, ignores: list[str], include_hidden: bool) -> Iterator[Path]:
    try:
        entries = list(base.iterdir())
    except PermissionError as exc:
        print(f"ERROR: permission denied listing '{base}': {exc}", file=sys.stderr)
        return
    except OSError as exc:
        print(f"ERROR: cannot list '{base}': {exc}", file=sys.stderr)
        return
    for entry in entries:
        try:
            if should_ignore(entry, base, ignores):
                continue
            if entry.is_file() and (include_hidden or not is_hidden(entry)):
                yield entry
        except OSError:
            continue


def _iter_recursive(base: Path, ignores: list[str], include_hidden: bool) -> Iterator[Path]:
    for root, dirs, files in os.walk(base, topdown=True, followlinks=False):
        root_path = Path(root)
        pruned: list[str] = []
        for name in list(dirs):
            directory = root_path / name
            if should_ignore(directory, base, ignores):
                pruned.append(name)
                continue
            try:
                directory.stat()
            except (PermissionError, OSError):
                print(f"WARNING: skipping unreadable directory '{directory}'", file=sys.stderr)
                pruned.append(name)
        for name in pruned:
            dirs.remove(name)
        for name in files:
            path = root_path / name
            if should_ignore(path, base, ignores):
                continue
            try:
                if path.is_file() and (include_hidden or not is_hidden(path)):
                    yield path
            except OSError:
                continue
