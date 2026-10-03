"""Installed TUI decisions settle through the real native profile runtime."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Select, Static

from cadrumo.adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.automation_store import CLIENT_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.runtime.enrollment_access import RuntimeEnrollmentPrepare, RuntimeEnrollmentPrepared
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from cadrumo.application.user_profile.automation_enrollment import EnrollmentStage
from cadrumo.core.config import override_settings
from cadrumo.core.operations import OperationEffect
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.tui.app import CadrumoTuiApp
from cadrumo.entrypoints.tui.components.account_chrome import AccountActionV1
from cadrumo.entrypoints.tui.launcher import main
from cadrumo.entrypoints.tui.profile.automation_inventory import RuntimeAutomationInventoryScreen
from cadrumo.entrypoints.tui.runtime_access_management import RuntimeAccessManagementScreen
from cadrumo.entrypoints.tui.secret.automation_decision import RuntimeAutomationDecisionScreen
from cadrumo.entrypoints.tui.secret.runtime_login import RuntimeLoginMethod, RuntimeLoginScreen

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "tui-automation-decision-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _requester(
    endpoint: WindowsRuntimeEndpoint, profile_id: UUID, native_store: MemoryNativePort
) -> tuple[VerifiedRuntimeConnection, NativeEnrollmentClient]:
    connection = VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )
    prepared = connection.enrollment_prepare(
        RuntimeEnrollmentPrepare(request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.MCP),
        deadline=time.monotonic() + 5,
    )
    assert isinstance(prepared, RuntimeEnrollmentPrepared)
    return connection, NativeEnrollmentClient(connection=connection, prepared=prepared, secrets_store=native_store)


async def _until(pilot: Pilot[object], predicate: Callable[[], bool], *, timeout: float = 90) -> None:
    """Advance the headless app until one real UI transition is observable."""
    async with asyncio.timeout(timeout):
        while not predicate():
            await pilot.pause(0.05)


def _request_row(table: DataTable[str], request_id: UUID) -> int:
    for index in range(table.row_count):
        if str(table.get_row_at(index)[0]) == str(request_id):
            return index
    raise AssertionError(f"review {request_id} is absent from the runtime inventory")


def test_installed_tui_approves_and_declines_exact_review_with_protected_requester(tmp_path: Path) -> None:
    """Masked consent controls publish only safe receipts; requester gets its key."""
    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
    installation = runtime_installation(
        storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()
        delete_profile_session(storage_root=storage_root, profile_id=profile_id)
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=storage_root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        server = RuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        stages: list[str] = []
        done = Event()
        polling: Future[None] | None = None

        def poll_requester(enrollment: NativeEnrollmentClient) -> None:
            deadline = time.monotonic() + 75
            while not done.is_set() and time.monotonic() < deadline:
                enrollment.poll(timeout=10)

        with override_settings(cadrumo_local_storage_root=storage_root), ThreadPoolExecutor(max_workers=3) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with ExitStack() as cleanup:
                    requester, enrollment = _requester(endpoint, profile_id, subject.client_native)
                    cleanup.callback(requester.close)
                    first = enrollment.submit(subject.proposal)
                    assert first.stage is EnrollmentStage.REQUESTED
                    second_requester, second_enrollment = _requester(endpoint, profile_id, MemoryNativePort())
                    cleanup.callback(second_requester.close)
                    second = second_enrollment.submit(subject.proposal)
                    assert second.stage is EnrollmentStage.REQUESTED

                    async def drive(pilot: Pilot[object]) -> None:
                        nonlocal polling
                        if not isinstance(pilot.app, CadrumoTuiApp):
                            screen = pilot.app.screen
                            assert isinstance(screen, RuntimeLoginScreen)
                            screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.PASSWORD
                            await pilot.pause()
                            credential = screen.query_one("#runtime-login-credential", Input)
                            assert credential.password
                            credential.value = PROFILE_INPUT
                            await pilot.click("#runtime-login-submit")
                            assert credential.value == ""
                            stages.append("human-login")
                            return

                        app = pilot.app
                        await _until(pilot, lambda: app.account_session is not None)
                        assert app.account_session is not None
                        assert app.account_session.profile_label == "Enrollment tests"
                        app.run_account_action(AccountActionV1.ACCESS)
                        await _until(pilot, lambda: isinstance(app.screen, RuntimeAccessManagementScreen))
                        access = app.screen
                        assert isinstance(access, RuntimeAccessManagementScreen)
                        for _ in range(100):
                            if (
                                access._admin_available
                                and not access._busy
                                and not access.query_one("#runtime-access-view-automation", Button).disabled
                            ):
                                break
                            await pilot.pause(0.05)
                        assert access._admin_available and not access._busy, (
                            type(app.screen).__name__,
                            access._screen_live,
                            access.is_mounted,
                            access._busy,
                            access.access_lost,
                            str(access.query_one("#runtime-access-status", Static).content),
                            str(access.query_one("#runtime-access-sessions", Static).content),
                            app.return_value,
                        )
                        access.query_one("#runtime-access-view-automation", Button).press()
                        for _ in range(100):
                            if isinstance(app.screen, RuntimeAutomationInventoryScreen):
                                break
                            await pilot.pause(0.05)
                        assert isinstance(app.screen, RuntimeAutomationInventoryScreen), (
                            type(app.screen).__name__,
                            access._busy,
                            access._admin_available,
                            access.access_lost,
                            str(access.query_one("#runtime-access-status", Static).content),
                            app.return_value,
                        )
                        inventory = app.screen
                        assert isinstance(inventory, RuntimeAutomationInventoryScreen)
                        table = inventory.query_one("#automation-inventory-requests", DataTable)
                        await _until(pilot, lambda: table.row_count == 2)
                        table.focus()
                        table.move_cursor(row=_request_row(table, first.request_id))
                        await _until(
                            pilot,
                            lambda: (
                                inventory._selected_review is not None
                                and inventory._selected_review.receipt.request_id == first.request_id
                            ),
                            timeout=5,
                        )
                        await _until(
                            pilot, lambda: not inventory.query_one("#automation-inventory-approve", Button).disabled
                        )
                        inventory.query_one("#automation-inventory-approve", Button).press()
                        await _until(pilot, lambda: isinstance(app.screen, RuntimeAutomationDecisionScreen))
                        approval = app.screen
                        assert isinstance(approval, RuntimeAutomationDecisionScreen)
                        consent = str(approval.query_one("#automation-decision-review", Static).content)
                        assert str(first.request_id) in consent and first.review_digest in consent
                        assert PROFILE_INPUT not in consent
                        field = approval.query_one("#automation-decision-password", Input)
                        assert field.password
                        field.value = PROFILE_INPUT
                        polling = pool.submit(poll_requester, enrollment)
                        approval.query_one("#automation-decision-confirm", Button).press()
                        await _until(pilot, lambda: field.value == "", timeout=5)
                        await _until(
                            pilot,
                            lambda: approval._outcome is not None and not approval._busy,
                        )
                        assert approval._outcome is not None and approval._outcome.completed, approval._outcome
                        assert approval._outcome.effect is OperationEffect.UPDATED
                        assert approval._pending_proof is None
                        assert PROFILE_INPUT not in repr(approval._outcome)
                        assert PROFILE_INPUT not in str(
                            approval.query_one("#automation-decision-status", Static).content
                        )
                        approval.action_close()
                        await _until(pilot, lambda: app.screen is inventory)
                        assert approval._outcome is not None and approval._outcome.operation_id is not None
                        stages.append("approved")
                        done.set()
                        if polling is not None:
                            await asyncio.to_thread(polling.result, 15)

                        inventory.query_one("#automation-inventory-refresh", Button).press()
                        await _until(pilot, lambda: table.row_count == 2)
                        table.focus()
                        table.move_cursor(row=_request_row(table, second.request_id))
                        await _until(
                            pilot,
                            lambda: (
                                inventory._selected_review is not None
                                and inventory._selected_review.receipt.request_id == second.request_id
                            ),
                            timeout=5,
                        )
                        await _until(
                            pilot, lambda: not inventory.query_one("#automation-inventory-decline", Button).disabled
                        )
                        inventory.query_one("#automation-inventory-decline", Button).press()
                        await _until(pilot, lambda: isinstance(app.screen, RuntimeAutomationDecisionScreen))
                        decline = app.screen
                        assert isinstance(decline, RuntimeAutomationDecisionScreen)
                        assert str(second.request_id) in str(
                            decline.query_one("#automation-decision-review", Static).content
                        )
                        assert not tuple(decline.query("#automation-decision-password"))
                        decline.query_one("#automation-decision-confirm", Button).press()
                        await _until(
                            pilot,
                            lambda: decline._outcome is not None and not decline._busy,
                        )
                        assert decline._outcome is not None and decline._outcome.completed, decline._outcome
                        assert decline._outcome.effect is OperationEffect.UPDATED
                        decline.action_close()
                        await _until(pilot, lambda: app.screen is inventory)
                        stages.append("declined")
                        app.exit()

                    try:
                        assert main(headless=True, auto_pilot=drive) == 0
                    finally:
                        done.set()
                        if polling is not None:
                            polling.result(timeout=15)
                    assert stages == ["human-login", "approved", "declined"]
                    completed = enrollment.inspect()
                    rejected = second_enrollment.inspect()
                    assert completed is not None and completed.stage is EnrollmentStage.COMPLETE
                    assert rejected is not None and rejected.stage is EnrollmentStage.DECLINED
                    assert completed.request_id == first.request_id
                    assert rejected.request_id == second.request_id
                    assert completed.credential_reference is not None
                    assert (CLIENT_NAMESPACE, str(completed.credential_reference)) in subject.client_native.items
                    assert (CLIENT_NAMESPACE, str(completed.credential_reference)) not in subject.native.items
                    assert len(subject.store.snapshot().grants) == len(subject.store.snapshot().keys) == 1
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
