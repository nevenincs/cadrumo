"""Full-screen login behavior for a restore-fed profile.

Two routes the earlier Pilot suite left uncodified: a profile that reaches
the machine through the capsule restore door (rather than registration)
must present on the login screen and unlock through the real door.

Real registration, restore, Argon2id and native profile workers, with explicit
synthetic OS-login/custody controls. RuntimeLoginScreen runs through Textual's
headless Pilot and hands off a live, admitted exact-profile connection.
"""

from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import AsyncExitStack, ExitStack
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from textual.app import App
from textual.widgets import Button, Input

from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.adapters.persistence.storage.tests.profile_session_setup import reset_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.capsule_restore import (
    read_profile_capsule_source,
    restore_profile_capsule_with_password,
)
from cadrumo.application.user_profile.login_interaction import profile_login_choices
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo_client.transport.posix_endpoint import PosixEndpoint
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_runtime.adapters.tests.profile_worker_support import owner_id
from cadrumo_runtime.adapters.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo.entrypoints.tui.secret.runtime_login import RuntimeLoginScreen
from cadrumo.entrypoints.tui.secret.runtime_login_contracts import (
    RuntimeLoginHandoff,
    RuntimeLoginMethod,
)
from cadrumo_runtime.host.profile_connections import RuntimeProfileConnections
from cadrumo_runtime.host.tests.test_profile_connections import LoginObservation

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.skipif(
        sys.platform not in {"win32", "linux"}, reason="native private workers support Windows and Linux"
    ),
]

_TERMINAL_SIZE = (140, 60)
_CREDENTIAL_INPUT = "login-restored-operator-secret"


class _RestoredLoginApp(App[None]):
    """Observe the screen's completed handoff independently of its worker lifetime."""

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


@pytest.mark.asyncio
async def test_a_restored_profile_presents_and_unlocks_on_the_login_screen(
    tmp_path: Path,
) -> None:
    """A profile that arrives by restore (not registration) is a login citizen."""

    with isolated_profile_storage_root(tmp_path=tmp_path / "source-root") as source_root:
        # Registration validates facts against registry authority, so it runs under a real lease.
        with bundled_indexed_authority().operation():
            profile_create_context, profile_decode_context = _profile_contexts_for_test()
            outcome = register_profile_with_credentials(
                label="Restore-born",
                passphrase=_CREDENTIAL_INPUT,
                profile_create_context=profile_create_context,
                profile_decode_context=profile_decode_context,
            )
        capsule = source_root / "buckets" / outcome.profile_id
        restored = restore_profile_capsule_with_password(
            label="Restore-born",
            capsule=read_profile_capsule_source(capsule),
            password=_CREDENTIAL_INPUT,
            root=tmp_path / "tui-root",
            profile_decode_context=profile_decode_context,
        )
        assert restored.profile_id == outcome.profile_id

    root = tmp_path / "tui-root"
    assert (root / "buckets" / restored.profile_id).is_dir()
    with override_settings(cadrumo_local_storage_root=str(root), cadrumo_output_language="en"):
        choices = list(profile_login_choices())
        assert any(choice.profile_id == restored.profile_id for choice in choices)
        reset_test_profile_session()
        profile_id = UUID(restored.profile_id)
        with ExitStack() as runtime_resources:
            endpoint = (
                WindowsEndpoint(storage_root=root) if sys.platform == "win32" else PosixEndpoint(storage_root=root)
            )
            runtime_resources.callback(endpoint.close)
            installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
            stop, boot, native = Event(), uuid4(), MemoryNativePort()
            profiles = RuntimeProfileConnections(
                storage_root=root,
                storage_identity=endpoint.storage_identity,
                runtime_boot_id=boot,
                stop=stop,
                capture_login=lambda _channel: LoginObservation(owner_id()),
                secret_store=lambda: native,
            )
            profiles.prepare_registry()
            server = RetainedRuntimeTransportServer(
                endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
            )
            with ThreadPoolExecutor(max_workers=1) as pool:
                running = pool.submit(server.serve)
                try:
                    assert await asyncio.to_thread(server.ready.wait, 3)
                    async with AsyncExitStack() as clients:
                        opened: list[FrontendClient] = []
                        accepted: list[RuntimeLoginHandoff] = []

                        async def open_client(selected: UUID) -> FrontendClient:
                            assert selected == profile_id
                            client = await open_installed_client(
                                profile_id=selected, frontend=OperationFrontendProjection.TUI
                            )
                            await clients.enter_async_context(client)
                            opened.append(client)
                            return client

                        def accept_handoff(handoff: RuntimeLoginHandoff) -> bool:
                            assert not accepted
                            accepted.append(handoff)
                            return True

                        screen = RuntimeLoginScreen(
                            choices=choices,
                            open_client=open_client,
                            accept_handoff=accept_handoff,
                            preselected=restored.profile_id,
                        )
                        app = _RestoredLoginApp(screen)
                        async with app.run_test(size=_TERMINAL_SIZE) as pilot:
                            await pilot.pause()
                            submit = screen.query_one("#runtime-login-submit", Button)
                            async with asyncio.timeout(30):
                                while submit.disabled:
                                    await pilot.pause(0.05)
                            credential = screen.query_one("#runtime-login-credential", Input)
                            assert credential.password
                            credential.value = _CREDENTIAL_INPUT
                            submit.scroll_visible(animate=False)
                            await pilot.pause()
                            assert await pilot.click("#runtime-login-submit")
                            async with asyncio.timeout(30):
                                await app.handoff_received.wait()
                            # The preselected profile first attempts receipt
                            # admission, then opens a fresh password connection.
                            assert len(opened) == 2 and len(accepted) == 1
                            with pytest.raises(FrontendRefusedError) as refused:
                                _ = opened[0].session_id
                            assert refused.value.reason == "authentication_required"
                            handoff = accepted[0]
                            assert app.handoff is handoff and handoff.client is opened[1]
                            assert handoff.method is RuntimeLoginMethod.PASSWORD
                            assert handoff.profile_id == profile_id
                            assert handoff.profile_label == "Restore-born"
                            assert handoff.client.frontend is OperationFrontendProjection.TUI
                            assert handoff.status.status.profile_id == profile_id
                            assert handoff.status.status.profile_bound
                            assert handoff.status.status.credential_authenticated
                            assert handoff.status.status.denial is None
                            assert handoff.client.session_id == handoff.status.status.session_id
                            assert credential.value == ""
                            current = await asyncio.to_thread(handoff.client.status)
                            assert current.status.denial is None
                            assert current.status.profile_id == profile_id
                            assert current.status.session_id == handoff.client.session_id
                finally:
                    primary = sys.exception()
                    stop.set()
                    try:
                        await await_cancellation_complete(
                            asyncio.to_thread(running.result, timeout=20), task_name="restored-login-runtime-drain"
                        )
                    except Exception as cleanup_error:
                        if primary is None:
                            raise
                        primary.add_note(
                            f"Native restored-login runtime cleanup failed ({type(cleanup_error).__name__})"
                        )
