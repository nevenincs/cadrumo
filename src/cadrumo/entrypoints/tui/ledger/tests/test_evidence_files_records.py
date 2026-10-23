"""Evidence records: list one page at a time, view, correct and remove through the confirmed write step."""

from __future__ import annotations

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input

from .....application.ledger.evidence_mutation_operation import (
    LedgerEvidenceRemoveRequest,
    LedgerEvidenceUpdateRequest,
)
from .....application.ledger.evidence_read_operation import LedgerEvidenceQueryRequest
from .....core.config import override_settings
from .....core.i18n.render import tr
from ...components.dialogs import ConfirmScreen
from ...tests.settling import settle
from ..controller import LedgerWorkspaceController
from ..evidence_files_doors import LEDGER_EVIDENCE_FILES_PAGE_SIZE
from ..evidence_files_records import LedgerEvidenceFilesRecordsScreen
from ..evidence_files_write import LedgerEvidenceFilesWriteScreen
from ..models import LedgerFlowState
from ..workspace_injection import LedgerWorkspaceInjection
from .evidence_files_fixtures import (
    EVIDENCE_FILES_REFUSAL_KEY,
    MemoryEvidenceFilesStore,
    press,
    synthetic_evidence_id,
    text_of,
)
from .workspace_fixtures import WorkspaceHostApp, ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _screen(store: MemoryEvidenceFilesStore) -> LedgerEvidenceFilesRecordsScreen:
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    return LedgerEvidenceFilesRecordsScreen(controller, store.doors())


def _records(pilot: Pilot[None]) -> DataTable[str]:
    return pilot.app.screen.query_one("#evidence-files-records", DataTable)


def _keys(pilot: Pilot[None]) -> list[str]:
    return [str(row.key.value) for row in _records(pilot).ordered_rows]


async def _select(pilot: Pilot[None], row: int) -> None:
    table = _records(pilot)
    table.focus()
    table.move_cursor(row=row)
    await pilot.press("enter")
    await settle(pilot)


def _type(pilot: Pilot[None], selector: str, value: str) -> None:
    pilot.app.screen.query_one(selector, Input).value = value


@pytest.mark.asyncio
async def test_a_correction_is_reviewed_confirmed_and_returns_to_the_same_record() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_records(3)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            assert _keys(pilot) == [synthetic_evidence_id(index) for index in (1, 2, 3)]
            await _select(pilot, 1)
            screen = pilot.app.screen
            assert tr(
                "tui.ledger.evidence_files.records.detail.invoice",
                supplier="Suministros Delta SL",
                number="F-2026-0002",
                date="2026-03-14",
            ) in text_of(screen, "#evidence-files-detail")
            assert screen.query_one("#evidence-files-field-supplier", Input).value == "Suministros Delta SL"

            _type(pilot, "#evidence-files-field-supplier", "Suministros Gamma SL")
            _type(pilot, "#evidence-files-field-taxable-base", "110")
            await press(pilot, "evidence-files-review-update")
            write = pilot.app.screen
            assert isinstance(write, LedgerEvidenceFilesWriteScreen)
            assert write.flow_state is LedgerFlowState.CONFIRMING
            review = text_of(write, "#evidence-files-review")
            assert (
                tr(
                    "tui.ledger.evidence_files.records.stage.change",
                    field=tr("tui.ledger.evidence_files.field.supplier"),
                    current="Suministros Delta SL",
                    new="Suministros Gamma SL",
                )
                in review
            )
            assert store.requests_of(LedgerEvidenceUpdateRequest) == []

            await press(pilot, "evidence-files-confirm")
            assert write.flow_state is LedgerFlowState.SUCCEEDED
            [update] = store.requests_of(LedgerEvidenceUpdateRequest)
            assert update.evidence_id == synthetic_evidence_id(2)
            assert update.patch_fields == ("supplier", "taxable_base")
            assert text_of(write, "#ledger-flow-status") == tr("tui.ledger.evidence_files.write.saved")

            await press(pilot, "evidence-files-done")
            back = pilot.app.screen
            assert isinstance(back, LedgerEvidenceFilesRecordsScreen)
            assert back.selected_id == synthetic_evidence_id(2)
            table = _records(pilot)
            assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == synthetic_evidence_id(2)
            assert table.get_row_at(1)[2] == "Suministros Gamma SL"
            assert back.query_one("#evidence-files-field-taxable-base", Input).value == "110"


