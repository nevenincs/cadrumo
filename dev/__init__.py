"""AEAT developer tooling — quality gates, audits, and docs build (not shipped in the wheel)."""

from __future__ import annotations

import sys

# Windows starts a Python process with its streams bound to the ANSI codepage
# (cp1252 on a stock installation), so ONE box-drawing character or accented
# identifier - in a tool's output, or in a command line a harness module echoes
# before running it - raises UnicodeEncodeError and takes the recipe down with
# it. The failure belongs to Python, not the shell: it reproduces identically
# under `cmd` and under `pwsh`, so no choice of `set windows-shell` avoids it
# and the fix has to live here.
#
# Reconfigure only this process. Exporting an encoding here would leak harness
# policy into every child and make recipe-driven subprocesses behave differently
# from direct invocations. Child readers must choose their own byte decoding.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8")
