"""Packaging-suite collection hook: reclaim abandoned build scratch under ``var/``.

Runs at collection because that is the only moment guaranteed to execute
regardless of how a previous run ended. The release-cohort integration proof
removes its multi-hundred-megabyte source clone in a ``finally`` block, which
covers a test that finishes and covers nothing about a killed worker or a
killed session -- and this suite's own timeout ceiling documents that a worker
parked in ``subprocess.wait()`` exits uncleanly rather than unwinding. A sweep
reachable only from a clean exit runs only in the case where it was not needed.

Scoped to this package rather than to the repository root because these are the
tests that mint the scratch: the sweep costs one listing of ``var/`` and a stat
per candidate, which is worth paying where the leak is produced and not worth
putting on the critical path of every unrelated session.
"""

from __future__ import annotations

import contextlib

from .._paths import REPO_ROOT
from .build_scratch_reclaim import sweep_var_scratch

with contextlib.suppress(OSError):
    sweep_var_scratch(REPO_ROOT / "var")
