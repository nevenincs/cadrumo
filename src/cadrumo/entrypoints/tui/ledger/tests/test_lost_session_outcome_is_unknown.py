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
from textual.widgets import Button, Input

from .....application.ledger.workspace import LedgerWorkspaceArea
from .....core.config import override_settings
from .....core.errors.error_codes import resolve_error_message
from .....core.i18n.render import tr
from .....domain.iva.schema import InvoiceKind
from ...account import AccountSessionExpiredError
from ...operations.outcome import SessionExpiredOutcomeUnknownError, SessionUnavailableOutcomeUnknownError
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
    _settle,
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
            await _settle(pilot)
            body = await flow.submit(pilot)
            await _settle(pilot)
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
            await _settle(pilot)
            body = await flow.submit(pilot)
            await _settle(pilot)
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
            await _settle(pilot)
            body = await flow.submit(pilot)
            assert isinstance(body, LedgerReviewScreen)
            await _settle(pilot)
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
            await _settle(pilot)
            door.hold_reads = True
            body.query_one("#ledger-evidence-path", Input).value = _EVIDENCE_PATH
            await _click(pilot, body, "ledger-evidence-add")
            assert await asyncio.to_thread(door.read_started.wait, 10)
            await pilot.pause()

            # The workspace re-read has landed, or failed, but the records it must show are still being read.
            add = body.query_one("#ledger-evidence-add", Button)
            assert add.disabled
            await _click(pilot, body, "ledger-evidence-add")
            assert write.calls == 1

            door.read_release.set()
            await _settle(pilot)
            assert not add.disabled
            assert resolve_error_message(_UNKNOWN) in _text(body, "#ledger-refusal")


@pytest.mark.asyncio
async def test_an_evidence_addition_with_an_unknown_outcome_is_not_offered_when_the_records_cannot_be_read() -> None:
    write = _CountingGate(error=_UNKNOWN)
    write.release.set()
    door = _RecordsHeldEvidenceDoor(write)
    body = _evidence_body(door, refresh_fails=False)
    with override_settings(cadrumo_output_language="en"):
        async with ReplacingHostApp(body).run_test(size=(120, 60)) as pilot:
            await _settle(pilot)
            door.hold_reads = True
            door.lose_session_on_read = True
            door.read_release.set()
            body.query_one("#ledger-evidence-path", Input).value = _EVIDENCE_PATH
            await _click(pilot, body, "ledger-evidence-add")
            await _settle(pilot)

            assert door.read_started.is_set()
            assert body.query_one("#ledger-evidence-add", Button).disabled
            assert write.calls == 1


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
            await _settle(pilot)
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
            await _settle(pilot)

            assert not body.in_flight
            assert door.confirmed == []
            await pilot.press("escape")
            await _settle(pilot)
            assert pilot.app.screen is not body
