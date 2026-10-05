"""Cold TUI recovery over encrypted persistence and real native transport."""

from __future__ import annotations

import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from textual.app import App
from textual.widgets import Input

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import RuntimeSessionRequest
from cadrumo.application.user_profile.access_contracts import AuthorityState
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo.application.user_profile.login_interaction import ProfileLoginChoice
from cadrumo.core.config import override_settings
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.runtime.tests.test_profile_connections import LoginObservation

from .....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from ..runtime_login import RuntimeLoginScreen
from ..runtime_login_contracts import RuntimeLoginHandoff

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _ColdRecoveryApp(App[None]):
    """Present the real login screen and retain its accepted native handoff."""

    def __init__(self, screen: RuntimeLoginScreen) -> None:
        super().__init__()
        self.login_screen = screen
        self.handoff: RuntimeLoginHandoff | None = None
        self.handoff_received = asyncio.Event()

    async def _present(self) -> None:
        self.handoff = await self.push_screen_wait(self.login_screen)
        self.handoff_received.set()

    def on_mount(self) -> None:
        self.run_worker(self._present())


async def _cold_tui_recovery(
    profile_id: UUID, selected_grant: UUID, store: AutomationControlStore, resources: ExitStack
) -> None:
    """Drop the old TUI lease before recovery through a new, unadmitted screen."""
    with await open_installed_runtime_client(
        profile_id=profile_id, frontend=OperationFrontendProjection.TUI
    ) as previous:
        await asyncio.to_thread(previous.login_password, bytearray(PROFILE_INPUT.encode()), timeout=25)
        previous_session = previous.session_id
        locked = await asyncio.to_thread(previous.deny_automation, AutomationDenialKind.PROFILE_LOCK)
        assert locked.access_denied and store.profile_lock_state().globally_locked
    del previous
    assert {item.state for item in store.snapshot().grants} == {AuthorityState.SUSPENDED}
    opened: list[RuntimeFrontendClient] = []
    accepted: list[RuntimeLoginHandoff] = []

    async def open_client(selected: UUID) -> RuntimeFrontendClient:
        assert selected == profile_id
        client = await open_installed_runtime_client(profile_id=selected, frontend=OperationFrontendProjection.TUI)
        resources.callback(client.close)
        opened.append(client)
        return client

    def accept_handoff(handoff: RuntimeLoginHandoff) -> bool:
        assert not accepted
        accepted.append(handoff)
        return True

    screen = RuntimeLoginScreen(
        choices=(ProfileLoginChoice(profile_id=str(profile_id), label="Synthetic cold recovery profile"),),
        open_client=open_client,
        accept_handoff=accept_handoff,
    )
    app = _ColdRecoveryApp(screen)
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        password = screen.query_one("#runtime-login-resume-password", Input)
        grants = screen.query_one("#runtime-login-resume-grants", Input)
        assert password.password
        password.value, grants.value = PROFILE_INPUT, str(selected_grant)
        screen.action_resume()
        worker = screen._worker
        assert worker is not None
        async with asyncio.timeout(30):
            await worker.wait()
        assert password.value == grants.value == ""
        assert app.screen is screen and not screen._busy
        assert not accepted and app.handoff is None
        assert len(opened) == 1
        with pytest.raises(RuntimeFrontendRefusedError):
            _ = opened[0].session_id
        # Observe the actual retained transport owner: recovery must close its
        # unadmitted client rather than leave a reusable connection behind.
        with pytest.raises(RuntimeRefusalError) as closed:
            opened[0]._connection.session(
                RuntimeSessionRequest(
                    action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()
                ),
                deadline=time.monotonic() + 1,
            )
        assert closed.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
        assert not store.profile_lock_state().globally_locked
        active = {item.grant_id for item in store.snapshot().grants if item.state is AuthorityState.ACTIVE}
        assert active == {selected_grant}

        credential = screen.query_one("#runtime-login-credential", Input)
        credential.value = PROFILE_INPUT
        screen.action_submit()
        # Successful dismissal unmounts the screen and can cancel its worker.
        # The app's receipt proves the actual accepted native handoff instead.
        async with asyncio.timeout(30):
            await app.handoff_received.wait()
        await pilot.pause()
        assert len(opened) == 2 and len(accepted) == 1
        handoff = accepted[0]
        assert app.handoff is handoff and handoff.client is opened[1]
        assert handoff.profile_id == profile_id and handoff.client.frontend is OperationFrontendProjection.TUI
        assert handoff.status.status.denial is None and handoff.status.status.credential_authenticated
        assert handoff.client.session_id == handoff.status.status.session_id != previous_session
        current = await asyncio.to_thread(handoff.client.status)
        assert current.status.denial is None and current.status.session_id == handoff.client.session_id


def test_cold_tui_global_lock_recovery_reactivates_only_explicit_grant(tmp_path: Path) -> None:
    """Real encrypted custody and native IPC, with explicit login/store test controls."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        issued: list[tuple[UUID, bytes]] = []
        for _ in range(2):
            request_id = uuid4()
            subject.service.request(request_id, subject.proposal)
            receipt = subject.approve(request_id)
            record = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)
            key = subject.owner.delivery.endpoint.possession(record)
            assert key is not None
            issued.append((receipt.grant_id, key.get_secret_value()))
        (selected_grant, selected_secret), (held_grant, held_secret) = issued
        assert selected_grant != held_grant
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: LoginObservation(owner_id()),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with (
                    override_settings(cadrumo_local_storage_root=root, cadrumo_output_language="en"),
                    ExitStack() as clients,
                ):
                    asyncio.run(_cold_tui_recovery(profile_id, selected_grant, subject.store, clients))
                    selected = asyncio.run(
                        open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
                    )
                    clients.callback(selected.close)
                    selected.login_api_key(bytearray(selected_secret), timeout=25)
                    assert selected.status().status.denial is None
                    held = asyncio.run(
                        open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
                    )
                    clients.callback(held.close)
                    with pytest.raises(RuntimeFrontendRefusedError):
                        held.login_api_key(bytearray(held_secret), timeout=25)
                    assert {
                        item.grant_id
                        for item in subject.store.snapshot().grants
                        if item.state is AuthorityState.SUSPENDED
                    } == {held_grant}
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    running.result(timeout=20)
                except Exception:
                    if primary is None:
                        raise
                finally:
                    endpoint.close()
