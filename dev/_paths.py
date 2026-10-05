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

import os
import sys
import tempfile
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
UTF_8: Final[str] = "utf-8"

# Standalone dev commands may not run from an editable installation. Make the
# checkout's source package importable before dev tooling reaches its storage
# path authority.
_SOURCE_ROOT = REPO_ROOT / "src"
if _SOURCE_ROOT.is_dir() and str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from cadrumo.core.storage_environment import prepare_temporary_directory, tool_storage_environment  # noqa: E402

# Every standalone dev entrypoint that imports this module gets the same
# overrideable build/cache paths and a controlled stdlib temp root. Pytest's
# run bootstrap narrows TEMP to per-run scratch before tests execute; nested
# processes keep that binding instead of widening it here.
os.environ.update(tool_storage_environment())
sys.pycache_prefix = os.environ["PYTHONPYCACHEPREFIX"]
if "CADRUMO_TEST_RUN_SCRATCH" not in os.environ:
    _TEMP_ROOT = prepare_temporary_directory()
    os.environ.update({"TEMP": str(_TEMP_ROOT), "TMP": str(_TEMP_ROOT), "TMPDIR": str(_TEMP_ROOT)})
    tempfile.tempdir = str(_TEMP_ROOT)

AUTHORITY_ROOT_ENV: Final[str] = "CADRUMO_AUTHORITY_ROOT"
"""Environment variable naming the directory holding the published authority."""

DEFAULT_AUTHORITY_ROOT: Final[Path] = REPO_ROOT / ".authority"
"""Where a checkout keeps its published authority, outside the packaged tree.

The repo-root ``conftest.py`` spells the same path out in pure stdlib, because
this module is private to ``dev`` and nothing the test suite already imports
reaches it. The two definitions cross-reference each other so a future edit to
one is not made deaf to the other."""

# The published authority is generated output that no longer lives inside the
# packaged tree, so every `python -m dev.*` entry point and every recipe that
# reaches one would otherwise need the variable exported by hand. Seeding it
# here, at the shared path-constants entry point, makes a checkout resolve its
# own authority with no operator setup. An explicit value always wins: a blank
# one is treated as unset, matching Settings' `env_ignore_empty` behaviour, so a
# variable exported empty by a shell profile does not resolve the authority to
# the process's current working directory.
if not os.environ.get(AUTHORITY_ROOT_ENV, "").strip():
    os.environ[AUTHORITY_ROOT_ENV] = str(DEFAULT_AUTHORITY_ROOT)

# Windows starts a Python process with its streams bound to the ANSI codepage
# (cp1252 on a stock installation). Configure the developer process at the
# shared path-constants entry point, after the package initializer has loaded,
# so tool output can carry the repository's Unicode identifiers safely.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding=UTF_8)

__all__ = ["AUTHORITY_ROOT_ENV", "DEFAULT_AUTHORITY_ROOT", "REPO_ROOT", "UTF_8"]
