"""The one canonical repo-root and text-encoding constants for `dev/` tooling.

`dev/` scripts run both as `python -m dev.<pkg>.<module>` and, for a small
number of entrypoints that predate the interpreter having `dev` on
`sys.path`, as bare scripts (`python dev/<pkg>/<module>.py`). A bare-script
invocation needs its own local `Path(__file__).resolve().parents[N]` to seed
`sys.path` before `dev` is importable at all — that bootstrap line is not
duplication, it is the precondition for reaching this module, and it stays
local. Every other `dev/` module reaches `dev` normally and repoints here.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
UTF_8: Final[str] = "utf-8"

# Windows starts a Python process with its streams bound to the ANSI codepage
# (cp1252 on a stock installation). Configure the developer process at the
# shared path-constants entry point, after the package initializer has loaded,
# so tool output can carry the repository's Unicode identifiers safely.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding=UTF_8)

__all__ = ["REPO_ROOT", "UTF_8"]
