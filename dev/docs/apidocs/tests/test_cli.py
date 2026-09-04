"""Tests for the apidocs CLI's drift-reporting contract.

`dev.quality.module_test_reach` listed `dev/docs/apidocs/cli.py` as unreached.
Its sibling `manager.py` is covered by `test_manager.py`; what had nothing was
the wiring that turns a drift result into an exit code, which is the only part
a workflow or a contributor's shell actually reads.

NOTHING HERE INVOKES ``scaffold`` WITHOUT ``--check``. That path writes and
deletes RST files under ``docs/api/``, and the manager it uses is built from the
repository root rather than an injected one, so a test that ran it would rewrite
the real stub tree. The manager's writing behaviour is exercised in
`test_manager.py` against constructed roots, which is where an injectable seam
exists; here only the read-only verbs are driven.

Both exit-code cases assert the AGREEMENT between the printed report and the
status code rather than a fixed verdict. The live tree currently carries drift
(42 missing, 12 stale at the time of writing), and pinning that number would
make this file fail the moment somebody fixed it - which is precisely backwards
for a drift gate.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from ..cli import app

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.docs]


def _invoke(*arguments: str) -> object:
    return CliRunner().invoke(app, list(arguments))


def test_both_verbs_are_registered() -> None:
    """The verbs are reached by name from a shell, so the names are the contract."""
    result = _invoke("--help")

    assert result.exit_code == 0, result.output
    assert "scaffold" in result.output
    assert "audit" in result.output


def test_invoking_the_group_with_no_verb_shows_help_rather_than_scaffolding() -> None:
    """A bare invocation must not fall through to the writing path.

    ``no_args_is_help`` is what stands between a mistyped command and a
    rewritten stub tree, so it is asserted rather than assumed.
    """
    result = _invoke()

    assert result.exit_code != 0
    assert "scaffold" in result.output


def test_the_drift_check_exit_code_agrees_with_its_own_report() -> None:
    """A drift gate that reported drift and exited 0 would gate nothing.

    Written against what the run actually found so it holds in both states:
    a conformant tree must exit 0, and a tree with drift must not.
    """
    result = _invoke("scaffold", "--check")

    conformant = "No drift detected" in result.output
    assert (result.exit_code == 0) == conformant, result.output


def test_the_drift_check_names_what_drifted() -> None:
    """A count with no names sends the reader to diff the whole stub tree."""
    result = _invoke("scaffold", "--check")

    if result.exit_code == 0:
        pytest.skip("the stub tree is conformant, so there is nothing to name")
    assert "Drift detected:" in result.output
    assert any(heading in result.output for heading in ("Missing stubs:", "Orphan stubs:", "Stale stubs:"))


def test_the_audit_exit_code_agrees_with_the_drift_check() -> None:
    """Two verbs reading one tree must not disagree about whether it is healthy.

    ``audit`` prints a report and then re-runs the same conformance question,
    so a divergence here would mean one of them is reading something else.
    """
    audited = _invoke("audit")
    checked = _invoke("scaffold", "--check")

    assert (audited.exit_code == 0) == (checked.exit_code == 0), audited.output


def test_the_audit_prints_a_report_before_deciding() -> None:
    """An audit that only sets an exit code tells a reader nothing to act on."""
    result = _invoke("audit")

    assert result.output.strip()
