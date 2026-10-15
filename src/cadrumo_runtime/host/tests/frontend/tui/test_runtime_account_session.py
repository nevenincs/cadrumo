"""The root's account watch uses one non-touching asynchronous session door."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast, override
from uuid import uuid4

import pytest

from cadrumo.application.overview.home import HomeAccountSession, HomeSessionPosture
from cadrumo.entrypoints.tui.account import (
    AccountDirectSessionActionV1,
    AccountRecomposeReasonV1,
    AccountRecomposeRequiredV1,
    AccountSessionExpiredError,
    AccountSessionUnavailableError,
)
from cadrumo.entrypoints.tui.app import CadrumoTuiApp
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....frontend.tui.runtime_account_session import runtime_account_session_reader

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _StatusClient:
    def __init__(self) -> None:
        self.profile_id = uuid4()
        self.session_id = uuid4()
        self.expires_at = datetime.now(UTC) + timedelta(minutes=10)
        self.calls = 0
        self.status_thread: int | None = None
        self.status_session_id = self.session_id

    def status(self) -> SimpleNamespace:
        self.calls += 1
        self.status_thread = threading.get_ident()
        return SimpleNamespace(
            status=SimpleNamespace(
                connected=True,
                credential_authenticated=True,
                profile_bound=True,
                profile_id=self.profile_id,
                session_id=self.status_session_id,
                session_expires_at=self.expires_at,
                denial=None,
            )
        )


@pytest.mark.asyncio
async def test_runtime_reader_checks_exact_session_off_ui_loop_without_touching_it() -> None:
    client = _StatusClient()
    reader = runtime_account_session_reader(
        cast(FrontendClient, client), profile_id=client.profile_id, profile_label="Current profile"
    )
    loop_thread = threading.get_ident()

    observed = await reader()

    assert observed == HomeAccountSession(
        posture=HomeSessionPosture.ACTIVE, profile_label="Current profile", expires_at=client.expires_at
    )
    assert client.calls == 1
    assert client.status_thread != loop_thread

    client.status_session_id = uuid4()
    with pytest.raises(AccountSessionExpiredError):
        await reader()

    client.status_session_id = client.session_id
    client.session_id = uuid4()
    with pytest.raises(AccountSessionExpiredError):
        await reader()
    assert client.calls == 2

    client.session_id = client.status_session_id
    client.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(AccountSessionExpiredError):
        await reader()


@pytest.mark.asyncio
async def test_account_watch_coalesces_polls_and_discards_late_result_after_severance() -> None:
    started = asyncio.Event()
    finish = asyncio.Event()
    calls = 0
    initial_expiry = datetime.now(UTC) + timedelta(minutes=10)
    initial = HomeAccountSession(
        posture=HomeSessionPosture.ACTIVE,
        profile_label="Current profile",
        expires_at=initial_expiry,
    )

    async def read() -> HomeAccountSession:
        nonlocal calls
        calls += 1
        started.set()
        await finish.wait()
        return initial.model_copy(update={"expires_at": initial_expiry + timedelta(minutes=1)})

    app = CadrumoTuiApp(
        read_account_session=read,
    )
    async with app.run_test() as pilot:
        app._account_session = initial
        app._watch_account_session()
        await started.wait()
        app._watch_account_session()
        assert calls == 1

        app._read_account_session = None
        finish.set()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.account_session == initial


@pytest.mark.asyncio
async def test_runtime_reader_preserves_unavailable_transport_as_distinct_from_expiry() -> None:
    class UnavailableClient(_StatusClient):
        @override
        def status(self) -> SimpleNamespace:
            raise FrontendRefusedError("runtime_connection_closed")

    client = UnavailableClient()
    reader = runtime_account_session_reader(
        cast(FrontendClient, client), profile_id=client.profile_id, profile_label="Current profile"
    )
    with pytest.raises(AccountSessionUnavailableError):
        await reader()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (OSError("connection closed"), AccountRecomposeReasonV1.UNAVAILABLE),
        (AccountSessionUnavailableError(), AccountRecomposeReasonV1.UNAVAILABLE),
        (AccountSessionExpiredError(), AccountRecomposeReasonV1.EXPIRED),
    ],
)
async def test_account_watch_clears_private_state_without_claiming_unobserved_expiry(
    failure: Exception, reason: AccountRecomposeReasonV1
) -> None:
    async def read() -> HomeAccountSession:
        raise failure

    app = CadrumoTuiApp(read_account_session=read)
    async with app.run_test() as pilot:
        app._account_session = HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE,
            profile_label="Current profile",
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        app._watch_account_session()
        await pilot.pause()
        assert app.return_value is not None and app.return_value.reason is reason
        assert app.account_session is None
        assert app._read_account_session is None


@pytest.mark.asyncio
async def test_person_input_reports_activity_once_while_polls_do_not() -> None:
    calls = 0

    async def note() -> None:
        nonlocal calls
        calls += 1

    app = CadrumoTuiApp(note_activity=note)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert calls == 0
        await pilot.press("a", "b")
        await pilot.pause()
        assert calls == 1
        app._last_activity_sent = None
        await pilot.press("c")
        await pilot.pause()
        assert calls == 2
        app._sever_profile_root()
        app._last_activity_sent = None
        await pilot.press("d")
        assert calls == 2


@pytest.mark.asyncio
async def test_activity_transport_failure_is_a_recoverable_handoff() -> None:
    async def note() -> None:
        raise OSError("connection closed")

    app = CadrumoTuiApp(note_activity=note)
    async with app.run_test() as pilot:
        await pilot.press("a")
        await pilot.pause()
        assert app.return_value is not None
        assert app.return_value.reason is AccountRecomposeReasonV1.UNAVAILABLE
        assert app._note_activity is None


@pytest.mark.asyncio
async def test_queued_retirement_does_not_overtake_logout_completion() -> None:
    started = asyncio.Event()
    finish = asyncio.Event()

    async def complete() -> AccountRecomposeRequiredV1:
        started.set()
        await finish.wait()
        return AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.SIGNED_OUT)

    app = CadrumoTuiApp()
    async with app.run_test() as pilot:
        app._start_direct_session_action(
            AccountDirectSessionActionV1(complete=complete), expected=AccountRecomposeReasonV1.SIGNED_OUT
        )
        await started.wait()
        app._post_session_retired()
        await pilot.pause()
        assert app.is_running and app.return_value is None
        finish.set()
        await pilot.pause()
        assert app.return_value is not None
        assert app.return_value.reason is AccountRecomposeReasonV1.SIGNED_OUT
