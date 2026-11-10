"""Runtime activity keeps shared human sessions alive; idle expiry pushes sign-out."""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from pydantic import BaseModel

from cadrumo.application.ledger.rule_contracts import LedgerRuleAddRequest, LedgerRuleListRequest
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.operations.models import OperationId
from cadrumo.core.config import load_settings
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection, profile_operation_subject
from cadrumo.domain.transactions.enums import BusinessClassification
from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, AccessScope
from cadrumo_client.contracts.attendance import AttendancePending
from cadrumo_client.contracts.deadline_budget import exchange_deadline
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationControl,
    OperationObserve,
    OperationObserved,
    OperationSubmit,
    OperationSubmitted,
)
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus
from cadrumo_client.contracts.session_events import ConnectionEvent, SessionEvent, SignInChanged
from cadrumo_client.contracts.sign_in import SignInPresence, SignInStatusRequest
from cadrumo_client.transport.frontend_client import FrontendClient

from .stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows transport and workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_cli_and_tui_activity_renew_shared_login_then_idle_pushes_desktop_sign_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Native login observation, keychain and runtime wall clock are explicit
    # fixture ports; transport, custody, receipts and notifications are real.
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        clients = []
        ended: list[SessionEvent] = []
        all_retired = Event()

        def retired(event: ConnectionEvent) -> None:
            if isinstance(event, SessionEvent):
                ended.append(event)
                if len(ended) == 2:
                    all_retired.set()

        for frontend in (
            OperationFrontendProjection.CLI,
            OperationFrontendProjection.TUI,
        ):
            connection = runtime.connect()
            admitted = runtime.resume(connection, frontend)
            assert isinstance(admitted, ProfileStatus) and admitted.status.session_id is not None, admitted
            connection.subscribe_session_events(retired)
            clients.append((connection, admitted.status.session_id))

        watcher = runtime.connect()
        sign_in_changed = Event()

        def changed(event: ConnectionEvent) -> None:
            if isinstance(event, SignInChanged):
                sign_in_changed.set()

        watcher.subscribe_session_events(changed)
        watcher.sign_in_status(
            SignInStatusRequest(request_id=uuid4(), profile_id=runtime.profile_id, watch=True),
            deadline=time.monotonic() + 5,
        )
        # Activity renews by the configured idle window. A resumed lease is
        # issued at admission but ends at the stored sign-in's idle deadline,
        # counted from when the sign-in was stored, so it can be shorter.
        idle_window = timedelta(minutes=load_settings().cadrumo_bucket_default_idle_lock_minutes)
        original = runtime.lease(clients[0][1])
        assert original.expires_at <= original.issued_at + idle_window
        for connection, session_id in clients:
            runtime.clock.ahead += idle_window * 0.75
            reply = runtime.session(connection, session_id, "session_activity")
            assert isinstance(reply, ProfileStatus) and reply.status.denial is None
            assert all(runtime.lease(identity).expires_at > runtime.clock() for _, identity in clients)
            assert runtime.sign_in(watcher).presence is SignInPresence.PRESENT
            assert not ended

        # Status reads do not constitute input and cannot renew the deadline.
        before = runtime.lease(clients[0][1]).expires_at
        for connection, session_id in clients:
            runtime.session(connection, session_id, "session_status")
        assert runtime.lease(clients[0][1]).expires_at == before
        sign_in_changed.clear()
        runtime.clock.ahead += idle_window + timedelta(seconds=1)
        runtime.profiles.lifecycle_changed()
        runtime.profiles.poll()
        assert sign_in_changed.wait(5), "runtime did not cue the desktop sign-in observer on idle expiry"
        assert runtime.sign_in(watcher).presence is SignInPresence.ABSENT
        assert all_retired.wait(5), "each frontend must hear its own session retirement"
        assert {event.session_id for event in ended} == {identity for _, identity in clients}
        assert all(event.reason is AccessDenialCode.SESSION_EXPIRED for event in ended)
        assert not runtime.leases()


def _person(runtime: StoredSignInRuntime, frontend: OperationFrontendProjection) -> FrontendClient:
    client = FrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=frontend)
    admitted = client.resume_receipt()
    assert admitted.status.denial is None and admitted.status.session_id == client.session_id
    return client


