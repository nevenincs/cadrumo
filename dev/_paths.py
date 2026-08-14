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

from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
UTF_8: Final[str] = "utf-8"

__all__ = ["REPO_ROOT", "UTF_8"]
