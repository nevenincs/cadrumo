"""A write whose session is lost before its outcome is known is said to be unknown, never refused.

The runtime reports such a write as a session error that carries the unknown
outcome. Every write flow still drops what it retained for the lost session,
and words the write as unknown with the operation named, because "not saved"
would invite a retry that could apply the change twice. The evidence body
offers an addition again only over records it has read again, and never
stays in flight once its confirmation is withdrawn.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import override

import pytest
from textual.widgets import Button, Input, Static

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from .....application.ledger.workspace import LedgerWorkspaceArea
from .....core.config import override_settings
from .....core.errors.error_codes import resolve_error_message
from .....core.i18n.render import tr
from .....domain.iva.schema import InvoiceKind
from ...account import AccountSessionExpiredError
from ...operations.outcome import SessionExpiredOutcomeUnknownError, SessionUnavailableOutcomeUnknownError
from ...tests.settling import SETTLE_TIMEOUT_SECONDS, settle, settle_until
from ..controller import LedgerWorkspaceController
from ..evidence import LedgerEvidenceScreen
from ..models import LedgerEvidenceConfirmationV1, LedgerEvidenceRecordRowV1, LedgerEvidenceRecordStatus
from ..review import LedgerReviewScreen
from ..workspace_injection import LedgerWorkspaceInjection, LedgerWorkspaceRefreshV1
from .invoices_fixtures import ReplacingHostApp
from .test_ledger_ingestion_surfaces import _EvidenceDoor
from .test_writes_hold_the_workspace import (
    _EVIDENCE_PATH,
    _FLOWS,
    _UNKNOWN,
    _click,
    _CountingGate,
    _Gate,
    _HeldEvidenceDoor,
    _rendered,
    _status,
    _text,
    _tools,
)
from .workspace_fixtures import ledger_context, ledger_evidence_action, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


class _SessionLostGate(_Gate):
    """Answers every held door call with a lost session that carries an unknown outcome."""

    def __init__(self, lost: AccountSessionExpiredError) -> None:
        super().__init__(error=None)
        self.lost = lost

    @override
    async def wait(self) -> None:
        await super().wait()
        raise self.lost


@pytest.mark.asyncio
@pytest.mark.parametrize("name", sorted(_FLOWS))
async def test_a_write_whose_session_is_lost_with_its_outcome_unknown_is_said_to_be_unknown(
    name: str, tmp_path: Path
) -> None:
    lost = SessionExpiredOutcomeUnknownError(_UNKNOWN)
    gate = _SessionLostGate(lost)
    gate.release.set()
    with override_settings(cadrumo_output_language="en"):
        flow = _FLOWS[name](gate, tmp_path)
        async with ReplacingHostApp(flow.body).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            body = await flow.submit(pilot)
            await settle(pilot)
            assert pilot.app.screen is body
            assert not body.in_flight
            assert _status(body) == tr("tui.ledger.flow.outcome_unknown")
            rendered = _rendered(body)
            # The operation is named, and the operator is told to sign in and read the records again.
            assert resolve_error_message(lost) in rendered
            assert _UNKNOWN.operation_id in rendered
            # The workspace is composed again on signing in; this body does not re-read over the lost session.
            assert not body.write_outcome_unknown


@pytest.mark.asyncio
async def test_a_write_whose_runtime_stops_answering_with_its_outcome_unknown_is_said_to_be_unknown(
    tmp_path: Path,
) -> None:
    lost = SessionUnavailableOutcomeUnknownError(_UNKNOWN)
    gate = _SessionLostGate(lost)
    gate.release.set()
    with override_settings(cadrumo_output_language="en"):
        flow = _FLOWS["invoice-entry"](gate, tmp_path)
        async with ReplacingHostApp(flow.body).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            body = await flow.submit(pilot)
            await settle(pilot)
            assert _status(body) == tr("tui.ledger.flow.outcome_unknown")
            assert resolve_error_message(lost) in _rendered(body)
            assert tr("tui.ledger.invoice.failure") not in _rendered(body)


@pytest.mark.asyncio
async def test_an_exclusion_whose_session_is_lost_drops_the_queue_it_was_read_for(tmp_path: Path) -> None:
    gate = _SessionLostGate(SessionExpiredOutcomeUnknownError(_UNKNOWN))
    gate.release.set()
    with override_settings(cadrumo_output_language="en"):
        flow = _FLOWS["review-exclusion"](gate, tmp_path)
        async with ReplacingHostApp(flow.body).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            body = await flow.submit(pilot)
            assert isinstance(body, LedgerReviewScreen)
            await settle(pilot)
            assert body.rows == ()
            assert not body.loaded
            assert body.pending_exclusion is None
            assert not body.excluding
            assert _status(body) == tr("tui.ledger.flow.outcome_unknown")


class _RecordsHeldEvidenceDoor(_HeldEvidenceDoor):
    """An evidence door whose record reads wait once held, then answer or find the session lost."""

    def __init__(self, gate: _Gate) -> None:
        super().__init__(gate)
        self.hold_reads = False
        self.lose_session_on_read = False
        self.read_started = threading.Event()
        self.read_release = threading.Event()

    @override
    def list_records(self) -> tuple[LedgerEvidenceRecordRowV1, ...]:
        if self.hold_reads:
            self.read_started.set()
            if not self.read_release.wait(timeout=10):
                raise AssertionError("the held record read was not released")
            if self.lose_session_on_read:
                raise AccountSessionExpiredError()
        return super().list_records()


def _evidence_body(door: _EvidenceDoor, *, refresh_fails: bool) -> LedgerEvidenceScreen:
    projection = ledger_projection()

    def refresh() -> LedgerWorkspaceRefreshV1:
        if refresh_fails:
            raise AccountSessionExpiredError()
        return LedgerWorkspaceRefreshV1(projection=projection, evidence_items=())

    controller = LedgerWorkspaceController(
        ledger_context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            evidence_action=ledger_evidence_action(),
            evidence_items=(),
            evidence_door=door,
            refresh=refresh,
            tools=_tools(LedgerWorkspaceArea.EVIDENCE),
        ),
    )
    return LedgerEvidenceScreen(controller)


@pytest.mark.asyncio
@pytest.mark.parametrize("refresh_fails", [False, True], ids=["refreshed", "refresh-failed"])
async def test_an_evidence_addition_with_an_unknown_outcome_returns_only_once_the_records_are_read(
    refresh_fails: bool,
) -> None:
    write = _CountingGate(error=_UNKNOWN)
    write.release.set()
    door = _RecordsHeldEvidenceDoor(write)
    body = _evidence_body(door, refresh_fails=refresh_fails)
    with override_settings(cadrumo_output_language="en"):
        async with ReplacingHostApp(body).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            door.hold_reads = True
            body.query_one("#ledger-evidence-path", Input).value = _EVIDENCE_PATH
            await _click(pilot, body, "ledger-evidence-add")
            assert await asyncio.to_thread(door.read_started.wait, SETTLE_TIMEOUT_SECONDS)
            await settle(pilot, workers=False)

            # The workspace re-read has landed, or failed, but the records it must show are still being read.
            add = body.query_one("#ledger-evidence-add", Button)
            assert add.disabled
            await _click(pilot, body, "ledger-evidence-add")
            assert write.calls == 1

            door.read_release.set()
            await settle(pilot)
            assert not add.disabled
            assert resolve_error_message(_UNKNOWN) in _text(body, "#ledger-refusal")
            # Whether or not the workspace was re-read, the status never claims the document was saved.
            status = _text(body, "#ledger-flow-status")
            assert "may or may not have been saved" in status
            assert "was saved" not in status


@pytest.mark.asyncio
async def test_an_evidence_addition_with_an_unknown_outcome_is_not_offered_when_the_records_cannot_be_read() -> None:
    write = _CountingGate(error=_UNKNOWN)
    write.release.set()
    door = _RecordsHeldEvidenceDoor(write)
    body = _evidence_body(door, refresh_fails=False)
    with override_settings(cadrumo_output_language="en"):
        async with ReplacingHostApp(body).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            door.hold_reads = True
            door.lose_session_on_read = True
            door.read_release.set()
            body.query_one("#ledger-evidence-path", Input).value = _EVIDENCE_PATH
            await _click(pilot, body, "ledger-evidence-add")
            await settle(pilot)

            assert door.read_started.is_set()
            assert body.query_one("#ledger-evidence-add", Button).disabled
            assert write.calls == 1


@pytest.mark.asyncio
async def test_a_records_load_started_before_an_unknown_addition_does_not_offer_add_again() -> None:
    write = _CountingGate(error=_UNKNOWN)
    write.release.set()
    door = _RecordsHeldEvidenceDoor(write)
    door.hold_reads = True
    projection = ledger_projection()
    refreshing = threading.Event()
    refreshed = threading.Event()

    def refresh() -> LedgerWorkspaceRefreshV1:
        refreshing.set()
        if not refreshed.wait(timeout=10):
            raise AssertionError("the held workspace re-read was not released")
        return LedgerWorkspaceRefreshV1(projection=projection, evidence_items=())

    controller = LedgerWorkspaceController(
        ledger_context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            evidence_action=ledger_evidence_action(),
            evidence_items=(),
            evidence_door=door,
            refresh=refresh,
            tools=_tools(LedgerWorkspaceArea.EVIDENCE),
        ),
    )
    body = LedgerEvidenceScreen(controller)
    with override_settings(cadrumo_output_language="en"):
        async with ReplacingHostApp(body).run_test(size=(120, 60)) as pilot:
            # The first records load is out, and still reading, when the addition is made.
            assert await asyncio.to_thread(door.read_started.wait, SETTLE_TIMEOUT_SECONDS)
            body.query_one("#ledger-evidence-path", Input).value = _EVIDENCE_PATH
            await _click(pilot, body, "ledger-evidence-add")
            assert await asyncio.to_thread(refreshing.wait, SETTLE_TIMEOUT_SECONDS)

            door.read_release.set()
            detail = body.query_one("#ledger-evidence-record-detail", Static)
            await settle_until(
                pilot,
                lambda: str(detail.render()) == tr("tui.ledger.evidence.records_empty"),
                "the first records load to render",
                workers=False,
            )
            # Those rows were read before the addition, so they cannot show whether it landed.
            add = body.query_one("#ledger-evidence-add", Button)
            assert add.disabled

            refreshed.set()
            await settle(pilot)
            assert not add.disabled
            assert write.calls == 1
            assert resolve_error_message(_UNKNOWN) in _text(body, "#ledger-refusal")


class _RecordsRefusedOnceDoor(_HeldEvidenceDoor):
    """An evidence door whose next record read is refused once armed, as a draining runtime refuses it."""

    def __init__(self, gate: _Gate) -> None:
        super().__init__(gate)
        self.refuse_next_read = False
        self.reads = 0

    @override
    def list_records(self) -> tuple[LedgerEvidenceRecordRowV1, ...]:
        self.reads += 1
        if self.refuse_next_read:
            self.refuse_next_read = False
            raise RefusalError(RefusalCode.DRAINING)
        return super().list_records()


class _CountedRefreshes:
    """Workspace re-reads that are counted, and refused for the call numbers in ``refused``."""

    def __init__(self, *, refused: frozenset[int] = frozenset()) -> None:
        self.refused = refused
        self.calls = 0

    def __call__(self) -> LedgerWorkspaceRefreshV1:
        number = self.calls
        self.calls += 1
        if number in self.refused:
            raise RefusalError(RefusalCode.DRAINING)
        return LedgerWorkspaceRefreshV1(projection=ledger_projection(), evidence_items=())


def _counted_evidence_body(door: _EvidenceDoor, refreshes: _CountedRefreshes) -> LedgerEvidenceScreen:
    projection = ledger_projection()
    controller = LedgerWorkspaceController(
        ledger_context(),
        projection,
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            evidence_action=ledger_evidence_action(),
            evidence_items=(),
            evidence_door=door,
            refresh=refreshes,
            tools=_tools(LedgerWorkspaceArea.EVIDENCE),
        ),
    )
    return LedgerEvidenceScreen(controller)


@pytest.mark.asyncio
async def test_an_unknown_addition_whose_records_fail_to_load_reads_them_again_when_add_is_pressed() -> None:
    write = _CountingGate(error=_UNKNOWN)
    write.release.set()
    door = _RecordsRefusedOnceDoor(write)
    refreshes = _CountedRefreshes()
    body = _counted_evidence_body(door, refreshes)
    with override_settings(cadrumo_output_language="en"):
        async with ReplacingHostApp(body).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            door.refuse_next_read = True
            body.query_one("#ledger-evidence-path", Input).value = _EVIDENCE_PATH
            await _click(pilot, body, "ledger-evidence-add")
            await settle(pilot)

            # The records that would show whether the document landed were not read: that is said, and Add
            # is offered to read them again, never to add the document a second time.
            add = body.query_one("#ledger-evidence-add", Button)
            assert _status(body) == tr("tui.ledger.flow.refresh_failed_unknown")
            assert resolve_error_message(_UNKNOWN) in _text(body, "#ledger-refusal")
            assert body.add_awaits_reread
            assert not add.disabled
            reads = door.reads

            await _click(pilot, body, "ledger-evidence-add")
            await settle(pilot)
            assert write.calls == 1
            assert refreshes.calls == 2
            assert door.reads == reads + 1
            assert not body.add_awaits_reread
            assert not add.disabled
            assert _status(body) == tr("tui.ledger.flow.outcome_unknown")
            assert resolve_error_message(_UNKNOWN) in _text(body, "#ledger-refusal")


@pytest.mark.asyncio
async def test_a_saved_addition_after_an_unknown_one_that_was_read_back_is_worded_as_saved_when_its_reread_fails() -> (
    None
):
    write = _CountingGate(error=_UNKNOWN)
    write.release.set()
    door = _HeldEvidenceDoor(write)
    refreshes = _CountedRefreshes(refused=frozenset({1}))
    body = _counted_evidence_body(door, refreshes)
    with override_settings(cadrumo_output_language="en"):
        async with ReplacingHostApp(body).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            body.query_one("#ledger-evidence-path", Input).value = _EVIDENCE_PATH
            await _click(pilot, body, "ledger-evidence-add")
            await settle(pilot)
            # Read back after the unknown addition, which therefore stops colouring later wording.
            assert refreshes.calls == 1
            assert not body.add_awaits_reread

            write.error = None
            body.query_one("#ledger-evidence-path", Input).value = _EVIDENCE_PATH
            await _click(pilot, body, "ledger-evidence-add")
            await settle(pilot)
            assert write.calls == 2
            assert refreshes.calls == 2
            # This addition returned, so it is saved; only the re-read after it failed.
            assert _status(body) == tr("tui.ledger.flow.refresh_failed")


_RECORD = LedgerEvidenceRecordRowV1(
    evidence_id="8747cbf318cf0adb",
    media_kind="pdf",
    file_name="invoice_A-0003.pdf",
    supplier=None,
    invoice_number=None,
    created_at="2026-09-16",
    status=LedgerEvidenceRecordStatus.AWAITING,
)


@pytest.mark.asyncio
async def test_a_confirmation_whose_review_is_withdrawn_before_it_runs_does_not_stay_in_flight() -> None:
    door = _EvidenceDoor(ready=True)
    door.records.append(_RECORD)
    body = _evidence_body(door, refresh_fails=False)
    with override_settings(cadrumo_output_language="en"):
        async with ReplacingHostApp(body).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            body.selected_record_id = _RECORD.evidence_id
            body.draft = await door.extract(_RECORD.evidence_id)
            body._reviewed_evidence_id = _RECORD.evidence_id
            confirmation = LedgerEvidenceConfirmationV1(
                evidence_id=_RECORD.evidence_id, kind=InvoiceKind.RECEIVED, country_code="ES"
            )

            body._start(body._confirm(confirmation), tr("tui.ledger.evidence.confirming"))
            # Withdrawn before the confirmation's worker has run, as choosing another record does.
            body._clear_review()
            assert body.in_flight
            await settle(pilot)

            assert not body.in_flight
            assert door.confirmed == []
            await pilot.press("escape")
            await settle(pilot)
            assert pilot.app.screen is not body
