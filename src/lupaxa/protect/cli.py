"""Command-line interface for lupaxa.protect."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lupaxa.protect import __version__
from lupaxa.protect.config import (
    Config,
    ensure_ext,
    find_config_file,
    load_config_file,
    load_json_or_jsonc,
    validate_config_dict,
)
from lupaxa.protect.constants import BUILTIN_IGNORES
from lupaxa.protect.ignore import effective_ignores, find_ignore_file, load_ignore_file
from lupaxa.protect.ops import clean, collect_backups, collect_sources, protect, revert, status


def build_parser() -> argparse.ArgumentParser:
    """Return the ``protect`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="protect",
        description="Create sidecar backups for files and revert or clean them later.",
    )
    action = parser.add_mutually_exclusive_group(required=False)
    action.add_argument("-p", "--protect", action="store_true", help="Create or refresh backups.")
    action.add_argument("-v", "--revert", action="store_true", help="Restore files from backups.")
    action.add_argument("-c", "--clean", action="store_true", help="Delete backup files.")
    action.add_argument(
        "-s",
        "--status",
        action="store_true",
        help="Report sidecar state without changing files.",
    )
    parser.add_argument(
        "-R",
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enter subdirectories. --no-recursive turns a config true off.",
    )
    parser.add_argument("-e", "--ext", default=None, help="Backup extension (default: .protect).")
    parser.add_argument("-d", "--dir", default=None, help="Base directory when no paths are given.")
    parser.add_argument(
        "--include-hidden",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include dotfiles. --no-include-hidden turns a config true off.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show actions without changing files.",
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Print only warnings and errors. This is the default.",
    )
    output.add_argument("--verbose", action="store_true", help="Print each action.")
    parser.add_argument(
        "--force",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Overwrite an existing sidecar. --no-force turns a config true off.",
    )
    parser.add_argument(
        "--update",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Refresh a sidecar only when the original is newer. --no-update turns this off.",
    )
    parser.add_argument(
        "--remove-backups",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "After revert, delete the sidecar that was restored. "
            "--no-remove-backups turns this off."
        ),
    )
    parser.add_argument(
        "-y",
        "--yes",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Skip confirmations. --no-yes turns a config true off.",
    )
    parser.add_argument("--config", default=None, help="Path to a .protect.config file.")
    parser.add_argument("--no-config", action="store_true", help="Do not load a config file.")
    parser.add_argument("--ignore", action="append", default=[], help="Add an ignore pattern.")
    parser.add_argument("--ignore-file", action="append", default=[], help="Read ignore patterns.")
    parser.add_argument(
        "--no-ignore",
        action="store_true",
        help="Do not auto-load .protectignore. Built-in ignores still apply.",
    )
    parser.add_argument(
        "--set",
        dest="sets",
        action="append",
        default=[],
        help="Named target set from the config. Repeat to combine sets.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="With status, exit 1 when a sidecar is missing or the original is newer.",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Print resolved settings as JSON.",
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate config and ignore files, then exit.",
    )
    parser.add_argument("--version", action="store_true", help="Show version information and exit.")
    parser.add_argument("paths", nargs="*", help="Files, directories, or globs.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"protect {__version__}")
        return 0
    if args.ext is not None:
        args.ext = ensure_ext(args.ext)
        if any(char in args.ext for char in ("/", "\\")) or args.ext.strip() in (".", ""):
            parser.error("Backup extension must start with '.' and contain no path separators.")
    if args.check and (args.protect or args.revert or args.clean):
        parser.error("--check is only valid with -s/--status")
    if args.check:
        args.status = True
    if not (
        args.print_config
        or args.validate_config
        or args.protect
        or args.revert
        or args.clean
        or args.status
    ):
        parser.error("one of -p/--protect, -v/--revert, -c/--clean, or -s/--status is required")
    return orchestrate(args)


def orchestrate(args: argparse.Namespace) -> int:
    """Resolve config and run the selected action."""
    if args.dir is None:
        discover_from = Path.cwd().resolve()
    else:
        discover_from = Path(args.dir).expanduser().resolve()
    cfg, cfg_path, cfg_raw, load_error, missing = resolve_config(discover_from, args)
    base_dir = discover_from if args.dir is not None else Path(cfg.dir).expanduser().resolve()
    ignore_paths, patterns_by_file, ignores = resolve_ignores(discover_from, args, cfg)
    runtime = runtime_settings(args, cfg, base_dir)

    if args.print_config:
        print(
            json.dumps(
                config_report(
                    base_dir, cfg, cfg_path, ignore_paths, patterns_by_file, ignores, runtime, args
                ),
                indent=2,
            )
        )
        return 0
    if args.validate_config:
        report, valid = validation_report(
            base_dir, cfg_path, cfg_raw, load_error, missing, ignore_paths
        )
        print(json.dumps(report, indent=2))
        return 0 if valid else 2
    return run_action(base_dir, args, cfg, runtime, ignores)


def resolve_config(
    start: Path, args: argparse.Namespace
) -> tuple[Config, Path | None, dict[str, object] | None, str | None, bool]:
    """Load config from ``--config``, discovery, or defaults."""
    cfg = Config()
    cfg_path: Path | None = None
    raw: dict[str, object] | None = None
    load_error: str | None = None
    missing = False
    if args.no_config:
        return cfg, cfg_path, raw, load_error, missing
    if args.config:
        candidate = Path(args.config).expanduser().resolve()
        if not candidate.is_file():
            print(f"WARNING: --config file not found: '{candidate}'", file=sys.stderr)
            return cfg, None, None, None, True
        cfg_path = candidate
    else:
        cfg_path = find_config_file(start)
    if cfg_path is None:
        return cfg, None, None, None, False
    try:
        raw = load_json_or_jsonc(cfg_path)
    except ValueError as exc:
        load_error = str(exc)
    cfg = load_config_file(cfg_path)
    return cfg, cfg_path, raw, load_error, missing


def resolve_ignores(
    start: Path, args: argparse.Namespace, cfg: Config
) -> tuple[list[Path], dict[str, list[str]], list[str]]:
    """Merge built-in, config, file, and CLI ignore patterns."""
    paths: list[Path] = []
    by_file: dict[str, list[str]] = {}
    extra = list(args.ignore or [])
    file_args = args.ignore_file or []
    if file_args:
        for item in file_args:
            path = Path(item).expanduser().resolve()
            patterns = load_ignore_file(path)
            paths.append(path)
            by_file[str(path)] = patterns
            extra.extend(patterns)
    elif not args.no_ignore:
        found = find_ignore_file(start)
        if found is not None:
            path = found.resolve()
            patterns = load_ignore_file(path)
            paths.append(path)
            by_file[str(path)] = patterns
            extra.extend(patterns)
    return paths, by_file, effective_ignores(cfg.ignore, extra)


def _chosen(cli: bool | None, configured: bool) -> bool:
    """Use the CLI value when the flag was passed, otherwise the config value."""
    return configured if cli is None else cli


def runtime_settings(args: argparse.Namespace, cfg: Config, base_dir: Path) -> dict[str, object]:
    """A passed flag wins. ``--no-*`` turns a config ``true`` off."""
    return {
        "ext": ensure_ext(args.ext if args.ext is not None else cfg.ext),
        "recursive": _chosen(args.recursive, cfg.recursive),
        "include_hidden": _chosen(args.include_hidden, cfg.include_hidden),
        "force": _chosen(args.force, cfg.force),
        "update": _chosen(args.update, cfg.update),
        "remove_backups": _chosen(args.remove_backups, cfg.remove_backups),
        "yes": _chosen(args.yes, cfg.yes),
        "dir": str(base_dir),
        "sets_available": sorted(cfg.sets),
    }


def config_report(
    base_dir: Path,
    cfg: Config,
    cfg_path: Path | None,
    ignore_paths: list[Path],
    patterns_by_file: dict[str, list[str]],
    ignores: list[str],
    runtime: dict[str, object],
    args: argparse.Namespace,
) -> dict[str, object]:
    """JSON body for ``--print-config``."""
    return {
        "base_dir": str(base_dir),
        "config": {
            "auto_discovery_enabled": not args.no_config,
            "path": str(cfg_path.resolve()) if cfg_path else None,
            "loaded": {
                "ext": cfg.ext,
                "recursive": cfg.recursive,
                "include_hidden": cfg.include_hidden,
                "force": cfg.force,
                "remove_backups": cfg.remove_backups,
                "yes": cfg.yes,
                "update": cfg.update,
                "dir": cfg.dir,
                "ignore": cfg.ignore,
                "sets": cfg.sets,
            },
        },
        "ignore": {
            "auto_discovery_enabled": not args.no_ignore,
            "paths_used": [str(path) for path in ignore_paths],
            "patterns_from_files": patterns_by_file,
            "builtin": BUILTIN_IGNORES,
            "from_config": cfg.ignore,
            "from_cli": args.ignore or [],
            "effective": ignores,
        },
        "effective_runtime_settings": runtime,
    }


def validation_report(
    base_dir: Path,
    cfg_path: Path | None,
    raw: dict[str, object] | None,
    load_error: str | None,
    missing: bool,
    ignore_paths: list[Path],
) -> tuple[dict[str, object], bool]:
    """JSON body for ``--validate-config``."""
    errors: list[str] = []
    warnings: list[str] = []
    if missing:
        errors.append("Explicit --config path not found.")
    elif cfg_path is None:
        warnings.append("No config file found (using built-in defaults).")
    elif load_error:
        errors.append(f"Failed to load config: {load_error}")
    elif raw is not None:
        found_errors, found_warnings = validate_config_dict(raw)
        errors.extend(found_errors)
        warnings.extend(found_warnings)
    ignore_errors: dict[str, list[str]] = {}
    for path in ignore_paths:
        try:
            path.read_text(encoding="utf-8")
        except OSError as exc:
            ignore_errors[str(path)] = [f"Could not read: {exc}"]
    valid = not errors and not ignore_errors
    return {
        "status": "valid" if valid else "invalid",
        "base_dir": str(base_dir),
        "config_path": str(cfg_path.resolve()) if cfg_path else None,
        "config_errors": errors,
        "config_warnings": warnings,
        "ignore_paths": [str(path) for path in ignore_paths],
        "ignore_errors": ignore_errors,
    }, valid


def run_action(
    base_dir: Path,
    args: argparse.Namespace,
    cfg: Config,
    runtime: dict[str, object],
    ignores: list[str],
) -> int:
    """Protect, revert, clean, or report the selected targets."""
    if not base_dir.is_dir():
        print(f"ERROR: '{base_dir}' is not a directory", file=sys.stderr)
        return 2
    targets = expand_sets(cfg.sets, args.sets or [])
    targets.extend(args.paths or [])
    ext = str(runtime["ext"])
    recursive = bool(runtime["recursive"])
    include_hidden = bool(runtime["include_hidden"])
    quiet = not args.verbose
    try:
        if args.protect or args.status:
            files = collect_sources(
                base=base_dir,
                paths=targets,
                recursive=recursive,
                include_hidden=include_hidden,
                ext=ext,
                ignores=ignores,
            )
            if args.status:
                return status(files=files, ext=ext, check=args.check)
            return protect(
                files=files,
                ext=ext,
                dry=args.dry_run,
                quiet=quiet,
                force=bool(runtime["force"]),
                update=bool(runtime["update"]),
            )
        pairs = collect_backups(
            base=base_dir,
            paths=targets,
            recursive=recursive,
            include_hidden=include_hidden,
            ext=ext,
            ignores=ignores,
        )
        if args.revert:
            return revert(
                pairs=pairs,
                dry=args.dry_run,
                quiet=quiet,
                remove_backups=bool(runtime["remove_backups"]),
                yes=bool(runtime["yes"]),
            )
        if args.clean:
            return clean(pairs=pairs, dry=args.dry_run, quiet=quiet, yes=bool(runtime["yes"]))
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        return 2
    return 2


def expand_sets(sets: dict[str, list[str]], selected: list[str]) -> list[str]:
    """Flatten named sets. Unknown names are skipped."""
    targets: list[str] = []
    for name in selected:
        if name not in sets:
            print(f"WARNING: unknown set '{name}' (ignored).", file=sys.stderr)
            continue
        targets.extend(sets[name])
    return targets
