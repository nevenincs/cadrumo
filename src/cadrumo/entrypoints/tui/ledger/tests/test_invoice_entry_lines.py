"""Multi-line invoice entry: typed lines reach the injected add door."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest
from textual.widgets import Button, Input, Select, Static

from .....core.aggregation import IntracomOperationType
from .....core.config import override_settings
from .....core.i18n.render import lookup_translation
from .....domain.iva.classification import InvoiceKind
from ...components.host import ScreenHostApp
from ..controller import LedgerWorkspaceController
from ..invoice_entry import LedgerInvoiceEntryScreen
from ..models import (
    LedgerFlowState,
    LedgerInvoiceAddResultV1,
    LedgerInvoiceEntryV1,
    LedgerInvoiceLineEntryV1,
)
from ..workspace_injection import LedgerWorkspaceInjection
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

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


def _text(screen: LedgerInvoiceEntryScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


@pytest.mark.asyncio
async def test_mixed_rate_lines_and_invoice_facts_reach_the_add_door_as_typed() -> None:
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
            amount_label = lookup_translation("tui.ledger.invoice.line.field.iva_amount", locale="en")
            assert amount_label is not None
            assert f"{amount_label} is required." in refusal
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
async def test_invoice_amounts_and_dates_refuse_every_shape_the_command_line_refuses() -> None:
    door = _RecordingDoor()
    screen = _entry_screen(door)
    date_label = lookup_translation("tui.ledger.invoice.field.invoice_date", locale="en")
    base_label = lookup_translation("tui.ledger.invoice.field.taxable_base", locale="en")
    assert date_label is not None
    assert base_label is not None
    refused_dates = ("20260315", "2026-W11-7", "2026-03-32")
    refused_amounts = ("1e3", "+5", "1_000", "NaN", "Infinity", "1.234", "10.005")
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 200)) as pilot:
            await pilot.pause()
            _header(screen)
            for raw in refused_dates:
                _fill(screen, invoice_date=raw, taxable_base="10.00", iva_rate="21")
                screen.query_one("#ledger-invoice-review", Button).press()
                await pilot.pause()
                assert screen.flow_state is LedgerFlowState.EDITING, raw
                assert f"{date_label} must be a date written YYYY-MM-DD." in _text(screen, "#ledger-refusal"), raw
            for raw in refused_amounts:
                _fill(screen, invoice_date="2026-03-15", taxable_base=raw, iva_rate="21")
                screen.query_one("#ledger-invoice-review", Button).press()
                await pilot.pause()
                assert screen.flow_state is LedgerFlowState.EDITING, raw
                assert f"{base_label} must be a number" in _text(screen, "#ledger-refusal"), raw
    assert not door.entries


@pytest.mark.asyncio
async def test_a_line_number_outside_the_canonical_grammar_is_refused_but_sub_cent_precision_is_kept() -> None:
    door = _RecordingDoor()
    screen = _entry_screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 200)) as pilot:
            await pilot.pause()
            for raw in ("1e3", "+5", "1_000", "NaN", "-Infinity"):
                _type_line(screen, {**_LINES[0], "quantity": raw})
                await pilot.pause()
                assert "Quantity must be a number" in _text(screen, "#ledger-refusal"), raw
                assert screen.lines == [], raw
            _type_line(screen, {**_LINES[0], "quantity": "8", "unit_price": "1.25", "subtotal": "10.00"})
            await pilot.pause()
            _type_line(screen, {**_LINES[1], "quantity": "40", "unit_price": "0.125", "subtotal": "5.00"})
            await pilot.pause()
            assert [line.unit_price for line in screen.lines] == [Decimal("1.25"), Decimal("0.125")]
    assert not door.entries


@pytest.mark.asyncio
async def test_an_issued_business_premises_lease_reaches_the_add_door_with_its_premises() -> None:
    """The form states the lessor's lease facts the add operation takes (RD 1065/2007 art. 34.1.d)."""
    door = _RecordingDoor()
    screen = _entry_screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 220)) as pilot:
            await pilot.pause()
            _header(screen)
            screen.query_one("#ledger-invoice-kind", Select).value = InvoiceKind.ISSUED.value
            screen.query_one("#ledger-invoice-lease", Select).value = str(True)
            screen.query_one("#ledger-invoice-situacion-inmueble", Select).value = "1"
            _fill(screen, referencia_catastral="9872023VH5797S0001WX")
            _type_line(screen, _LINES[0])
            await pilot.pause()

            screen.query_one("#ledger-invoice-review", Button).press()
            await pilot.pause()
            assert screen.flow_state is LedgerFlowState.CONFIRMING, _text(screen, "#ledger-refusal")
            assert "Business premises lease · situación 1 · referencia catastral 9872023VH5797S0001WX" in _text(
                screen, "#ledger-invoice-summary"
            )
            screen.query_one("#ledger-invoice-confirm", Button).press()
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()

    (entry,) = door.entries
    assert entry.kind is InvoiceKind.ISSUED
    assert entry.arrendamiento_local_negocio is True
    assert entry.situacion_inmueble == "1"
    assert entry.referencia_catastral == "9872023VH5797S0001WX"


@pytest.mark.asyncio
async def test_an_invoice_entered_without_the_lease_choice_states_no_lease() -> None:
    door = _RecordingDoor()
    screen = _entry_screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 220)) as pilot:
            await pilot.pause()
            _header(screen)
            _type_line(screen, _LINES[0])
            await pilot.pause()
            screen.query_one("#ledger-invoice-review", Button).press()
            await pilot.pause()
            assert "Business premises lease" not in _text(screen, "#ledger-invoice-summary")
            screen.query_one("#ledger-invoice-confirm", Button).press()
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()

    (entry,) = door.entries
    assert entry.arrendamiento_local_negocio is False
    assert entry.situacion_inmueble is None
    assert entry.referencia_catastral is None
