"""The installed account password action settles through a real native worker."""

from __future__ import annotations

import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, Select

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalError
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from cadrumo.core.config import override_settings
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.tui.account import AccountRecomposeReasonV1, AccountRecomposeRequiredV1
from cadrumo.entrypoints.tui.app import CadrumoTuiApp
from cadrumo.entrypoints.tui.components.account_chrome import AccountActionV1
from cadrumo.entrypoints.tui.launcher import main
from cadrumo.entrypoints.tui.secret.passphrase import PassphraseScreen
from cadrumo.entrypoints.tui.secret.runtime_login import RuntimeLoginScreen
from cadrumo.entrypoints.tui.secret.runtime_login_contracts import RuntimeLoginMethod

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_REPLACEMENT = "s16-new-native-tui-passphrase-do-not-print"


class _LoginObservation:
    login_id = "tui-password-rotation-native-login"

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


def _require_runtime_app(value: object) -> CadrumoTuiApp:
    assert isinstance(value, CadrumoTuiApp)
    return value


def test_installed_account_password_change_retires_old_lease_and_reauthenticates(tmp_path: Path) -> None:
    """The mounted account screen rotates custody, then a fresh password reads it."""
    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
    installation = runtime_installation(
        storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
        subject.owner.requesting = requester
        subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
            requester=requester, secrets_store=subject.client_native
        )
        enrollment_request = uuid4()
        subject.service.request(enrollment_request, subject.proposal)
        subject.approve(enrollment_request)
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()

        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=storage_root,
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
        stages: list[str] = []

        async def drive(pilot: Pilot[object]) -> None:
            app: object = pilot.app
            if not isinstance(app, CadrumoTuiApp):
                screen = pilot.app.screen
                assert isinstance(screen, RuntimeLoginScreen)
                method = screen.query_one("#runtime-login-method", Select)
                method.value = RuntimeLoginMethod.PASSWORD
                await pilot.pause()
                credential = screen.query_one("#runtime-login-credential", Input)
                assert credential.password
                credential.value = PROFILE_INPUT if not stages else _REPLACEMENT
                stages.append("login-original" if not stages else "login-replacement")
                await pilot.click("#runtime-login-submit")
                assert credential.value == ""
                return

            root_app = _require_runtime_app(pilot.app)
            async with asyncio.timeout(90):
                while root_app.account_session is None:
                    await pilot.pause(0.05)
            assert root_app.account_session.profile_label == "Enrollment tests"
            if "password-changed" in stages:
                stages.append("fresh-root")
                root_app.exit()
                return

            assert stages == ["login-original"]
            root_app.run_account_action(AccountActionV1.PASSWORD)
            await pilot.pause()
            screen = root_app.screen
            assert isinstance(screen, PassphraseScreen)
            fields = tuple(screen.query(Input))
            assert len(fields) == 3 and all(field.password for field in fields)
            screen.query_one("#field-current", Input).value = PROFILE_INPUT
            screen.query_one("#field-new", Input).value = _REPLACEMENT
            screen.query_one("#field-confirm", Input).value = _REPLACEMENT
            screen.action_change()
            assert all(field.value == "" for field in fields)
            root_app._watch_account_session()
            async with asyncio.timeout(90):
                while root_app.return_value is None:
                    await pilot.pause(0.05)
            assert root_app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.PASSWORD_CHANGED)
            stages.append("password-changed")

        with override_settings(cadrumo_local_storage_root=storage_root), ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with ExitStack() as cleanup:
                    old = RuntimeFrontendClient(
                        _connect(endpoint), profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                    )
                    cleanup.callback(old.close)
                    old_proof = bytearray(PROFILE_INPUT.encode())
                    old.login_password(old_proof, timeout=25)
                    assert not any(old_proof)
                    old_session = old.session_id

                    assert main(headless=True, auto_pilot=drive) == 0
                    assert stages == [
                        "login-original",
                        "password-changed",
                        "login-replacement",
                        "fresh-root",
                    ]
                    with pytest.raises((RuntimeFrontendRefusedError, RuntimeRefusalError)):
                        old.status()

                    fresh = RuntimeFrontendClient(
                        _connect(endpoint), profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                    )
                    cleanup.callback(fresh.close)
                    fresh_proof = bytearray(_REPLACEMENT.encode())
                    status = fresh.login_password(fresh_proof, timeout=25)
                    assert not any(fresh_proof)
                    assert status.status.session_id == fresh.session_id != old_session
                    assert fresh.status().status.session_id == fresh.session_id
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    try:
                        running.result(timeout=20)
                    except Exception:
                        if primary is None:
                            raise
                finally:
                    endpoint.close()