def _submit(client: FrontendClient, definition_id: str, payload: BaseModel) -> OperationId:
    submitted = client.operation(
        OperationSubmit(
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=client.session_id,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(client.profile_id)),
            payload_json=payload.model_dump_json(),
        ),
        deadline=exchange_deadline(),
    )
    assert isinstance(submitted, OperationSubmitted), submitted
    return submitted.receipt.operation_id


def _start(client: FrontendClient, operation_id: OperationId) -> None:
    started = client.operation(
        OperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=client.session_id,
            operation_id=operation_id,
        ),
        deadline=exchange_deadline(),
    )
    assert isinstance(started, OperationAcknowledged), started


def _settled(client: FrontendClient, operation_id: OperationId) -> OperationPublicProjectionV1:
    """Start a submitted operation and observe it until it settles."""
    _start(client, operation_id)
    deadline = time.monotonic() + HANG_GUARD_SECONDS
    while time.monotonic() < deadline:
        observed = client.operation(
            OperationObserve(
                request_id=uuid4(),
                profile_id=client.profile_id,
                session_id=client.session_id,
                observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32),
            ),
            deadline=exchange_deadline(),
        )
        assert isinstance(observed, OperationObserved), observed
        assert isinstance(observed.observation, OperationObservationSuccessV1)
        if observed.observation.projection.terminal_condition is not None:
            return observed.observation.projection
        time.sleep(0.02)
    raise AssertionError("the operation did not settle")


def _rule(client: FrontendClient, pattern: str) -> LedgerRuleAddRequest:
    return LedgerRuleAddRequest(
        profile_id=client.profile_id,
        description_pattern=pattern,
        classification=BusinessClassification.BUSINESS,
        category_id="material_oficina",
    )


def _expiry_after_last_request(runtime: StoredSignInRuntime, client: FrontendClient) -> datetime:
    """Read the lease once the runtime has finished the client's last request, renewal included.

    A connection's requests are served in order, so this status read is
    answered only after the observation before it has been handled in full.
    """
    status = client.status()
    assert status.status.denial is None, status
    return runtime.lease(client.session_id).expires_at


def test_a_saved_change_on_an_attended_connection_renews_the_idle_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        tui = _person(runtime, OperationFrontendProjection.TUI)
        # The person's input report attends the connection; it renews nothing so soon after signing in.
        tui.note_activity()
        idle_window = timedelta(minutes=load_settings().cadrumo_bucket_default_idle_lock_minutes)
        signed_in = runtime.lease(tui.session_id).expires_at
        runtime.clock.ahead += idle_window / 2

        # Reads, the window's own refreshes among them, never renew.
        listed = _settled(tui, _submit(tui, "ledger.rule.list", LedgerRuleListRequest(profile_id=runtime.profile_id)))
        assert listed.effect is OperationEffect.NONE
        assert _expiry_after_last_request(runtime, tui) == signed_in
        # Nor does a change that saves nothing.
        refused = _settled(tui, _submit(tui, "ledger.rule.add", _rule(tui, "   ")))
        assert refused.effect is OperationEffect.NONE
        assert _expiry_after_last_request(runtime, tui) == signed_in

        saved = _settled(tui, _submit(tui, "ledger.rule.add", _rule(tui, "^office")))
        assert saved.effect is OperationEffect.UPDATED
        renewed = _expiry_after_last_request(runtime, tui)
        assert renewed > signed_in
        assert renewed >= runtime.clock() + idle_window - timedelta(seconds=30)
        # The stored sign-in follows, so a later command resumes past the original idle deadline.
        assert runtime.sign_in(runtime.connect()).idle_deadline == renewed
        # Observing the settled change again renews nothing more.
        runtime.clock.ahead += timedelta(minutes=1)
        observed_again = tui.operation(
            OperationObserve(
                request_id=uuid4(),
                profile_id=runtime.profile_id,
                session_id=tui.session_id,
                observation=OperationObservationRequestV1(
                    operation_id=saved.operation_id, after_cursor=0, page_limit=32
                ),
            ),
            deadline=exchange_deadline(),
        )
        assert isinstance(observed_again, OperationObserved), observed_again
        assert _expiry_after_last_request(runtime, tui) == renewed


