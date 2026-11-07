"""Defaults shared by config discovery and the CLI."""

from __future__ import annotations

from pathlib import Path

DEFAULT_EXT = ".protect"

BUILTIN_IGNORES: list[str] = [
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".DS_Store",
    "node_modules",
    "dist",
    "build",
    "target",
    ".tox",
    ".coverage",
    "coverage*",
    "*.coverage",
    "*.pyc",
    "*.pyo",
    "*.lock",
    "*.log",
    "venv",
    ".venv",
    ".env",
    ".env.*",
]

CONFIG_FILENAMES = [".protect.config"]
USER_CONFIG_PATH = Path("~/.protect/protect.config").expanduser()

IGNORE_FILENAMES = [".protectignore"]
USER_IGNORE_PATH = Path("~/.protect/protectignore").expanduser()

ALLOWED_CONFIG_KEYS = {
    "ext",
    "recursive",
    "include_hidden",
    "force",
    "remove_backups",
    "yes",
    "update",
    "dir",
    "ignore",
    "sets",
}
