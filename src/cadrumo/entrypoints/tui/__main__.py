"""Module execution for the dedicated TUI.

Delegates to the launcher's entry point and nothing else. The CLI is not
imported here, and must not be: the TUI is an outermost process entrypoint,
so a full-screen session starts through this module or through the
installed console script, never by a sibling entrypoint reaching across.

``--self-test`` runs one session headless to a clean exit, which is how an
installed artifact proves its full-screen surface starts without a terminal.
"""

from __future__ import annotations

import sys

from .launcher import main

SELF_TEST_FLAG = "--self-test"

if __name__ == "__main__":
    raise SystemExit(main(headless=SELF_TEST_FLAG in sys.argv[1:]))
