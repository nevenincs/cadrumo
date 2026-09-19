"""Packaging-suite session hook: reclaim abandoned build scratch under ``var/``.

Runs at session start because that is the only moment guaranteed to execute
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

It reclaims only what it can OBSERVE to be abandoned -- scratch whose name
carries a process identifier that no longer resolves. Nothing here acts on age
alone; ``var/`` holds trees an operator keeps on purpose, and reclaiming those
is a decision made through ``just clean-apply`` rather than as a side effect of
running a test.
"""

from __future__ import annotations

import contextlib

import pytest

from dev._paths import REPO_ROOT

from .build_scratch_reclaim import sweep_var_scratch

_RELEASE_PROOF_FILE = "dev/packaging/tests/test_release_cohort_integration.py"
_RELEASE_PROOF_NODEID = f"{_RELEASE_PROOF_FILE}::test_real_clean_source_build_is_complete_and_reproducible"


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Start the long release proof before shorter xdist loadfile groups.

    The two real cohort builds are the lane's critical path. The stable sort
    preserves every other test's order and changes only when this proof is
    selected, so an ordinary focused invocation keeps its natural ordering.
    """
    items.sort(key=lambda item: item.nodeid != _RELEASE_PROOF_NODEID)


def pytest_sessionstart(session: pytest.Session) -> None:
    """Reclaim scratch left by a run that was killed rather than torn down.

    Best-effort: a locked directory or a permission refusal is swallowed, since
    this is tidiness rather than correctness and nothing reads a scratch tree
    that survives. Safe under xdist, where every worker runs this too -- nothing
    it removes belongs to a live run, so two sweepers meeting on one directory
    cannot make any run observe a difference.
    """
    del session
    with contextlib.suppress(OSError):
        sweep_var_scratch(REPO_ROOT / "var")
