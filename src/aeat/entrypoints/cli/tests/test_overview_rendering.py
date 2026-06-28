"""Tests for the operator-facing ``overview status`` text rendering.

These pin two cluster-E findings: the next-step guidance must reflect
the actual workspace state rather than always saying "import a bank
file" (M19), and the draft / work-unit distinction must read
unmistakably so an operator with work units never thinks their work
was lost (the downgraded overview-wording polish item).
"""

from __future__ import annotations

import pytest

from ....application.overview import OverviewStatusReport
from .._overview_rendering import render_cli_overview_status_lines

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _report(
    *,
    transactions: int = 0,
    invoices: int = 0,
    drafts: int = 0,
    work_units: int = 0,
    discarded_work_units: int = 0,
    unsupported_work_create_modelos: tuple[str, ...] = (),
) -> OverviewStatusReport:
    return OverviewStatusReport(
        active_profile="bucket-uuid",
        active_profile_name="Test Persona",
        transactions=transactions,
        invoices=invoices,
        drafts=drafts,
        work_units=work_units,
        discarded_work_units=discarded_work_units,
        calculation_revisions=0,
        unreadable_rows=0,
        unsupported_work_create_modelos=unsupported_work_create_modelos,
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


def test_next_step_does_not_suggest_unsupported_m210_work_create() -> None:
    """IRNR profiles must not be steered toward unsupported Modelo 210 work units."""

    lines = render_cli_overview_status_lines(
        _report(transactions=6, unsupported_work_create_modelos=("210",)),
    )
    joined = "\n".join(lines)
    assert "ledger import" not in joined
    assert "ledger review" in joined
    assert "modelo work create" not in joined
    assert "modelo describe 210" in joined
    assert "G320" in joined


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


def test_work_units_line_separates_discarded_from_active() -> None:
    """When some work units are discarded the line must state the
    active / discarded split rather than a single inflated total - an
    operator reading '5 work units' must not count abandoned ones as
    live work."""

    lines = render_cli_overview_status_lines(_report(work_units=4, discarded_work_units=1))
    work_unit_line = next(line for line in lines if "discarded" in line.lower())
    # The active count is named distinctly from the discarded count.
    assert "4" in work_unit_line
    assert "1" in work_unit_line
    assert "discarded" in work_unit_line.lower()
    assert "active" in work_unit_line.lower()


def test_work_units_line_plain_when_none_discarded() -> None:
    """With no discarded units the line stays the plain present-count
    wording - the active/discarded split is scoped to the case that
    needs it."""

    lines = render_cli_overview_status_lines(_report(work_units=3))
    joined = "\n".join(lines)
    assert "discarded" not in joined.lower()
    work_unit_line = next(line for line in lines if line.lstrip().startswith("3 modelo"))
    assert "in progress" in work_unit_line.lower()


def test_work_units_line_shown_when_only_discarded_exist() -> None:
    """A workspace whose only work units are discarded is not reported
    as empty: the discarded count is surfaced so the operator sees the
    units still exist."""

    lines = render_cli_overview_status_lines(_report(work_units=0, discarded_work_units=2))
    work_unit_line = next(line for line in lines if "discarded" in line.lower())
    assert "0" in work_unit_line
    assert "2" in work_unit_line


def test_empty_invoice_register_line_does_not_read_as_lost_ledger_work() -> None:
    """C3: an empty invoice register must not read as lost ledger work.

    The `invoices` counter is the sales/purchase invoice register - a
    store separate from the bank ledger. An operator who has classified
    several ledger transactions must not see this line as "your work is
    gone": the wording names the invoice register explicitly and states
    it does not count ledger transactions.
    """

    lines = render_cli_overview_status_lines(_report(transactions=8, invoices=0))
    invoice_line = next(line for line in lines if "invoice" in line.lower())
    # The line names the separate store and rules out the misreading.
    assert "register" in invoice_line.lower()
    assert "ledger" in invoice_line.lower()


def test_invoice_register_line_with_records_names_the_register() -> None:
    """A populated invoice register line still names the separate store."""

    lines = render_cli_overview_status_lines(_report(invoices=3))
    invoice_line = next(line for line in lines if "invoice" in line.lower())
    assert "3" in invoice_line
    assert "register" in invoice_line.lower()