def test_an_unattended_script_or_attended_automation_change_does_not_renew(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        tui = _person(runtime, OperationFrontendProjection.TUI)
        cli = _person(runtime, OperationFrontendProjection.CLI)
        attended = FrontendClient(
            runtime.connect(),
            profile_id=runtime.profile_id,
            frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
            scope=AccessScope(
                operations=frozenset({"ledger.rule.add"}),
                actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT}),
                disclosures=frozenset(),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
        )
        # The person's frontend holds the profile's asks once it reads them.
        assert tui.attendance_inventory().candidates == ()
        pending = attended.request_attendance()
        assert isinstance(pending, AttendancePending), pending
        assert tui.decide_attendance(pending.attendance_id, approve=True).approved
        admitted = attended.attendance_status(pending.attendance_id)
        assert isinstance(admitted, ProfileStatus) and admitted.status.denial is None, admitted
        saved_changes = Event()
        tui.subscribe_profile_record_changes(saved_changes.set)
        signed_in = runtime.lease(tui.session_id).expires_at
        # Far enough that renewal would show, inside the attended session's own bounded lifetime.
        runtime.clock.ahead += timedelta(minutes=1)

        # A script resumes the sign-in without reporting the person's input, so its saved change is no one's input.
        assert _settled(cli, _submit(cli, "ledger.rule.add", _rule(cli, "^cli"))).effect is OperationEffect.UPDATED
        assert _expiry_after_last_request(runtime, cli) == signed_in
        assert _expiry_after_last_request(runtime, tui) == signed_in
        # Nor is a change on the person's own frontend before that connection has reported any input.
        assert _settled(tui, _submit(tui, "ledger.rule.add", _rule(tui, "^tui"))).effect is OperationEffect.UPDATED
        assert _expiry_after_last_request(runtime, tui) == signed_in

        # An automation's change, though the person let it follow their sign-in, is not the person's input.
        saved_changes.clear()
        _start(attended, _submit(attended, "ledger.rule.add", _rule(attended, "^agent")))
        assert saved_changes.wait(HANG_GUARD_SECONDS), "the attended client's change never saved"
        assert _expiry_after_last_request(runtime, tui) == signed_in


def test_an_idle_expired_session_refuses_a_change_and_stays_ended(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        connection = runtime.connect()
        admitted = runtime.resume(connection, OperationFrontendProjection.TUI)
        assert isinstance(admitted, ProfileStatus) and admitted.status.session_id is not None, admitted
        session_id = admitted.status.session_id
        ended: list[SessionEvent] = []
        retired = Event()

        def observe(event: ConnectionEvent) -> None:
            if isinstance(event, SessionEvent):
                ended.append(event)
                retired.set()

        connection.subscribe_session_events(observe)
        runtime.clock.ahead += runtime.lease(session_id).expires_at - runtime.clock() + timedelta(seconds=1)

        # A change submitted after the idle deadline is refused and revives nothing.
        refused = connection.operation(
            OperationSubmit(
                request_id=uuid4(),
                profile_id=runtime.profile_id,
                session_id=session_id,
                definition_id="ledger.rule.add",
                subject_ref=profile_operation_subject(str(runtime.profile_id)),
                payload_json=LedgerRuleAddRequest(
                    profile_id=runtime.profile_id,
                    description_pattern="^late",
                    classification=BusinessClassification.BUSINESS,
                    category_id="material_oficina",
                ).model_dump_json(),
            ),
            deadline=exchange_deadline(),
        )
        assert isinstance(refused, AccessRefusal), refused
        assert retired.wait(5), "the expired session was not retired"
        assert [(event.session_id, event.reason) for event in ended] == [(session_id, AccessDenialCode.SESSION_EXPIRED)]
        assert session_id not in {lease.session_id for lease in runtime.leases()}
        activity = runtime.session(connection, session_id, "session_activity")
        assert not (isinstance(activity, ProfileStatus) and activity.status.denial is None), activity
        assert not runtime.leases()
        assert runtime.sign_in(runtime.connect()).presence is SignInPresence.ABSENT
