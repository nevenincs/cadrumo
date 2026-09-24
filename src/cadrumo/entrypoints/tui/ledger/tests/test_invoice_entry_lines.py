"""Multi-line invoice entry: typed lines reach the writer and read back in the detail view."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError
from textual.widgets import Button, Input, Select, Static

from .....adapters.persistence.storage.tests.active_profile_isolated_backend_fixture import (
    DEFAULT_BUCKET_ID,
    active_profile_isolated_backend_fixture,
)
from .....core.aggregation import IntracomOperationType
from .....core.config import override_settings
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.iva.classification import InvoiceKind
from ...components.host import ScreenHostApp
from ...ledger_doors import LedgerRecordDoors, ledger_invoice_add_door
from ..controller import LedgerWorkspaceController
from ..invoice_entry import LedgerInvoiceEntryScreen
from ..models import LedgerFlowState, LedgerInvoiceAddResultV1, LedgerInvoiceEntryV1, LedgerInvoiceLineEntryV1
from ..record_views import LedgerInvoiceDetailScreen
from ..workspace_injection import LedgerWorkspaceInjection
from .test_ledger_selection_journey import _WorkspaceHostApp
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_isolated_backend = active_profile_isolated_backend_fixture()

#: One invoice printed with two IVA rates: the case a single base and rate
#: cannot represent without attributing the whole cuota to one rate.
_LINES: tuple[Mapping[str, str], ...] = (
    {
        "description": "Printer paper",
        "quantity": "1",
        "unit_price": "10.00",
        "subtotal": "10.00",
        "iva_rate": "RATE_21",
        "iva_amount": "2.10",
    },
    {
        "description": "Reference book",
        "quantity": "1",
        "unit_price": "5.00",
        "subtotal": "5.00",
        "iva_rate": "RATE_10",
        "iva_amount": "0.50",
    },
)


def _typed(line: Mapping[str, str]) -> LedgerInvoiceLineEntryV1:
    return LedgerInvoiceLineEntryV1(
        description=line["description"],
        quantity=Decimal(line["quantity"]),
        unit_price=Decimal(line["unit_price"]),
        subtotal=Decimal(line["subtotal"]),
        iva_rate=line["iva_rate"],
        iva_amount=Decimal(line["iva_amount"]),
    )


def _entry(*lines: Mapping[str, str]) -> LedgerInvoiceEntryV1:
    return LedgerInvoiceEntryV1(
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_nif="A58818501",
        country_code="ES",
        invoice_number="LINES-001",
        invoice_date=date(2026, 3, 15),
        taxable_base=None,
        iva_rate=None,
        lines=tuple(_typed(line) for line in lines),
        operation_date=date(2026, 3, 14),
        currency="EUR",
        series="L",
    )


class _RecordingDoor:
    def __init__(self) -> None:
        self.entries: list[LedgerInvoiceEntryV1] = []

    async def __call__(self, entry: LedgerInvoiceEntryV1) -> LedgerInvoiceAddResultV1:
        self.entries.append(entry)
        base = sum((line.subtotal for line in entry.lines), Decimal(0))
        iva = sum((line.iva_amount for line in entry.lines), Decimal(0))
        return LedgerInvoiceAddResultV1(
            invoice_id="c" * 64,
            invoice_number=entry.invoice_number,
            base_total=base,
            iva_total=iva,
            grand_total=base + iva,
            currency=entry.currency,
        )


def _entry_screen(door: _RecordingDoor) -> LedgerInvoiceEntryScreen:
    return LedgerInvoiceEntryScreen(
        LedgerWorkspaceController(
            ledger_context(),
            ledger_projection(),
            LedgerWorkspaceInjection(review_action=ledger_review_action(), invoice_add_door=door),
        )
    )


def _fill(screen: LedgerInvoiceEntryScreen, **values: str) -> None:
    for name, value in values.items():
        screen.query_one(f"#ledger-invoice-{name.replace('_', '-')}", Input).value = value


def _type_line(screen: LedgerInvoiceEntryScreen, line: Mapping[str, str]) -> None:
    for name, value in line.items():
        screen.query_one(f"#ledger-invoice-line-{name.replace('_', '-')}", Input).value = value
    screen.query_one("#ledger-invoice-line-add", Button).press()


def _header(screen: LedgerInvoiceEntryScreen) -> None:
    _fill(
        screen,
        counterparty_name="Papeleria Sol SL",
        counterparty_nif="A58818501",
        invoice_number="LINES-001",
        invoice_date="2026-03-15",
    )


def _text(screen: LedgerInvoiceEntryScreen | LedgerInvoiceDetailScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


@pytest.mark.asyncio
async def test_mixed_rate_lines_and_invoice_facts_reach_the_writer_as_typed() -> None:
    door = _RecordingDoor()
    screen = _entry_screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 200)) as pilot:
            await pilot.pause()
            _header(screen)
            _fill(screen, operation_date="2026-03-14", recargo_amount="0.77", rectifies_invoice_number="LINES-000")
            screen.query_one("#ledger-invoice-operation-type", Select).value = IntracomOperationType.A.value
            for line in _LINES:
                _type_line(screen, line)
                await pilot.pause()
            listing = _text(screen, "#ledger-invoice-lines")
            assert "1. Printer paper" in listing
            assert "2. Reference book" in listing
            assert "RATE_10 0.50" in listing
            assert not screen.query_one("#ledger-invoice-line-remove", Button).disabled

            screen.query_one("#ledger-invoice-review", Button).press()
            await pilot.pause()
            assert screen.flow_state is LedgerFlowState.CONFIRMING, _text(screen, "#ledger-refusal")
            summary = _text(screen, "#ledger-invoice-summary")
            assert "Printer paper" in summary
            assert "Reference book" in summary
            assert "Modelo 349 key A · operation date 2026-03-14" in summary
            assert "Equivalence surcharge 0.77 EUR" in summary
            assert "Corrects invoice LINES-000" in summary
            assert screen.query_one("#ledger-invoice-line-add", Button).disabled
            assert not door.entries

            screen.query_one("#ledger-invoice-confirm", Button).press()
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
            assert screen.flow_state is LedgerFlowState.SUCCEEDED

    assert len(door.entries) == 1
    entry = door.entries[0]
    assert entry.lines == tuple(_typed(line) for line in _LINES)
    assert entry.taxable_base is None
    assert entry.iva_rate is None
    assert entry.operation_type is IntracomOperationType.A
    assert entry.operation_date == date(2026, 3, 14)
    assert entry.recargo_amount == Decimal("0.77")
    assert entry.rectifies_invoice_number == "LINES-000"


@pytest.mark.asyncio
async def test_a_line_that_cannot_be_read_is_not_added_and_names_every_field() -> None:
    door = _RecordingDoor()
    screen = _entry_screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 200)) as pilot:
            await pilot.pause()
            _type_line(screen, {**_LINES[0], "quantity": "one", "iva_amount": ""})
            await pilot.pause()
            refusal = _text(screen, "#ledger-refusal")
            assert "Quantity must be a number" in refusal
            assert "Line IVA amount is required." in refusal
            assert screen.lines == []
            assert "No lines entered" in _text(screen, "#ledger-invoice-lines")
            assert screen.query_one("#ledger-invoice-line-remove", Button).disabled
    assert not door.entries


@pytest.mark.asyncio
async def test_an_invoice_is_entered_by_lines_or_by_one_base_never_both_and_never_neither() -> None:
    door = _RecordingDoor()
    screen = _entry_screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 200)) as pilot:
            await pilot.pause()
            _header(screen)
            _type_line(screen, _LINES[0])
            await pilot.pause()
            _fill(screen, taxable_base="10.00", iva_rate="21")
            screen.query_one("#ledger-invoice-review", Button).press()
            await pilot.pause()
            assert screen.flow_state is LedgerFlowState.EDITING
            assert "either as lines or as one taxable base" in _text(screen, "#ledger-refusal")

            screen.query_one("#ledger-invoice-line-remove", Button).press()
            await pilot.pause()
            assert screen.lines == []
            _fill(screen, taxable_base="", iva_rate="")
            screen.query_one("#ledger-invoice-review", Button).press()
            await pilot.pause()
            assert screen.flow_state is LedgerFlowState.EDITING
            assert "Enter a taxable base, or add at least one invoice line." in _text(screen, "#ledger-refusal")
    assert not door.entries


@pytest.mark.asyncio
async def test_the_real_writer_keeps_every_line_and_the_detail_view_reads_them_back(
    operation: PinnedAuthorityOperation,
) -> None:
    """The per-rate breakdown survives the canonical writer and the canonical read."""
    recorded = await ledger_invoice_add_door(DEFAULT_BUCKET_ID, operation)(_entry(*_LINES))

    assert (recorded.base_total, recorded.iva_total, recorded.grand_total) == (
        Decimal("15.00"),
        Decimal("2.60"),
        Decimal("17.60"),
    )
    doors = LedgerRecordDoors(bucket_id=DEFAULT_BUCKET_ID, operation=operation)
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), record_doors=doors),
    )
    with override_settings(cadrumo_output_language="en"):
        detail = LedgerInvoiceDetailScreen(controller, doors, recorded.invoice_id)
        async with _WorkspaceHostApp(detail).run_test(size=(110, 55)) as pilot:
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
            rendered = _text(detail, "#ledger-record-detail")
            refusal = _text(detail, "#ledger-refusal")
    assert "1. Printer paper · 1 × 10.00 = 10.00 · IVA RATE_21 2.10" in rendered, refusal
    assert "2. Reference book · 1 × 5.00 = 5.00 · IVA RATE_10 0.50" in rendered
    assert "operation date 2026-03-14" in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("line", "refusal"),
    [
        pytest.param(
            {**_LINES[0], "subtotal": "11.00"},
            "subtotal must equal quantity",
            id="subtotal-disagrees-with-quantity-and-price",
        ),
        pytest.param({**_LINES[0], "iva_rate": "RATE_99"}, "IVA rate slot is not governed", id="ungoverned-rate-slot"),
    ],
)
async def test_the_real_writer_refuses_a_line_the_domain_line_refuses_and_records_nothing(
    line: Mapping[str, str],
    refusal: str,
    operation: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(ValidationError, match=refusal):
        await ledger_invoice_add_door(DEFAULT_BUCKET_ID, operation)(_entry(line, _LINES[1]))
    assert await LedgerRecordDoors(bucket_id=DEFAULT_BUCKET_ID, operation=operation).invoices() == ()
