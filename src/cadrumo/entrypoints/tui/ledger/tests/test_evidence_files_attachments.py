"""Attach and detach evidence for the selected entry; with no entry selected the tool says how to choose one."""

from __future__ import annotations

from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input

from .....application.ledger.attachment_mutation_operation import LedgerAttachRequest, LedgerDetachRequest
from .....core.config import override_settings
from .....core.i18n.render import tr
from ...components.dialogs import ConfirmScreen
from ...tests.settling import settle
from ..controller import LedgerWorkspaceController
from ..evidence_files_attachments import LedgerEvidenceFilesAttachmentsScreen, parse_identities
from ..evidence_files_write import LedgerEvidenceFilesWriteScreen
from ..models import LedgerFlowState
from ..workspace_injection import LedgerWorkspaceInjection
from .evidence_files_fixtures import EVIDENCE_FILES_REFUSAL_KEY, MemoryEvidenceFilesStore, press, text_of
from .workspace_fixtures import (
    LEDGER_TX_A,
    WorkspaceHostApp,
    ledger_context,
    ledger_focused_context,
    ledger_projection,
    ledger_review_action,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _screen(store: MemoryEvidenceFilesStore, *, focused: bool = True) -> LedgerEvidenceFilesAttachmentsScreen:
    controller = LedgerWorkspaceController(
        ledger_focused_context(LEDGER_TX_A) if focused else ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action()),
    )
    return LedgerEvidenceFilesAttachmentsScreen(controller, store.doors())


async def _select(pilot: Pilot[None], table_id: str, row: int) -> None:
    table = cast("DataTable[str]", pilot.app.screen.query_one(f"#{table_id}", DataTable))
    table.focus()
    table.move_cursor(row=row)
    await pilot.press("enter")
    await settle(pilot)


@pytest.mark.asyncio
async def test_with_no_entry_selected_the_tool_says_how_to_choose_one_and_offers_nothing() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_attachments(1)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store, focused=False)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            screen = pilot.app.screen
            assert text_of(screen, "#evidence-files-attachments-entry") == tr(
                "tui.ledger.evidence_files.attachments.choose_entry"
            )
            assert screen.query_one("#evidence-files-review-attach", Button).disabled
            assert screen.query_one("#evidence-files-review-detach", Button).disabled
            assert screen.query_one("#evidence-files-attach-ids", Input).disabled
            assert store.requests == []


@pytest.mark.asyncio
async def test_evidence_is_attached_to_and_detached_from_the_selected_entry() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_attachments(2)
    chosen = sorted(store.attachments)[0]
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            screen = pilot.app.screen
            assert isinstance(screen, LedgerEvidenceFilesAttachmentsScreen)
            assert text_of(screen, "#evidence-files-attachments-entry") == tr(
                "tui.ledger.evidence_files.attachments.entry", entry=screen.controller.entry_label(LEDGER_TX_A)
            )
            await _select(pilot, "evidence-files-attachments-pending", 0)
            assert parse_identities(screen.query_one("#evidence-files-attach-ids", Input).value) == (chosen,)

            await press(pilot, "evidence-files-review-attach")
            write = pilot.app.screen
            assert isinstance(write, LedgerEvidenceFilesWriteScreen)
            assert store.requests_of(LedgerAttachRequest) == []
            await press(pilot, "evidence-files-confirm")
            assert write.flow_state is LedgerFlowState.SUCCEEDED
            [attach] = store.requests_of(LedgerAttachRequest)
            assert attach.transaction_id == LEDGER_TX_A
            assert attach.attachment_ids == (chosen,)
            assert store.transactions[LEDGER_TX_A] == (chosen,)
            assert text_of(write, "#evidence-files-outcome").startswith(
                tr("tui.ledger.evidence_files.attachments.outcome.attached", count=1)
            )

            await press(pilot, "evidence-files-done")
            back = pilot.app.screen
            assert isinstance(back, LedgerEvidenceFilesAttachmentsScreen)
            linked = cast("DataTable[str]", back.query_one("#evidence-files-attachments-linked", DataTable))
            assert [row.key.value for row in linked.ordered_rows] == [chosen]

            await _select(pilot, "evidence-files-attachments-linked", 0)
            assert parse_identities(back.query_one("#evidence-files-detach-ids", Input).value) == (chosen,)
            await press(pilot, "evidence-files-review-detach")
            detach_step = pilot.app.screen
            assert isinstance(detach_step, LedgerEvidenceFilesWriteScreen)
            await press(pilot, "evidence-files-confirm")
            assert isinstance(pilot.app.screen, ConfirmScreen)
            await press(pilot, "btn-confirm-accept")
            assert detach_step.flow_state is LedgerFlowState.SUCCEEDED
            [detach] = store.requests_of(LedgerDetachRequest)
            assert detach.attachment_ids == (chosen,)
            assert store.transactions[LEDGER_TX_A] == ()

            await press(pilot, "evidence-files-done")
            assert text_of(pilot.app.screen, "#evidence-files-attachments-linked-hint") == tr(
                "tui.ledger.evidence_files.attachments.linked_none"
            )


@pytest.mark.asyncio
async def test_a_detach_cancelled_at_its_dialog_writes_nothing() -> None:
    store = MemoryEvidenceFilesStore()
    store.seed_attachments(1)
    chosen = next(iter(store.attachments))
    store.transactions[LEDGER_TX_A] = (chosen,)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            pilot.app.screen.query_one("#evidence-files-detach-ids", Input).value = chosen
            await press(pilot, "evidence-files-review-detach")
            await press(pilot, "evidence-files-confirm")
            await press(pilot, "btn-confirm-cancel")
            write = pilot.app.screen
            assert isinstance(write, LedgerEvidenceFilesWriteScreen)
            assert write.flow_state is LedgerFlowState.CONFIRMING
            await press(pilot, "evidence-files-cancel")
            assert isinstance(pilot.app.screen, LedgerEvidenceFilesAttachmentsScreen)
            assert store.requests_of(LedgerDetachRequest) == []
            assert store.transactions[LEDGER_TX_A] == (chosen,)


@pytest.mark.asyncio
async def test_the_operation_s_own_validation_refusal_is_shown_and_nothing_is_linked() -> None:
    store = MemoryEvidenceFilesStore()
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await press(pilot, "evidence-files-review-attach")
            assert text_of(pilot.app.screen, "#ledger-refusal") == tr(
                "tui.ledger.evidence_files.attachments.attach_required"
            )
            pilot.app.screen.query_one("#evidence-files-attach-ids", Input).value = "f" * 64
            await press(pilot, "evidence-files-review-attach")
            await press(pilot, "evidence-files-confirm")
            write = pilot.app.screen
            assert isinstance(write, LedgerEvidenceFilesWriteScreen)
            assert write.flow_state is LedgerFlowState.FAILED
            assert text_of(write, "#ledger-refusal") == "attachment not found"
            assert text_of(write, "#ledger-flow-status") == tr("tui.ledger.evidence_files.write.refused")
            assert store.transactions[LEDGER_TX_A] == ()


@pytest.mark.asyncio
async def test_a_typed_refusal_of_the_pending_queue_is_shown() -> None:
    store = MemoryEvidenceFilesStore()
    store.refusing.add("attachment_queue")
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(_screen(store)).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            assert text_of(pilot.app.screen, "#ledger-refusal") == tr(EVIDENCE_FILES_REFUSAL_KEY)


def test_typed_identities_split_on_any_separator_and_keep_the_first_of_a_repeat() -> None:
    assert parse_identities(" a, b;c  a\n") == ("a", "b", "c")
    assert parse_identities("   ") == ()
