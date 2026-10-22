"""Focused mounted behavior for the invoice catalogue and the invoice and transaction detail screens.

The screens receive the registered operations' public projections through
in-memory doors that refuse a write against a record that changed, as the
runtime doors do after their re-read.
"""

from __future__ import annotations

from typing import cast, override

import pytest
from textual.containers import VerticalScroll
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Select, Static
from textual.worker import NoActiveWorker, get_current_worker

from .....application.invoices.catalogue_lifecycle import CatalogueInvoicePatch
from .....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from .....application.ledger.transaction_projection import LedgerTransactionProjection
from .....application.ledger.update_contracts import LedgerUpdatePatch, LedgerUpdatePatchField
from .....core.config import override_settings
from .....core.i18n.render import lookup_translation, tr
from .....domain.invoices.errors import InvoiceValidationError
from .....domain.iva.schema import InvoiceKind
from .....domain.transactions.errors import TransactionValidationError
from ...components.host import ScreenHostApp
from ...tests.frame import geometry_band
from ..controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from ..models import LedgerRecordDoorsV1
from ..record_views import INVOICE_PAGE_SIZE, LedgerInvoiceCatalogueScreen, LedgerInvoiceDetailScreen
from ..transaction_views import LedgerTransactionDetailScreen
from ..workspace_injection import LedgerWorkspaceInjection
from .invoices_fixtures import STALE_KEY, MemoryRecordDoors, invoice_snapshot, transaction_projection
from .test_ledger_selection_journey import _WorkspaceHostApp
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_SIZES = ((80, 24), (100, 30), (120, 40), (200, 50))
_THEMES = ("cadrumo-dark", "cadrumo-light")


def _controller(doors: MemoryRecordDoors) -> LedgerWorkspaceController:
    return LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), record_doors=cast(LedgerRecordDoorsV1, doors)),
    )


def _catalogue(doors: MemoryRecordDoors) -> LedgerInvoiceCatalogueScreen:
    return LedgerInvoiceCatalogueScreen(_controller(doors), cast(LedgerRecordDoorsV1, doors))


def _detail(doors: MemoryRecordDoors, invoice_id: str) -> LedgerInvoiceDetailScreen:
    return LedgerInvoiceDetailScreen(_controller(doors), cast(LedgerRecordDoorsV1, doors), invoice_id)


