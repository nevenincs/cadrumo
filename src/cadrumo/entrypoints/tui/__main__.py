"""Module execution for the dedicated TUI.

Delegates to the launcher's entry point and nothing else. The CLI is not
imported here, and must not be: the TUI is an outermost process entrypoint,
so a full-screen session starts through this module or through the
installed console script, never by a sibling entrypoint reaching across.
"""

from __future__ import annotations

from .launcher import main

if __name__ == "__main__":
    raise SystemExit(main())
