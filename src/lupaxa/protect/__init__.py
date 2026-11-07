"""lupaxa.protect — sidecar backups for local editing.

``protect`` copies a file to a sibling with a backup extension.
``revert`` restores the original. ``clean`` deletes the sidecar.
``status`` reports whether each sidecar is missing, stale, newer, or current.
"""

from __future__ import annotations

from lupaxa.protect.config import Config
from lupaxa.protect.ops import clean, protect, revert, status
from lupaxa.protect.version import __version__, get_version

__all__ = [
    "Config",
    "__version__",
    "clean",
    "get_version",
    "protect",
    "revert",
    "status",
]
