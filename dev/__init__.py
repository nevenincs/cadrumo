"""AEAT developer tooling — quality gates, audits, and docs build (not shipped in the wheel)."""

from __future__ import annotations

import os
import sys

# Windows starts a Python process with its streams bound to the ANSI codepage
# (cp1252 on a stock installation), so ONE box-drawing character or accented
# identifier - in a tool's output, or in a command line a harness module echoes
# before running it - raises UnicodeEncodeError and takes the recipe down with
# it. The failure belongs to Python, not the shell: it reproduces identically
# under `cmd` and under `pwsh`, so no choice of `set windows-shell` avoids it
# and the fix has to live here.
#
# Both halves are load bearing. Reconfiguring this process's own streams covers
# everything a `python -m dev.*` entry point prints; exporting PYTHONIOENCODING
# covers every Python child it spawns, which is most of the toolchain and is why
# this belongs in the package root rather than beside any one `subprocess.run`.
# An explicit value from the operator or a caller wins, so a deliberate override
# still works.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8")
