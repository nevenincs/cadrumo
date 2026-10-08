"""The TUI invoice form shows a missing euro rate returned by its add door."""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.widgets import Button, Input, Static

from .....core.config import override_settings
from ...components.host import ScreenHostApp
from ..controller import LedgerWorkspaceController
from ..invoice_entry import LedgerInvoiceEntryScreen
from ..models import LedgerFlowState, LedgerInvoiceAddResultV1, LedgerInvoiceEntryV1
from ..workspace_injection import LedgerWorkspaceInjection
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _PendingDoor:
    async def __call__(self, entry: LedgerInvoiceEntryV1) -> LedgerInvoiceAddResultV1:
        return LedgerInvoiceAddResultV1(
            invoice_id="d" * 64,
            invoice_number=entry.invoice_number,
            base_total=Decimal("100.00"),
            iva_total=Decimal("21.00"),
            grand_total=Decimal("121.00"),
            currency=entry.currency,
            euro_value_pending=True,
        )


@pytest.mark.asyncio
async def test_the_entry_screen_shows_the_missing_rate_after_recording() -> None:
    screen = LedgerInvoiceEntryScreen(
        LedgerWorkspaceController(
            ledger_context(),
            ledger_projection(),
            LedgerWorkspaceInjection(review_action=ledger_review_action(), invoice_add_door=_PendingDoor()),
        )
    )
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 200)) as pilot:
            await pilot.pause()
            for name, value in {
                "counterparty_name": "Proveedor Exterior SL",
                "invoice_number": "FX-USD",
                "invoice_date": "2026-03-16",
                "taxable_base": "100.00",
                "iva_rate": "21",
                "currency": "USD",
            }.items():
                screen.query_one(f"#ledger-invoice-{name.replace('_', '-')}", Input).value = value
            screen.query_one("#ledger-invoice-review", Button).press()
            await pilot.pause()
            screen.query_one("#ledger-invoice-confirm", Button).press()
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
            assert screen.flow_state is LedgerFlowState.SUCCEEDED
            status = str(screen.query_one("#ledger-flow-status", Static).render())
    assert "No euro exchange rate for USD" in status
