"""Allow ``python -m lupaxa.protect`` to run the CLI."""

from __future__ import annotations

from lupaxa.protect.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
