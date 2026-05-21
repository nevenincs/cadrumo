"""Tests for the operator-facing ``overview status`` text rendering.

These pin two cluster-E findings: the next-step guidance must reflect
the actual workspace state rather than always saying "import a bank
file" (M19), and the draft / work-unit distinction must read
unmistakably so an operator with work units never thinks their work
was lost (the downgraded overview-wording polish item).
"""

from __future__ import annotations

import pytest

from aeat.application.overview import OverviewStatusReport
from aeat.entrypoints.cli._overview_rendering import render_cli_overview_status_lines

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _report(
    *,
    transactions: int = 0,
    invoices: int = 0,
    drafts: int = 0,
    work_units: int = 0,
) -> OverviewStatusReport:
    return OverviewStatusReport(
        active_profile="bucket-uuid",
        active_profile_name="Test Persona",
        transactions=transactions,
        invoices=invoices,
        drafts=drafts,
        work_units=work_units,
        calculation_revisions=0,
        unreadable_rows=0,
    )


def test_empty_workspace_next_step_is_import() -> None:
    """A cold workspace with no ledger data is correctly told to import
    a bank statement."""

    lines = render_cli_overview_status_lines(_report())
    joined = "\n".join(lines)
    assert "ledger import" in joined


def test_next_step_not_import_once_ledger_has_transactions() -> None:
    """M19: after manual ledger entries exist, the next-step guidance
    must not tell the operator to import a bank file - that step is
    done. It points at the real next action instead."""

    lines = render_cli_overview_status_lines(_report(transactions=6))
    joined = "\n".join(lines)
    assert "ledger import" not in joined
    # The operator is guided forward, not backward.
    assert "ledger review" in joined
    assert "modelo work create" in joined


def test_next_step_resumes_modelo_work_when_work_units_exist() -> None:
    """An operator with in-progress work units is pointed at resuming
    that work, never at re-importing a bank statement."""

    lines = render_cli_overview_status_lines(_report(transactions=6, work_units=2))
    joined = "\n".join(lines)
    assert "ledger import" not in joined
    assert "modelo work list" in joined


def test_drafts_empty_line_does_not_read_as_lost_work_when_work_units_exist() -> None:
    """Overview-wording polish: when work units exist, the zero-drafts
    line must explicitly state it does not affect the work units, so
    the operator cannot misread it as 'your work is gone'."""

    lines = render_cli_overview_status_lines(_report(work_units=3))
    joined = "\n".join(lines)
    # The zero-drafts line must reference the work units explicitly.
    assert "work unit" in joined.lower()
    # The work-units line itself reassures the operator the work is saved.
    work_unit_line = next(line for line in lines if line.lstrip().startswith("3 modelo"))
    assert "saved" in work_unit_line.lower()


def test_drafts_empty_line_unchanged_without_work_units() -> None:
    """With no work units, the plain zero-drafts line is shown - the
    reassurance wording is scoped to the misreadable case only."""

    lines = render_cli_overview_status_lines(_report())
    joined = "\n".join(lines)
    assert "No saved declaration drafts" in joined