@pytest.mark.asyncio
async def test_a_removal_cancelled_at_its_dialog_writes_nothing_and_a_confirmed_one_removes() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_records(2)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _select(pilot, 0)
            await press(pilot, "evidence-files-review-remove")
            write = pilot.app.screen
            assert isinstance(write, LedgerEvidenceFilesWriteScreen)
            assert text_of(write, "#evidence-files-review") == tr(
                "tui.ledger.evidence_files.records.stage.remove",
                record=synthetic_evidence_id(1)[:12],
                file="factura-0001.pdf",
                supplier="Suministros Delta SL",
                number="F-2026-0001",
            )

            await press(pilot, "evidence-files-confirm")
            assert isinstance(pilot.app.screen, ConfirmScreen)
            await press(pilot, "btn-confirm-cancel")
            assert pilot.app.screen is write
            assert write.flow_state is LedgerFlowState.CONFIRMING
            assert store.requests_of(LedgerEvidenceRemoveRequest) == []

            await press(pilot, "evidence-files-confirm")
            await press(pilot, "btn-confirm-accept")
            assert write.flow_state is LedgerFlowState.SUCCEEDED
            assert [request.evidence_id for request in store.requests_of(LedgerEvidenceRemoveRequest)] == [
                synthetic_evidence_id(1)
            ]
            await press(pilot, "evidence-files-done")
            assert isinstance(pilot.app.screen, LedgerEvidenceFilesRecordsScreen)
            assert _keys(pilot) == [synthetic_evidence_id(2)]


@pytest.mark.asyncio
async def test_cancelling_a_staged_correction_returns_to_the_list_without_writing() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_records(1)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _select(pilot, 0)
            _type(pilot, "#evidence-files-field-notes", "Revisar con la gestoría")
            await press(pilot, "evidence-files-review-update")
            await press(pilot, "evidence-files-cancel")
            assert isinstance(pilot.app.screen, LedgerEvidenceFilesRecordsScreen)
            assert store.requests_of(LedgerEvidenceUpdateRequest) == []


@pytest.mark.asyncio
async def test_a_refused_correction_is_shown_on_the_write_step() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_records(1)
    store.refusing.add("update")
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _select(pilot, 0)
            _type(pilot, "#evidence-files-field-invoice-number", "F-2026-0099")
            await press(pilot, "evidence-files-review-update")
            await press(pilot, "evidence-files-confirm")
            write = pilot.app.screen
            assert isinstance(write, LedgerEvidenceFilesWriteScreen)
            assert write.flow_state is LedgerFlowState.FAILED
            assert text_of(write, "#ledger-refusal") == tr(EVIDENCE_FILES_REFUSAL_KEY)
            assert store.records[synthetic_evidence_id(1)].invoice_number == "F-2026-0001"


@pytest.mark.asyncio
async def test_an_unchanged_or_malformed_correction_is_refused_before_review() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_records(1)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _select(pilot, 0)
            await press(pilot, "evidence-files-review-update")
            screen = pilot.app.screen
            assert isinstance(screen, LedgerEvidenceFilesRecordsScreen)
            assert text_of(screen, "#ledger-refusal") == tr("tui.ledger.evidence_files.records.no_change")

            # The operation's own patch admits only canonical decimal text.
            _type(pilot, "#evidence-files-field-taxable-base", "100.00")
            await press(pilot, "evidence-files-review-update")
            assert isinstance(pilot.app.screen, LedgerEvidenceFilesRecordsScreen)
            assert "taxable_base" in text_of(screen, "#ledger-refusal")
            assert store.requests_of(LedgerEvidenceUpdateRequest) == []


