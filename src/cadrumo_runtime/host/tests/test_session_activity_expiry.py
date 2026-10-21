"""Runtime activity keeps shared human sessions alive; idle expiry pushes sign-out."""

from __future__ import annotations

import sys
import time
from datetime import timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.contracts.session_events import ConnectionEvent, SessionEvent, SignInChanged
from cadrumo_client.contracts.sign_in import SignInPresence, SignInStatusRequest

from .stored_sign_in_runtime import stored_sign_in_runtime

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
        original = runtime.lease(clients[0][1])
        idle_window = original.expires_at - original.issued_at
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
