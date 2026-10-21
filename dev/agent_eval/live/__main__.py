"""Entry point of the live agent lane, run only by its recipes."""

from __future__ import annotations

from .lane import main

if __name__ == "__main__":
    raise SystemExit(main())
