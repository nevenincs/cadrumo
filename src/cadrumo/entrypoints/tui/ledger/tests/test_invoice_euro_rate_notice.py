"""The TUI invoice form says at capture when a foreign invoice has no euro rate.

The door reports the fact from the invoice the writer recorded, and the entry
screen shows it after the success line. The rate provider is the production ECB
provider over an in-memory transport that publishes no series.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from textual.widgets import Button, Input, Static

from .....adapters.outbound.fx.ecb_provider import EcbReferenceRateProvider
from .....adapters.persistence.storage.tests.active_profile_isolated_backend_fixture import (
    DEFAULT_BUCKET_ID,
    active_profile_isolated_backend_fixture,
)
from .....application.exchange_rate_provider import bind_exchange_rate_provider_factory
from .....core.config import override_settings
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.iva.classification import InvoiceKind
from .....tests.ecb_stub import ecb_csv_fetch
from ....tui.components.host import ScreenHostApp
from ...ledger_doors import ledger_invoice_add_door
from ..controller import LedgerWorkspaceController
from ..invoice_entry import LedgerInvoiceEntryScreen
from ..models import LedgerFlowState, LedgerInvoiceAddResultV1, LedgerInvoiceEntryV1
from ..workspace_injection import LedgerWorkspaceInjection
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_isolated_backend = active_profile_isolated_backend_fixture()


def _entry(number: str, currency: str) -> LedgerInvoiceEntryV1:
    return LedgerInvoiceEntryV1(
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Proveedor Exterior SL",
        counterparty_nif="A58818501",
        country_code="ES",
        invoice_number=number,
        invoice_date=date(2026, 3, 16),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        currency=currency,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("currency", "pending"), [("USD", True), ("EUR", False)])
async def test_the_real_door_reports_a_foreign_invoice_recorded_without_a_rate(
    operation: PinnedAuthorityOperation, currency: str, pending: bool
) -> None:
    with bind_exchange_rate_provider_factory(lambda: EcbReferenceRateProvider(fetch=ecb_csv_fetch({}))):
        recorded = await ledger_invoice_add_door(DEFAULT_BUCKET_ID, operation)(_entry(f"FX-{currency}", currency))

    assert recorded.euro_value_pending is pending


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
