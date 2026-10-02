"""The root's account watch uses one non-touching asynchronous session door."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.overview.home import HomeAccountSession, HomeSessionPosture
from ..account import AccountSessionExpiredError
from ..app import CadrumoTuiApp
from ..runtime_account_session import runtime_account_session_reader

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
        cast(RuntimeFrontendClient, client), profile_id=client.profile_id, profile_label="Current profile"
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
