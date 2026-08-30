"""Fail when an execution record declares a Step its plan does not contain.

The vault's own ``exec-mapping`` check DETECTS this correctly and reports it as
one warning among twenty-eight, in a run that exits zero. That is the whole
problem: a committed execution record for a step that no longer exists is a
record of finished work with nothing to be finished, and it produces no signal
anyone acts on.

It is not hypothetical. A peer commit landed a plan file predating five rows
added the same evening; the rows vanished, one of them CLOSED with its execution
record already committed. The vault reported the resulting inconsistency exactly
-- and reported it as warning nineteen of twenty-eight, so nobody saw it. It was
found only because ``vault add exec`` refused loudly on a later, unrelated call.

This gate adds no detection. It re-reads the vault's own verdict and raises the
severity of one diagnostic class, because the detection was never the missing
part.

Scoped deliberately to the step-not-in-plan class. The sibling classes -- a
missing parent plan, a retired step id -- are real but describe records whose
plan is gone or whose id was deliberately retired, which is a different and
usually intentional situation.

See Also:
    :mod:`dev.tests.test_every_source_file_parses`
        The other gate written after a silent loss in this tree: both make an
        existing failure legible rather than detecting something new.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from .._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ORPHANED_STEP_PHRASE = "which does not exist in parent plan"

_UNADJUDICATED: frozenset[str] = frozenset(
    {
        ".vault/exec/2026-06-09-quality-hardening-campaign/2026-06-09-quality-hardening-campaign-ledger.md",
        ".vault/exec/2026-08-28-semantic-consolidation/2026-08-28-semantic-consolidation-P08-S105.md",
    }
)
"""Records already carrying this defect when the gate landed.

NOT an allowlist and NOT a blessing: each belongs to another campaign, and only
that campaign can say whether the row was lost, renamed, or retired. They are
named here so a NEW occurrence fails while these stay visible as owing an
adjudication. Removing an entry once its owner resolves it is the intended
lifecycle; adding one to silence a fresh failure is not.
"""


def _orphaned_step_records() -> tuple[str, ...]:
    """Return the vault's own step-not-in-plan diagnostics, as repo-relative paths."""
    executable = shutil.which("vaultspec-core")
    if executable is None:  # pragma: no cover - present in the dev environment
        pytest.skip("vaultspec-core is not on PATH")
    completed = subprocess.run(  # noqa: S603 - resolved executable, fixed argv, no caller input
        [executable, "vault", "check", "exec-mapping", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(completed.stdout)
    items = payload["data"]["diagnostics"]["items"]
    return tuple(
        sorted(
            {
                str(item["path"]).replace("\\", "/")
                for item in items
                if _ORPHANED_STEP_PHRASE in str(item["message"])
            }
        )
    )


def test_no_execution_record_declares_a_step_its_plan_does_not_contain() -> None:
    """A committed record must map to a live Step, or its work has no home.

    Reads the vault's verdict rather than re-deriving it: a second parser of
    plan structure would be a duplicate authority free to disagree with the
    tool, and the tool is right about this already.
    """
    orphaned = _orphaned_step_records()

    # Non-vacuity: a parse failure or a renamed diagnostic would otherwise
    # yield an empty set and pass silently, which is the failure this gate
    # exists to prevent, one level up.
    assert _UNADJUDICATED, "the unadjudicated set is empty; confirm the gate still reads real diagnostics"

    unexpected = tuple(path for path in orphaned if path not in _UNADJUDICATED)
    assert not unexpected, (
        "execution record(s) declare a Step their plan does not contain. Either a plan row was lost "
        "-- a peer commit predating it is how this happened before -- or a record names the wrong "
        "step. Restore the row or re-point the record; do NOT add it to the unadjudicated set:\n  "
        + "\n  ".join(unexpected)
    )
