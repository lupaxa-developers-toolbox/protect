"""Project and user configuration."""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from lupaxa.protect.constants import (
    ALLOWED_CONFIG_KEYS,
    CONFIG_FILENAMES,
    DEFAULT_EXT,
    USER_CONFIG_PATH,
)


@dataclass
class Config:
    """Settings loaded from a config file, before CLI flags are applied."""

    ext: str = DEFAULT_EXT
    recursive: bool = False
    include_hidden: bool = False
    force: bool = False
    remove_backups: bool = False
    yes: bool = False
    update: bool = False
    dir: str = "."
    ignore: list[str] = field(default_factory=list)
    sets: dict[str, list[str]] = field(default_factory=dict)


def ensure_ext(ext: str) -> str:
    """Return ``ext`` with a leading dot, or the default when it is blank."""
    cleaned = ext.strip()
    if not cleaned:
        return DEFAULT_EXT
    return cleaned if cleaned.startswith(".") else f".{cleaned}"


def walk_up_to_home(start: Path) -> Iterator[Path]:
    """Yield ``start`` and its parents, stopping at the home directory."""
    home = Path.home().resolve()
    current = start.resolve()
    while True:
        yield current
        if current == home or current.parent == current:
            break
        current = current.parent


def find_config_file(start_dir: Path) -> Path | None:
    """Find ``.protect.config`` above ``start_dir``, then the user file."""
    for parent in walk_up_to_home(start_dir):
        for name in CONFIG_FILENAMES:
            candidate = parent / name
            if candidate.is_file():
                return candidate
    if USER_CONFIG_PATH.is_file():
        return USER_CONFIG_PATH
    return None


def load_json_or_jsonc(path: Path) -> dict[str, object]:
    """Load JSON or JSON-with-comments."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Failed to read '{path}': {exc}") from exc
    text = re.sub(r"(?m)^\s*//.*$", "", text)
    text = re.sub(
        r'(?m)(?P<code>[^"\\]|\\.|"(?:\\.|[^"\\])*")\s*//.*$',
        r"\g<code>",
        text,
    )
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON/JSONC in '{path}': {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"Config '{path}' must be a JSON object.")
    return loaded


def load_config_file(path: Path) -> Config:
    """Load a config file. A parse failure returns defaults and warns."""
    try:
        data = load_json_or_jsonc(path)
    except ValueError as exc:
        print(f"WARNING: failed to load config '{path}': {exc}", file=sys.stderr)
        return Config()

    cfg = Config()
    ext = data.get("ext", cfg.ext)
    cfg.ext = ensure_ext(str(ext))
    cfg.recursive = bool(data.get("recursive", cfg.recursive))
    cfg.include_hidden = bool(data.get("include_hidden", cfg.include_hidden))
    cfg.force = bool(data.get("force", cfg.force))
    cfg.remove_backups = bool(data.get("remove_backups", cfg.remove_backups))
    cfg.yes = bool(data.get("yes", cfg.yes))
    cfg.update = bool(data.get("update", cfg.update))
    cfg.dir = str(data.get("dir", cfg.dir))

    ignore_val = data.get("ignore", [])
    if isinstance(ignore_val, list):
        cfg.ignore = [str(item) for item in ignore_val]
    elif isinstance(ignore_val, str):
        cfg.ignore = [ignore_val]

    sets_val = data.get("sets", {})
    if isinstance(sets_val, dict):
        normalised: dict[str, list[str]] = {}
        for key, value in sets_val.items():
            if isinstance(value, list):
                normalised[str(key)] = [str(item) for item in value]
            elif isinstance(value, str):
                normalised[str(key)] = [value]
        cfg.sets = normalised
    return cfg


def validate_config_dict(data: dict[str, object]) -> tuple[list[str], list[str]]:
    """Return ``(errors, warnings)`` for a raw config object."""
    errors: list[str] = []
    warnings: list[str] = []
    unknown = set(data.keys()) - ALLOWED_CONFIG_KEYS
    if unknown:
        warnings.append(f"Unknown keys in config: {sorted(unknown)}")

    ext = data.get("ext", DEFAULT_EXT)
    if not isinstance(ext, str):
        errors.append("`ext` must be a string.")
    else:
        if not ext.startswith("."):
            errors.append("`ext` must start with a '.' (e.g., '.protect').")
        if any(char in ext for char in ("/", "\\")):
            errors.append("`ext` must not contain path separators ('/' or '\\').")
        if ext.strip() in (".", ""):
            errors.append("`ext` cannot be just '.' or empty.")

    for key in ("recursive", "include_hidden", "force", "remove_backups", "yes", "update"):
        if key in data and not isinstance(data[key], bool):
            errors.append(f"`{key}` must be a boolean.")

    if "dir" in data and not isinstance(data["dir"], str):
        errors.append("`dir` must be a string.")

    if "ignore" in data and not _is_str_or_str_list(data["ignore"]):
        errors.append("`ignore` must be a string or a list of strings.")

    if "sets" in data:
        sets_val = data["sets"]
        if not isinstance(sets_val, dict):
            errors.append("`sets` must be an object mapping set-name -> list of strings.")
        else:
            errors.extend(_validate_sets(sets_val))
    return errors, warnings


def _is_str_or_str_list(value: object) -> bool:
    if isinstance(value, str):
        return True
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_sets(sets_val: dict[object, object]) -> list[str]:
    errors: list[str] = []
    for key, value in sets_val.items():
        if not isinstance(key, str):
            errors.append("All set names (keys) in `sets` must be strings.")
            break
        if not _is_str_or_str_list(value):
            errors.append(f"`sets['{key}']` must be a string or a list of strings.")
    return errors
