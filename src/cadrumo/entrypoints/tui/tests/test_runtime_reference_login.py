"""Stored-reference TUI admission reaches only the native restricted API shell."""

from __future__ import annotations

import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import cast
from uuid import UUID, uuid4

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, Select, Static

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLoginContext,
    SessionKind,
)
from cadrumo.application.user_profile.login_interaction import ProfileLoginChoice
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.tui.runtime_admission import runtime_login_session
from cadrumo.entrypoints.tui.runtime_session import RuntimeRestrictedSessionApp
from cadrumo.entrypoints.tui.secret.runtime_login import RuntimeLoginScreen
from cadrumo.entrypoints.tui.secret.runtime_login_contracts import RuntimeLoginMethod

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows runtime workers and pipes"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "tui-reference-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _connect(endpoint: WindowsRuntimeEndpoint) -> VerifiedRuntimeConnection:
    return VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def test_stored_reference_enters_restricted_shell_without_human_fallback(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        request_id = uuid4()
        subject.service.request(request_id, subject.proposal)
        approved = subject.approve(request_id)
        assert approved.credential_reference is not None
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        opened_plain: list[UUID] = []
        opened_references: list[tuple[UUID, UUID]] = []

        async def open_plain(selected: UUID) -> RuntimeFrontendClient:
            opened_plain.append(selected)
            raise AssertionError("reference login must never open a password/API-key form client")

        async def open_reference(selected: UUID, reference: UUID) -> RuntimeFrontendClient:
            opened_references.append((selected, reference))
            return await open_installed_credential_client(
                profile_id=selected,
                credential_reference=reference,
                frontend=OperationFrontendProjection.TUI,
                secrets_store=subject.client_native,
            )

        async def drive_success(pilot: Pilot[object]) -> None:
            screen = pilot.app.screen
            assert isinstance(screen, RuntimeLoginScreen)
            selected = cast("Select[RuntimeLoginMethod]", screen.query_one("#runtime-login-method", Select))
            selected.value = RuntimeLoginMethod.API_REFERENCE
            await pilot.pause()
            credential = screen.query_one("#runtime-login-credential", Input)
            reference = screen.query_one("#runtime-login-reference", Input)
            assert credential.password and credential.value == "" and not credential.display
            assert reference.display
            reference.value = str(approved.credential_reference)
            await pilot.click("#runtime-login-submit")
            assert reference.value == "" and credential.value == ""

        async def drive_restricted(pilot: Pilot[object]) -> None:
            app = pilot.app
            assert isinstance(app, RuntimeRestrictedSessionApp)
            async with asyncio.timeout(15):
                while str(profile_id) not in str(app.query_one("#restricted-profile", Static).render()):
                    await pilot.pause(0.05)
            assert not hasattr(app, "services")
            await pilot.click("#restricted-close")

        async def drive_refusals(pilot: Pilot[object]) -> None:
            screen = pilot.app.screen
            assert isinstance(screen, RuntimeLoginScreen)
            selected = cast("Select[RuntimeLoginMethod]", screen.query_one("#runtime-login-method", Select))
            selected.value = RuntimeLoginMethod.API_REFERENCE
            await pilot.pause()
            reference = screen.query_one("#runtime-login-reference", Input)
            credential = screen.query_one("#runtime-login-credential", Input)
            reference.value = "not-a-uuid"
            await pilot.click("#runtime-login-submit")
            assert reference.value == "" and credential.value == ""
            assert opened_references == [(profile_id, approved.credential_reference)]
            subject.client_native.unavailable = True
            try:
                reference.value = str(approved.credential_reference)
                screen.action_submit()
                assert reference.value == ""
                async with asyncio.timeout(15):
                    while screen._busy:
                        await pilot.pause(0.05)
                assert reference.value == "" and credential.value == ""
                assert opened_references == [
                    (profile_id, approved.credential_reference),
                    (profile_id, approved.credential_reference),
                ]
            finally:
                subject.client_native.unavailable = False
            screen.action_abandon()

        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                observer = RuntimeFrontendClient(
                    _connect(endpoint), profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                )
                try:
                    observer.login_password(bytearray(PROFILE_INPUT.encode()), timeout=25)

                    async def exercise() -> None:
                        choices = (ProfileLoginChoice(profile_id=str(profile_id), label="Enrollment tests"),)
                        async with runtime_login_session(
                            choices=choices,
                            open_client=open_plain,
                            open_credential_client=open_reference,
                            headless=True,
                            auto_pilot=drive_success,
                        ) as handoff:
                            assert handoff is not None
                            assert handoff.method is RuntimeLoginMethod.API_REFERENCE
                            assert handoff.client.profile_id == profile_id
                            assert handoff.status.status.grant_valid
                            sessions = await asyncio.to_thread(observer.sessions)
                            api = tuple(item for item in sessions if item.session_id == handoff.client.session_id)
                            assert len(api) == 1 and api[0].kind is SessionKind.API_KEY
                            await RuntimeRestrictedSessionApp(
                                handoff.client, profile_label=handoff.profile_label
                            ).run_async(headless=True, auto_pilot=drive_restricted)
                        async with runtime_login_session(
                            choices=choices,
                            open_client=open_plain,
                            open_credential_client=open_reference,
                            headless=True,
                            auto_pilot=drive_refusals,
                        ) as denied:
                            assert denied is None

                    asyncio.run(exercise())
                    assert opened_plain == []
                    deadline = time.monotonic() + 5
                    while True:
                        remaining = {item.session_id for item in observer.sessions()}
                        if remaining == {observer.session_id} or time.monotonic() >= deadline:
                            break
                        time.sleep(0.02)
                    assert remaining == {observer.session_id}
                finally:
                    observer.close()
            finally:
                stop.set()
                running.result(timeout=20)
                endpoint.close()
