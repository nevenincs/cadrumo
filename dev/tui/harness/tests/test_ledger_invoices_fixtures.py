"""Invoice and record capture frames reach their declared state on the production screens."""

from __future__ import annotations

import pytest
from textual.widgets import Static

from cadrumo.entrypoints.tui.ledger.invoices_import import LedgerInvoiceImportScreen
from cadrumo.entrypoints.tui.ledger.invoices_wizard import LedgerInvoiceWizardScreen
from cadrumo.entrypoints.tui.ledger.models import LedgerFlowState
from dev.tui.harness.ledger_invoices_fixtures import (
    InvoicesFixtureState,
    build_invoices_fixture,
    invoices_fixture_interfaces,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FLOW_STATES = {
    InvoicesFixtureState.IMPORT_FORM: LedgerFlowState.EDITING,
    InvoicesFixtureState.IMPORT_REVIEW: LedgerFlowState.CONFIRMING,
    InvoicesFixtureState.IMPORT_OUTCOME: LedgerFlowState.SUCCEEDED,
    InvoicesFixtureState.WIZARD_FIRST_STEP: LedgerFlowState.EDITING,
    InvoicesFixtureState.WIZARD_REVIEW: LedgerFlowState.CONFIRMING,
    InvoicesFixtureState.WIZARD_REFUSED: LedgerFlowState.FAILED,
}
_STAGED = {
    InvoicesFixtureState.INVOICE_STAGED: "#ledger-invoice-staged",
    InvoicesFixtureState.TRANSACTION_STAGED: "#ledger-transaction-staged",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("state", list(InvoicesFixtureState))
async def test_invoice_frames_reach_their_declared_state(state: InvoicesFixtureState) -> None:
    """A frame that rendered the wrong screen or stopped short of its state would review the wrong thing."""
    app = build_invoices_fixture(state)
    async with app.run_test(size=(100, 30)) as pilot:
        await app.settle()
        await pilot.pause()
        top = type(app.screen)
        assert f"{top.__module__}.{top.__qualname__}" in invoices_fixture_interfaces(state)
        captured = app.captured
        if state in _FLOW_STATES:
            assert isinstance(captured, LedgerInvoiceImportScreen | LedgerInvoiceWizardScreen)
            assert captured.flow_state is _FLOW_STATES[state]
        if state in _STAGED:
            assert str(captured.query_one(_STAGED[state], Static).render())
        assert not str(captured.query_one("#ledger-refusal", Static).render()) or state is (
            InvoicesFixtureState.WIZARD_REFUSED
        )