@pytest.mark.asyncio
async def test_without_a_selection_nothing_can_be_staged() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_records(1)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            screen = pilot.app.screen
            assert screen.query_one("#evidence-files-review-update", Button).disabled
            assert screen.query_one("#evidence-files-review-remove", Button).disabled
            assert screen.query_one("#evidence-files-field-supplier", Input).disabled


@pytest.mark.asyncio
async def test_an_empty_list_says_so_and_a_typed_refusal_is_shown() -> None:
    store = MemoryEvidenceFilesStore()
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            assert _records(pilot).row_count == 0
            assert text_of(pilot.app.screen, "#ledger-flow-status") == tr("tui.ledger.evidence_files.records.empty")

            store.refusing.add("query")
            await press(pilot, "evidence-files-all")
            assert text_of(pilot.app.screen, "#ledger-refusal") == tr(EVIDENCE_FILES_REFUSAL_KEY)


@pytest.mark.asyncio
async def test_the_identity_filter_is_the_query_s_own_and_a_miss_says_none_matched() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_records(3)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            _type(pilot, "#evidence-files-filter", synthetic_evidence_id(3))
            await press(pilot, "evidence-files-search")
            assert _keys(pilot) == [synthetic_evidence_id(3)]
            assert store.requests_of(LedgerEvidenceQueryRequest)[-1].evidence_id == synthetic_evidence_id(3)

            _type(pilot, "#evidence-files-filter", "ffffffffffffffff")
            await press(pilot, "evidence-files-search")
            assert _keys(pilot) == []
            assert text_of(pilot.app.screen, "#ledger-flow-status") == tr(
                "tui.ledger.evidence_files.records.none_found"
            )


@pytest.mark.asyncio
async def test_a_thousand_records_render_one_page_and_page_forward_and_back() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_records(1_050)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            screen = pilot.app.screen
            assert _records(pilot).row_count == LEDGER_EVIDENCE_FILES_PAGE_SIZE
            assert screen.query_one("#evidence-files-records-previous", Button).disabled
            await press(pilot, "evidence-files-records-next")
            assert _keys(pilot)[0] == synthetic_evidence_id(LEDGER_EVIDENCE_FILES_PAGE_SIZE + 1)
            for _ in range(20):
                if screen.query_one("#evidence-files-records-next", Button).disabled:
                    break
                await press(pilot, "evidence-files-records-next")
            assert _records(pilot).row_count == 1_050 % LEDGER_EVIDENCE_FILES_PAGE_SIZE
            assert _keys(pilot)[-1] == synthetic_evidence_id(1_050)
            assert text_of(screen, "#evidence-files-records-position") == tr(
                "tui.ledger.evidence_files.page.position", first=1_001, last=1_050, total=1_050
            )
            await press(pilot, "evidence-files-records-previous")
            assert _records(pilot).row_count == LEDGER_EVIDENCE_FILES_PAGE_SIZE
            assert _keys(pilot)[0] == synthetic_evidence_id(901)


@pytest.mark.asyncio
async def test_a_record_removed_elsewhere_and_a_lost_session_both_clear_the_view() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_records(2)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            del store.records[synthetic_evidence_id(1)]
            await _select(pilot, 0)
            screen = pilot.app.screen
            assert isinstance(screen, LedgerEvidenceFilesRecordsScreen)
            assert text_of(screen, "#ledger-refusal") == tr("tui.ledger.evidence_files.records.gone")
            assert screen.selected is None

            await _select(pilot, 1)
            assert screen.selected is not None
            store.expired = True
            await press(pilot, "evidence-files-all")
            assert screen.selected is None
            assert _records(pilot).row_count == 0
            assert text_of(screen, "#evidence-files-detail") == ""
            assert screen.query_one("#evidence-files-field-supplier", Input).value == ""
