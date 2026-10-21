"""Entry point of the desktop agent lane, run only by its recipe."""

from __future__ import annotations

from .lane import main

if __name__ == "__main__":
    raise SystemExit(main())