def _text(screen: LedgerWorkspaceScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _keys(screen: LedgerWorkspaceScreen) -> list[str]:
    table = cast("DataTable[str]", screen.query_one("#ledger-invoice-catalogue", DataTable))
    return [str(row.key.value) for row in table.ordered_rows]


async def _settle(pilot: Pilot[None]) -> None:
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def _press(pilot: Pilot[None], screen: LedgerWorkspaceScreen, button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await _settle(pilot)


@pytest.mark.asyncio
async def test_invoice_catalogue_opens_canonical_detail_and_saves_reviewed_notes() -> None:
    doors = MemoryRecordDoors((invoice_snapshot(notes="before"),))
    screen = _catalogue(doors)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(screen).run_test(size=(110, 55)) as pilot:
            await _settle(pilot)
            table = screen.query_one("#ledger-invoice-catalogue", DataTable)
            assert table.row_count == 1
            table.focus()
            table.move_cursor(row=0)
            await pilot.press("enter")
            await _settle(pilot)
            detail = pilot.app.screen
            assert isinstance(detail, LedgerInvoiceDetailScreen)
            rendered = _text(detail, "#ledger-record-detail")
            assert (
                tr("tui.ledger.records.totals", base="100.00", iva="21.00", total="121.00", currency="EUR") in rendered
            )
            row_template = lookup_translation("tui.ledger.invoice.line.row", locale="en")
            assert row_template is not None
            assert (
                row_template.format(
                    index=1,
                    description="Synthetic service",
                    quantity="1",
                    unit_price="100.00",
                    subtotal="100.00",
                    rate="RATE_21",
                    amount="21.00",
                )
                in rendered
            )
            assert detail.query_one("#ledger-invoice-notes", Input).value == "before"
            detail.query_one("#ledger-invoice-notes", Input).value = "after"
            await _press(pilot, detail, "ledger-invoice-edit-review")
            assert doors.writes == []
            staged = _text(detail, "#ledger-invoice-staged")
            assert (
                tr(
                    "tui.ledger.records.change",
                    field=tr("tui.ledger.invoice.field.notes"),
                    before="before",
                    after="after",
                )
                in staged
            )
            assert detail.query_one("#ledger-invoice-notes", Input).disabled
            await _press(pilot, detail, "ledger-invoice-edit-save")
            assert doors.writes == [("update", invoice_snapshot().invoice_id)]
            assert doors.catalogue[invoice_snapshot().invoice_id].notes == "after"
            assert detail.baseline == doors.catalogue[invoice_snapshot().invoice_id]
            assert _text(detail, "#ledger-flow-status") == tr("tui.ledger.records.saved")


@pytest.mark.asyncio
async def test_an_unchanged_form_is_not_staged() -> None:
    doors = MemoryRecordDoors((invoice_snapshot(),))
    detail = _detail(doors, invoice_snapshot().invoice_id)
    async with ScreenHostApp[None](detail).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
        await _press(pilot, detail, "ledger-invoice-edit-review")
        assert detail.staged is None
        assert _text(detail, "#ledger-refusal") == tr("tui.ledger.records.no_change")


@pytest.mark.asyncio
async def test_a_correction_against_a_changed_invoice_is_refused_with_a_reload_hint() -> None:
    doors = MemoryRecordDoors((invoice_snapshot(notes="seen"),))
    detail = _detail(doors, invoice_snapshot().invoice_id)
    async with ScreenHostApp[None](detail).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
        detail.query_one("#ledger-invoice-notes", Input).value = "mine"
        await _press(pilot, detail, "ledger-invoice-edit-review")
        # Another session corrects the invoice after this screen read it.
        changed = invoice_snapshot(notes="theirs")
        doors.catalogue[changed.invoice_id] = changed
        await _press(pilot, detail, "ledger-invoice-edit-save")
        assert doors.writes == []
        assert _text(detail, "#ledger-refusal") == tr(STALE_KEY)
        assert _text(detail, "#ledger-flow-status") == tr("tui.ledger.records.failed")
        assert detail.baseline == invoice_snapshot(notes="seen")


@pytest.mark.asyncio
async def test_correcting_several_fields_sends_only_the_changed_ones() -> None:
    doors = MemoryRecordDoors((invoice_snapshot(),))
    detail = _detail(doors, invoice_snapshot().invoice_id)
    async with ScreenHostApp[None](detail).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
        detail.query_one("#ledger-invoice-series", Input).value = "B"
        detail.query_one("#ledger-invoice-retention-rate", Input).value = "15"
        cast("Select[str]", detail.query_one("#ledger-invoice-payment-status", Select)).value = "PAID"
        await _press(pilot, detail, "ledger-invoice-edit-review")
        await _press(pilot, detail, "ledger-invoice-edit-save")
    assert len(doors.invoice_patches) == 1
    patch = doors.invoice_patches[0]
    assert patch.model_fields_set == {"series", "retention_rate", "payment_status"}
    assert str(patch.retention_rate) == "15"
    assert doors.writes == [("update", invoice_snapshot().invoice_id)]


@pytest.mark.asyncio
async def test_removing_an_invoice_asks_first_and_returns_to_the_catalogue() -> None:
    kept, removed = invoice_snapshot(0), invoice_snapshot(1)
    doors = MemoryRecordDoors((kept, removed))
    detail = _detail(doors, removed.invoice_id)
    with override_settings(cadrumo_output_language="en"):
        async with _WorkspaceHostApp(detail).run_test(size=(110, 55)) as pilot:
            await _settle(pilot)
            await _press(pilot, detail, "ledger-invoice-remove")
            assert doors.writes == []
            dialog_message = str(pilot.app.screen.query_one("#confirm-message", Static).render())
            assert dialog_message == tr(
                "tui.ledger.records.remove_message",
                number=removed.invoice_number,
                counterparty=removed.counterparty_name,
                total="121.00 EUR",
            )
            pilot.app.screen.query_one("#btn-confirm-accept", Button).press()
            await _settle(pilot)
            await _settle(pilot)
            assert doors.writes == [("remove", removed.invoice_id)]
            catalogue = pilot.app.screen
            assert isinstance(catalogue, LedgerInvoiceCatalogueScreen)
            assert _keys(catalogue) == [kept.invoice_id]
            assert _text(catalogue, "#ledger-flow-status") == tr(
                "tui.ledger.records.removed", number=removed.invoice_number
            )


@pytest.mark.asyncio
async def test_cancelling_a_removal_writes_nothing() -> None:
    doors = MemoryRecordDoors((invoice_snapshot(),))
    detail = _detail(doors, invoice_snapshot().invoice_id)
    async with ScreenHostApp[None](detail).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
        await _press(pilot, detail, "ledger-invoice-remove")
        pilot.app.screen.query_one("#btn-confirm-cancel", Button).press()
        await _settle(pilot)
        assert pilot.app.screen is detail
        assert doors.writes == []
        assert invoice_snapshot().invoice_id in doors.catalogue
        assert _text(detail, "#ledger-flow-status") == tr("tui.ledger.records.remove_cancelled")


@pytest.mark.asyncio
async def test_a_refused_removal_is_shown_and_the_invoice_stays() -> None:
    linked = invoice_snapshot(linked=("e" * 64,))
    doors = MemoryRecordDoors((linked,))
    doors.refusal = InvoiceValidationError(
        translated_message="application.invoices.lifecycle.errors.remove_linked_invoice",
        context={"invoice_id": linked.invoice_id, "linked_transaction_ids": "e" * 64},
    )
    detail = _detail(doors, linked.invoice_id)
    async with ScreenHostApp[None](detail).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
        await _press(pilot, detail, "ledger-invoice-remove")
        pilot.app.screen.query_one("#btn-confirm-accept", Button).press()
        await _settle(pilot)
        assert pilot.app.screen is detail
        assert doors.writes == []
        assert _text(detail, "#ledger-refusal") == tr(
            "application.invoices.lifecycle.errors.remove_linked_invoice",
            invoice_id=linked.invoice_id,
            linked_transaction_ids="e" * 64,
        )
        assert not detail.query_one("#ledger-invoice-remove", Button).disabled


@pytest.mark.asyncio
async def test_the_catalogue_renders_one_page_of_a_large_catalogue_and_pages_both_ways() -> None:
    total = 10 * INVOICE_PAGE_SIZE + 5
    invoices = tuple(invoice_snapshot(index) for index in range(total))
    doors = MemoryRecordDoors(invoices)
    screen = _catalogue(doors)
    async with ScreenHostApp[None](screen).run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        assert _keys(screen) == [row.invoice_id for row in invoices[:INVOICE_PAGE_SIZE]]
        assert screen.query_one("#ledger-invoice-previous", Button).disabled
        for _ in range(10):
            await _press(pilot, screen, "ledger-invoice-next")
        assert _keys(screen) == [row.invoice_id for row in invoices[10 * INVOICE_PAGE_SIZE :]]
        assert screen.query_one("#ledger-invoice-next", Button).disabled
        await _press(pilot, screen, "ledger-invoice-previous")
        assert _keys(screen) == [row.invoice_id for row in invoices[9 * INVOICE_PAGE_SIZE : 10 * INVOICE_PAGE_SIZE]]
    assert INVOICE_PAGE_SIZE <= 200


@pytest.mark.asyncio
async def test_back_from_an_invoice_lands_on_its_row_by_identity() -> None:
    invoices = tuple(invoice_snapshot(index) for index in range(INVOICE_PAGE_SIZE + 3))
    chosen = invoices[INVOICE_PAGE_SIZE + 1]
    doors = MemoryRecordDoors(invoices)
    detail = _detail(doors, chosen.invoice_id)
    async with _WorkspaceHostApp(detail).run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        await pilot.press("escape")
        await _settle(pilot)
        await _settle(pilot)
        catalogue = pilot.app.screen
        assert isinstance(catalogue, LedgerInvoiceCatalogueScreen)
        assert catalogue.page == 1
        table = cast("DataTable[str]", catalogue.query_one("#ledger-invoice-catalogue", DataTable))
        assert table.ordered_rows[table.cursor_row].key.value == chosen.invoice_id


@pytest.mark.asyncio
async def test_the_kind_filter_keeps_only_that_kind() -> None:
    issued = invoice_snapshot(0, kind=InvoiceKind.ISSUED)
    received = invoice_snapshot(1, kind=InvoiceKind.RECEIVED)
    doors = MemoryRecordDoors((issued, received))
    screen = _catalogue(doors)
    async with ScreenHostApp[None](screen).run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        assert _keys(screen) == [issued.invoice_id, received.invoice_id]
        cast("Select[str]", screen.query_one("#ledger-invoice-kind-filter", Select)).value = InvoiceKind.ISSUED.value
        await _settle(pilot)
        assert _keys(screen) == [issued.invoice_id]


@pytest.mark.asyncio
async def test_an_empty_catalogue_says_so_and_a_refused_read_is_shown() -> None:
    empty = _catalogue(MemoryRecordDoors())
    async with ScreenHostApp[None](empty).run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        assert _keys(empty) == []
        assert _text(empty, "#ledger-flow-status") == tr("tui.ledger.records.no_invoices")
        assert empty.query_one("#ledger-invoice-next", Button).disabled

    doors = MemoryRecordDoors()
    doors.read_refusal = InvoiceValidationError(translated_message="tui.ledger.records.failed", context={})
    refused = _catalogue(doors)
    async with ScreenHostApp[None](refused).run_test(size=(120, 40)) as pilot:
        await _settle(pilot)
        assert _text(refused, "#ledger-refusal") == tr("tui.ledger.records.failed")


@pytest.mark.asyncio
async def test_imported_invoice_detail_shows_stored_filename_and_row() -> None:
    invoice = invoice_snapshot(source_filename="march-invoices.xlsx")
    detail = _detail(MemoryRecordDoors((invoice,)), invoice.invoice_id)
    async with ScreenHostApp[None](detail).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
        assert "march-invoices.xlsx:7" in _text(detail, "#ledger-record-detail")


def _transaction_screen(doors: MemoryRecordDoors, transaction_id: str) -> LedgerTransactionDetailScreen:
    return LedgerTransactionDetailScreen(_controller(doors), cast(LedgerRecordDoorsV1, doors), transaction_id)


@pytest.mark.asyncio
async def test_transaction_detail_stages_and_saves_only_the_changed_fields() -> None:
    transaction = transaction_projection()
    doors = MemoryRecordDoors(transactions=(transaction,))
    screen = _transaction_screen(doors, transaction.transaction_id)
    async with ScreenHostApp[None](screen).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
        screen.query_one("#ledger-transaction-description", Input).value = "changed description"
        screen.query_one("#ledger-transaction-taxable-base", Input).value = "100.00"
        cast("Select[str]", screen.query_one("#ledger-transaction-direction", Select)).value = "INCOMING"
        await _press(pilot, screen, "ledger-transaction-edit-review")
        assert doors.transaction_patches == []
        staged = _text(screen, "#ledger-transaction-staged")
        assert (
            tr(
                "tui.ledger.records.change",
                field=tr("tui.ledger.records.transaction_field.description"),
                before="Synthetic bank movement",
                after="changed description",
            )
            in staged
        )
        await _press(pilot, screen, "ledger-transaction-edit-save")
        assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.records.saved")
    patch, fields = doors.transaction_patches[0]
    assert fields == ("direction", "description", "taxable_base")
    assert (patch.description, patch.taxable_base, patch.direction) == ("changed description", "100", "INCOMING")
    assert doors.transactions[transaction.transaction_id].description == "changed description"


@pytest.mark.asyncio
async def test_linked_transaction_detail_shows_refusal_without_claiming_a_save() -> None:
    transaction = transaction_projection(invoice_id=invoice_snapshot().invoice_id)
    doors = MemoryRecordDoors(transactions=(transaction,))
    doors.refusal = TransactionValidationError(
        "linked transaction identity cannot change without updating its invoice link"
    )
    screen = _transaction_screen(doors, transaction.transaction_id)
    async with ScreenHostApp[None](screen).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
        screen.query_one("#ledger-transaction-description", Input).value = "changed description"
        await _press(pilot, screen, "ledger-transaction-edit-review")
        await _press(pilot, screen, "ledger-transaction-edit-save")
        assert "identity cannot change" in _text(screen, "#ledger-refusal")
        assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.records.failed")
        assert screen.baseline == transaction
        assert doors.transactions[transaction.transaction_id] == transaction


@pytest.mark.asyncio
async def test_a_transaction_correction_against_a_changed_record_is_refused_with_a_reload_hint() -> None:
    transaction = transaction_projection()
    doors = MemoryRecordDoors(transactions=(transaction,))
    screen = _transaction_screen(doors, transaction.transaction_id)
    async with ScreenHostApp[None](screen).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
        screen.query_one("#ledger-transaction-notes", Input).value = "mine"
        await _press(pilot, screen, "ledger-transaction-edit-review")
        doors.transactions[transaction.transaction_id] = transaction_projection(description="changed elsewhere")
        await _press(pilot, screen, "ledger-transaction-edit-save")
        assert _text(screen, "#ledger-refusal") == tr(STALE_KEY)
        assert doors.writes == []


class _WorkerOnlyDoors(MemoryRecordDoors):
    """Records whether each door call ran inside a Textual worker rather than a handler."""

    def __init__(self) -> None:
        super().__init__((invoice_snapshot(),), (transaction_projection(),))
        self.calls: list[tuple[str, bool]] = []

    def _enter(self, name: str) -> None:
        try:
            get_current_worker()
        except NoActiveWorker:
            self.calls.append((name, False))
        else:
            self.calls.append((name, True))

    @override
    async def invoices(self) -> tuple[CatalogueInvoiceSnapshot, ...]:
        self._enter("invoices")
        return await super().invoices()

    @override
    async def invoice(self, invoice_id: str) -> CatalogueInvoiceSnapshot:
        self._enter("invoice")
        return await super().invoice(invoice_id)

    @override
    async def update_invoice(
        self, baseline: CatalogueInvoiceSnapshot, patch: CatalogueInvoicePatch
    ) -> CatalogueInvoiceSnapshot:
        self._enter("update_invoice")
        return await super().update_invoice(baseline, patch)

    @override
    async def remove_invoice(self, baseline: CatalogueInvoiceSnapshot) -> CatalogueInvoiceSnapshot:
        self._enter("remove_invoice")
        return await super().remove_invoice(baseline)

    @override
    async def transaction(self, transaction_id: str) -> LedgerTransactionProjection:
        self._enter("transaction")
        return await super().transaction(transaction_id)

    @override
    async def update_transaction(
        self,
        baseline: LedgerTransactionProjection,
        patch: LedgerUpdatePatch,
        fields: tuple[LedgerUpdatePatchField, ...],
    ) -> LedgerTransactionProjection:
        self._enter("update_transaction")
        return await super().update_transaction(baseline, patch, fields)


@pytest.mark.asyncio
async def test_every_record_door_runs_in_a_worker_off_the_input_handlers() -> None:
    doors = _WorkerOnlyDoors()
    catalogue = _catalogue(doors)
    async with ScreenHostApp[None](catalogue).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
    detail = _detail(doors, invoice_snapshot().invoice_id)
    async with ScreenHostApp[None](detail).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
        detail.query_one("#ledger-invoice-notes", Input).value = "after"
        await _press(pilot, detail, "ledger-invoice-edit-review")
        await _press(pilot, detail, "ledger-invoice-edit-save")
        await _press(pilot, detail, "ledger-invoice-remove")
        pilot.app.screen.query_one("#btn-confirm-accept", Button).press()
        await _settle(pilot)
    transaction = _transaction_screen(doors, transaction_projection().transaction_id)
    async with ScreenHostApp[None](transaction).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
        transaction.query_one("#ledger-transaction-description", Input).value = "changed"
        await _press(pilot, transaction, "ledger-transaction-edit-review")
        await _press(pilot, transaction, "ledger-transaction-edit-save")

    assert {name for name, _in_worker in doors.calls} == {
        "invoices",
        "invoice",
        "update_invoice",
        "remove_invoice",
        "transaction",
        "update_transaction",
    }
    assert [name for name, in_worker in doors.calls if not in_worker] == []


def _assert_geometry(app: ScreenHostApp[None], screen: LedgerWorkspaceScreen, width: int) -> None:
    assert geometry_band(app, width) == []
    assert all(table.max_scroll_x == 0 for table in screen.query(DataTable))
    owners = [widget for widget in screen.query(VerticalScroll) if widget.display and widget.show_vertical_scrollbar]
    assert all(owner.id == "ledger-page" for owner in owners)


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", _THEMES)
@pytest.mark.parametrize("size", _SIZES)
async def test_record_screens_fit_every_supported_terminal(theme: str, size: tuple[int, int]) -> None:
    invoices = tuple(invoice_snapshot(index) for index in range(30))
    for build in (
        lambda doors: _catalogue(doors),
        lambda doors: _detail(doors, invoices[0].invoice_id),
        lambda doors: _transaction_screen(doors, transaction_projection().transaction_id),
    ):
        doors = MemoryRecordDoors(invoices, (transaction_projection(),))
        screen = build(doors)
        app = ScreenHostApp[None](screen)
        with override_settings(cadrumo_output_language="en"):
            async with app.run_test(size=size) as pilot:
                app.theme = theme
                await _settle(pilot)
                _assert_geometry(app, screen, size[0])


@pytest.mark.asyncio
async def test_a_refused_record_read_is_shown_and_nothing_can_be_staged() -> None:
    missing_invoice = _detail(MemoryRecordDoors(), invoice_snapshot().invoice_id)
    async with ScreenHostApp[None](missing_invoice).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
        assert _text(missing_invoice, "#ledger-refusal") == tr(
            "application.invoices.lifecycle.errors.invoice_not_found", invoice_id=invoice_snapshot().invoice_id
        )
        assert missing_invoice.query_one("#ledger-invoice-edit-review", Button).disabled
        assert missing_invoice.query_one("#ledger-invoice-remove", Button).disabled

    missing_transaction = _transaction_screen(MemoryRecordDoors(), transaction_projection().transaction_id)
    async with ScreenHostApp[None](missing_transaction).run_test(size=(110, 55)) as pilot:
        await _settle(pilot)
        assert _text(missing_transaction, "#ledger-refusal") == tr(STALE_KEY)
        assert missing_transaction.query_one("#ledger-transaction-edit-review", Button).disabled
