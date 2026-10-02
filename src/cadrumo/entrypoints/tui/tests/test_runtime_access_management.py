"""The standalone access screen uses exact runtime doors and owns recovery proof."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Event
from typing import cast, override
from uuid import UUID, uuid4

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Input, Static

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.profile_access import RuntimeProfileStatus, RuntimeSessionsLocked
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    AuthorityState,
    Availability,
    ProfileAccessStatus,
    SessionKind,
    SessionState,
)
from ....application.user_profile.access_projections import PublicAccessSession
from ....application.user_profile.automation_custody_port import AutomationSecretStore
from ....application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from ....application.user_profile.automation_lifecycle_service import AutomationResumeReceipt
from ....application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from ....core.async_cleanup import AsyncResourceCleanupError
from ....core.i18n.render import tr
from ..components.host import ScreenHostApp
from ..runtime_access_management import RecoveryClientOpener, RuntimeAccessManagementScreen
from ..secret.automation_requester import RuntimeAutomationRequesterScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _RuntimeClient(RuntimeFrontendClient):
    """Explicit UI fault port; no native acceptance is claimed here."""

    def __init__(self, profile_id: UUID, *, admitted: bool) -> None:
        self._profile_id = profile_id
        self._frontend = OperationFrontendProjection.TUI
        self._session_id = uuid4() if admitted else None
        self.api_key = False
        self.denials: list[tuple[AutomationDenialKind, UUID | None]] = []
        self.selected_targets: list[UUID] = []
        self.selected_cascade: tuple[UUID, ...] = ()
        self.locked = False
        self.closed = False
        self.inventory: tuple[PublicAccessSession, ...] = (
            (_session(profile_id, self._session_id),) if self._session_id is not None else ()
        )
        self.proof_seen: bytes | None = None
        self.proof_buffer: bytearray | None = None
        self.wipe_in_port = True
        self.grants_seen: frozenset[UUID] | None = None
        self.proof_started = Event()
        self.release_proof = Event()
        self.release_proof.set()
        self.proof_failure: Exception | None = None
        self.proof_calls = 0
        self.recovery_outcome: AutomationResumeReceipt | None = None
        self.close_calls = 0
        self.close_failures_remaining = 0
        self.close_started = Event()
        self.release_close = Event()
        self.release_close.set()

    @override
    def sessions(self, *, timeout: float = 5) -> tuple[PublicAccessSession, ...]:
        return self.inventory

    @override
    def status(self, *, timeout: float = 5) -> RuntimeProfileStatus:
        session_id = self.session_id
        return RuntimeProfileStatus(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            status=ProfileAccessStatus(
                connected=True,
                credential_authenticated=True,
                profile_id=self.profile_id,
                session_id=session_id,
                session_expires_at=datetime.now(UTC) + timedelta(minutes=10),
                grant_state=AuthorityState.ACTIVE if self.api_key else None,
                grant_expires_at=datetime.now(UTC) + timedelta(minutes=10) if self.api_key else None,
                grant_valid=self.api_key,
                profile_bound=True,
                storage=Availability.AVAILABLE,
                automation_custody=Availability.AVAILABLE,
                published_authority=Availability.AVAILABLE,
                provider=Availability.NOT_REQUIRED,
                effective_scope=self.inventory[0].scope if self.inventory else _scope(),
                denial=None,
            ),
        )

    @override
    def deny_automation(
        self, kind: AutomationDenialKind, *, target_id: UUID | None = None, timeout: float = 10
    ) -> AutomationDenialReceipt:
        self.denials.append((kind, target_id))
        if kind is AutomationDenialKind.PROFILE_LOCK:
            self._session_id = None
        return AutomationDenialReceipt(
            request_id=uuid4(),
            profile_id=self.profile_id,
            access_denied=True,
            cleanup_pending=False,
            revision=2,
            profile_lock_generation=1 if kind is AutomationDenialKind.PROFILE_LOCK else None,
        )

    @override
    def lock(self, *, timeout: float = 5) -> RuntimeSessionsLocked:
        session_id = self.session_id
        self.locked = True
        self._session_id = None
        return RuntimeSessionsLocked(
            request_id=uuid4(), runtime_boot_id=uuid4(), connection_id=uuid4(), session_ids=(session_id,)
        )

    @override
    def revoke_session(self, target_session_id: UUID, *, timeout: float = 5) -> RuntimeSessionsLocked:
        self.selected_targets.append(target_session_id)
        if self._session_id in self.selected_cascade:
            self._session_id = None
        return RuntimeSessionsLocked(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            session_ids=self.selected_cascade,
        )

    @override
    def recover_profile(
        self, password: bytearray, *, grants: frozenset[UUID] = frozenset(), timeout: float = 20
    ) -> AutomationResumeReceipt:
        self.proof_calls += 1
        self.proof_seen = bytes(password)
        self.proof_buffer = password
        self.grants_seen = grants
        self.proof_started.set()
        if not self.release_proof.wait(5):
            raise TimeoutError("test proof release was not signalled")
        if self.wipe_in_port:
            password[:] = bytes(len(password))
        if self.proof_failure is not None:
            raise self.proof_failure
        if self.recovery_outcome is not None:
            return self.recovery_outcome
        return AutomationResumeReceipt(
            request_id=uuid4(),
            profile_id=self.profile_id,
            revision=2,
            lock_generation=1,
            reactivated_grants=grants,
        )

    @override
    def close(self) -> None:
        self.close_calls += 1
        self.close_started.set()
        if not self.release_close.wait(5):
            raise TimeoutError("test close release was not signalled")
        if self.close_failures_remaining:
            self.close_failures_remaining -= 1
            raise OSError("private-close-error-canary")
        self.closed = True


class _RefusingInventoryClient(_RuntimeClient):
    @override
    def sessions(self, *, timeout: float = 5) -> tuple[PublicAccessSession, ...]:
        raise RuntimeFrontendRefusedError("profile_session_expired")


class _ApiInventoryClient(_RuntimeClient):
    def __init__(self, profile_id: UUID) -> None:
        super().__init__(profile_id, admitted=True)
        self.api_key = True

    @override
    def sessions(self, *, timeout: float = 5) -> tuple[PublicAccessSession, ...]:
        raise RuntimeFrontendRefusedError("human_authority_required")


class _ExpiringInventoryClient(_RuntimeClient):
    def __init__(self, profile_id: UUID, *, failure: Exception) -> None:
        super().__init__(profile_id, admitted=True)
        self.reads = 0
        self.failure = failure

    @override
    def sessions(self, *, timeout: float = 5) -> tuple[PublicAccessSession, ...]:
        self.reads += 1
        if self.reads > 1:
            raise self.failure
        return self.inventory


def _scope() -> AccessScope:
    return AccessScope(
        operations=frozenset(),
        actions=frozenset(),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _session(profile_id: UUID, session_id: UUID) -> PublicAccessSession:
    return PublicAccessSession(
        session_id=session_id,
        profile_id=profile_id,
        client_id=uuid4(),
        parent_session_id=None,
        grant_id=None,
        key_id=None,
        kind=SessionKind.HUMAN,
        state=SessionState.ACTIVE,
        scope=_scope(),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )


async def _until(pilot: Pilot[None], condition: Callable[[], bool]) -> None:
    async with asyncio.timeout(6):
        while not condition():
            await pilot.pause(0.02)


async def _assert_resume_replay_fenced(screen: RuntimeAccessManagementScreen, recovery: _RuntimeClient) -> None:
    """A disabled button alone cannot fence a programmatic retry."""
    assert screen.query_one("#runtime-access-resume", Button).disabled
    calls = recovery.proof_calls
    password = screen.query_one("#runtime-access-password", Input)
    grants = screen.query_one("#runtime-access-grants", Input)
    password.value, grants.value = "private-replay-proof", str(uuid4())
    await screen._perform("resume")
    assert recovery.proof_calls == calls and password.value == grants.value == ""
    prior_worker = screen._worker
    password.value, grants.value = "private-event-replay-proof", str(uuid4())
    screen.on_button_pressed(Button.Pressed(screen.query_one("#runtime-access-resume", Button)))
    assert screen._worker is prior_worker
    assert recovery.proof_calls == calls and password.value == grants.value == ""


class _UnmountNotifiedScreen(RuntimeAccessManagementScreen):
    def __init__(self, client: RuntimeFrontendClient, *, open_recovery_client: RecoveryClientOpener) -> None:
        super().__init__(client, open_recovery_client=open_recovery_client)
        self.unmounting = asyncio.Event()

    @override
    async def on_unmount(self) -> None:
        self.unmounting.set()
        await super().on_unmount()


@pytest.mark.asyncio
async def test_inventory_denial_and_current_lock_keep_distinct_runtime_actions() -> None:
    profile_id = uuid4()
    client = _RuntimeClient(profile_id, admitted=True)

    async def open_recovery() -> RuntimeFrontendClient:
        raise AssertionError("recovery was not requested")

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(
            pilot, lambda: str(client.session_id) in str(screen.query_one("#runtime-access-sessions", Static).content)
        )
        assert not screen.query_one("#runtime-access-view-automation", Button).disabled
        assert not screen.query("#runtime-access-revoke-session")
        target = uuid4()
        screen.query_one("#runtime-access-target", Input).value = str(target)
        screen.query_one("#runtime-access-deny-key", Button).press()
        await _until(pilot, lambda: bool(client.denials) and not screen._busy)
        assert client.denials == [(AutomationDenialKind.KEY, target)]
        screen.query_one("#runtime-access-deny-all", Button).press()
        await _until(pilot, lambda: len(client.denials) == 2)
        assert client.denials[-1] == (AutomationDenialKind.ALL, None)
        screen.query_one("#runtime-access-lock-current", Button).press()
        await _until(pilot, lambda: client.locked)
        assert not screen.query_one("#runtime-access-sessions", Static).content
        assert screen.query_one("#runtime-access-deny-key", Button).disabled
        assert not screen.query_one("#runtime-access-resume", Button).disabled
        assert not client.closed


@pytest.mark.asyncio
async def test_human_create_journey_borrows_exact_reviewer_and_refreshes_after_cancel() -> None:
    """Presentation wiring opens a requester, without granting or opening its custody."""
    client = _RuntimeClient(uuid4(), admitted=True)
    created: list[RuntimeAutomationRequesterScreen] = []

    async def open_recovery() -> RuntimeFrontendClient:
        raise AssertionError("recovery was not requested")

    async def open_requester(_profile_id: UUID) -> RuntimeFrontendClient:
        raise AssertionError("unsubmitted requester must not open a native client")

    def factory(reviewer: RuntimeFrontendClient) -> RuntimeAutomationRequesterScreen:
        assert reviewer is client
        definitions = build_user_profile_operation_definitions()
        registration = next(
            item
            for item in build_user_profile_operation_registrations(definitions)
            if str(item.contract.definition_id) == "user-profile.view"
        )
        requester = RuntimeAutomationRequesterScreen(
            profile_id=client.profile_id,
            contracts=OperationPublicContractSetV1.build((registration.contract,)),
            secrets_store=cast(AutomationSecretStore, object()),
            open_client=open_requester,
            reviewer_client=reviewer,
        )
        created.append(requester)
        return requester

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery, requester_factory=factory)
    app = ScreenHostApp(screen)
    async with app.run_test(size=(140, 48)) as pilot:
        await _until(pilot, lambda: screen._admin_available and not screen._busy)
        screen.query_one("#runtime-access-create-automation", Button).press()
        await _until(pilot, lambda: isinstance(app.screen, RuntimeAutomationRequesterScreen))
        await pilot.pause()
        requester = app.screen
        assert isinstance(requester, RuntimeAutomationRequesterScreen)
        assert created == [requester]
        assert requester._reviewer_client is client and requester._client is None
        requester.action_close()
        await _until(pilot, lambda: app.screen is screen and not screen._busy)
        assert screen._admin_available and not client.closed
        assert not screen.query_one("#runtime-access-create-automation", Button).disabled


@pytest.mark.asyncio
async def test_api_human_refusal_fences_create_even_for_programmatic_button_event() -> None:
    client = _ApiInventoryClient(uuid4())

    async def open_recovery() -> RuntimeFrontendClient:
        raise AssertionError("recovery was not requested")

    def factory(_reviewer: RuntimeFrontendClient) -> RuntimeAutomationRequesterScreen:
        raise AssertionError("API authority must not open human enrollment")

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery, requester_factory=factory)
    app = ScreenHostApp(screen)
    async with app.run_test(size=(140, 48)) as pilot:
        await _until(pilot, lambda: not screen._busy and not screen._admin_available)
        button = screen.query_one("#runtime-access-create-automation", Button)
        assert button.disabled
        screen.on_button_pressed(Button.Pressed(button))
        await pilot.pause()
        assert app.screen is screen and not screen._access_lost
        assert not screen.query_one("#runtime-access-lock-current", Button).disabled


@pytest.mark.asyncio
async def test_session_detail_keeps_parent_grant_key_and_action_scope_visible() -> None:
    client = _RuntimeClient(uuid4(), admitted=True)
    session = client.inventory[0].model_copy(
        update={
            "parent_session_id": uuid4(),
            "grant_id": uuid4(),
            "key_id": uuid4(),
            "scope": _scope().model_copy(
                update={"operations": frozenset({"user-profile.view"}), "actions": frozenset({AccessAction.OBSERVE})}
            ),
        }
    )
    client.inventory = (session,)

    async def open_recovery() -> RuntimeFrontendClient:
        raise AssertionError("recovery was not requested")

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(140, 48)) as pilot:
        await _until(pilot, lambda: screen._admin_available and not screen._busy)
        shown = str(screen.query_one("#runtime-access-sessions", Static).content)
        for identity in (
            session.session_id,
            session.client_id,
            session.parent_session_id,
            session.grant_id,
            session.key_id,
        ):
            assert str(identity) in shown
        assert "user-profile.view" in shown and AccessAction.OBSERVE.value in shown
        assert tr("tui.automation_inventory.all_periods") in shown


@pytest.mark.asyncio
async def test_denial_receipt_distinguishes_denied_access_from_pending_native_cleanup() -> None:
    class PendingCleanupClient(_RuntimeClient):
        @override
        def deny_automation(
            self, kind: AutomationDenialKind, *, target_id: UUID | None = None, timeout: float = 10
        ) -> AutomationDenialReceipt:
            return (
                super()
                .deny_automation(kind, target_id=target_id, timeout=timeout)
                .model_copy(update={"cleanup_pending": True})
            )

    client = PendingCleanupClient(uuid4(), admitted=True)

    async def open_recovery() -> RuntimeFrontendClient:
        raise AssertionError("recovery was not requested")

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(140, 48)) as pilot:
        await _until(pilot, lambda: screen._admin_available and not screen._busy)
        screen.query_one("#runtime-access-deny-all", Button).press()
        await _until(pilot, lambda: bool(client.denials) and not screen._busy)
        assert str(screen.query_one("#runtime-access-status", Static).content) == tr(
            "tui.runtime_access.denial_acknowledgement",
            access_denied=tr("flows.confirm.yes"),
            cleanup_pending=tr("flows.confirm.yes"),
        )
        session_id = client.session_id
        screen.query_one("#runtime-access-lock-current", Button).press()
        await _until(pilot, lambda: client.locked and not screen._busy)
        assert str(screen.query_one("#runtime-access-status", Static).content) == tr(
            "tui.runtime_access.sessions_locked", session_ids=str(session_id)
        )


@pytest.mark.asyncio
async def test_profile_lock_uses_distinct_durable_denial_door() -> None:
    profile_id = uuid4()
    client = _RuntimeClient(profile_id, admitted=True)

    async def open_recovery() -> RuntimeFrontendClient:
        raise AssertionError("recovery was not requested")

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        screen.query_one("#runtime-access-lock-profile", Button).press()
        await _until(pilot, lambda: bool(client.denials))
        assert client.denials == [(AutomationDenialKind.PROFILE_LOCK, None)]
        assert not client.locked
        assert screen.query_one("#runtime-access-lock-current", Button).disabled


@pytest.mark.asyncio
async def test_recovery_owns_fresh_client_and_waits_for_native_proof_to_settle() -> None:
    profile_id = uuid4()
    client = _RuntimeClient(profile_id, admitted=True)
    recovery = _RuntimeClient(profile_id, admitted=False)
    recovery.release_proof.clear()
    opened = 0

    async def open_recovery() -> RuntimeFrontendClient:
        nonlocal opened
        opened += 1
        return recovery

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    proof_input = "private-test-proof"
    grant_id = uuid4()
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        password = screen.query_one("#runtime-access-password", Input)
        assert password.password
        password.value = proof_input
        screen.query_one("#runtime-access-grants", Input).value = str(grant_id)
        screen.query_one("#runtime-access-resume", Button).press()
        await _until(pilot, recovery.proof_started.is_set)
        assert password.value == ""
        assert screen.query_one("#runtime-access-close", Button).disabled
        screen.action_close()
        assert screen.is_mounted
        recovery.release_proof.set()
        await _until(pilot, lambda: recovery.closed and not screen._busy)
        assert opened == 1
        assert recovery.proof_seen == proof_input.encode()
        assert recovery.grants_seen == frozenset({grant_id})
        assert not client.closed
        assert proof_input not in str(screen.query_one("#runtime-access-status", Static).content)
        assert proof_input not in repr(screen)


@pytest.mark.asyncio
async def test_invalid_grant_selection_wipes_password_before_opening_connection() -> None:
    profile_id = uuid4()
    client = _RuntimeClient(profile_id, admitted=True)
    opened = False

    async def open_recovery() -> RuntimeFrontendClient:
        nonlocal opened
        opened = True
        raise AssertionError("invalid selection cannot open recovery")

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        password = screen.query_one("#runtime-access-password", Input)
        password.value = "private-test-proof"
        screen.query_one("#runtime-access-grants", Input).value = f"{uuid4()},"
        screen.query_one("#runtime-access-resume", Button).press()
        await _until(pilot, lambda: password.value == "")
        assert not opened
        assert "private-test-proof" not in str(screen.query_one("#runtime-access-status", Static).content)


@pytest.mark.asyncio
async def test_cancelled_recovery_retains_proof_and_connection_until_native_call_settles() -> None:
    profile_id = uuid4()
    client = _RuntimeClient(profile_id, admitted=True)
    recovery = _RuntimeClient(profile_id, admitted=False)
    recovery.release_proof.clear()

    async def open_recovery() -> RuntimeFrontendClient:
        return recovery

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        screen.query_one("#runtime-access-password", Input).value = "bounded-private-proof"
        task = asyncio.create_task(screen._perform("resume"))
        await _until(pilot, recovery.proof_started.is_set)
        task.cancel()
        await pilot.pause(0.05)
        assert not task.done()
        assert not recovery.closed
        assert recovery.proof_buffer == bytearray(b"bounded-private-proof")
        assert screen.query_one("#runtime-access-close", Button).disabled
        recovery.release_proof.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert recovery.closed
        assert recovery.proof_buffer is not None and not any(recovery.proof_buffer)
        assert screen.query_one("#runtime-access-password", Input).value == ""
        assert not client.closed


@pytest.mark.asyncio
async def test_authority_loss_clears_inventory_and_disables_admitted_actions() -> None:
    profile_id = uuid4()
    client = _RefusingInventoryClient(profile_id, admitted=True)

    async def open_recovery() -> RuntimeFrontendClient:
        raise AssertionError("recovery was not requested")

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: screen._access_lost)
        assert not screen.query_one("#runtime-access-sessions", Static).content
        assert screen.query_one("#runtime-access-lock-current", Button).disabled
        assert screen.query_one("#runtime-access-lock-profile", Button).disabled
        assert not screen.query_one("#runtime-access-resume", Button).disabled
        assert not screen.query_one("#runtime-access-close", Button).disabled


@pytest.mark.asyncio
async def test_api_inventory_human_refusal_keeps_only_authorized_current_lock() -> None:
    client = _ApiInventoryClient(uuid4())

    async def open_recovery() -> RuntimeFrontendClient:
        raise AssertionError("recovery was not requested")

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy and not screen._admin_available)
        assert not screen._access_lost
        assert not screen.query_one("#runtime-access-lock-current", Button).disabled
        for suffix in (
            "refresh",
            "view-automation",
            "lock-selected",
            "lock-profile",
            "deny-key",
            "deny-grant",
            "deny-all",
        ):
            assert screen.query_one(f"#runtime-access-{suffix}", Button).disabled
        assert not screen.query_one("#runtime-access-sessions", Static).content
        screen.query_one("#runtime-access-lock-current", Button).press()
        await _until(pilot, lambda: client.locked)
        assert screen._access_lost
        assert not client.closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [RuntimeFrontendRefusedError("session_expired"), OSError("private-transport-error-canary")],
    ids=["expiry", "transport-loss"],
)
async def test_later_authority_or_transport_loss_clears_previously_rendered_private_rows(failure: Exception) -> None:
    client = _ExpiringInventoryClient(uuid4(), failure=failure)

    async def open_recovery() -> RuntimeFrontendClient:
        raise AssertionError("recovery was not requested")

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(
            pilot, lambda: str(client.session_id) in str(screen.query_one("#runtime-access-sessions", Static).content)
        )
        screen.query_one("#runtime-access-refresh", Button).press()
        await _until(pilot, lambda: screen._access_lost)
        assert not screen.query_one("#runtime-access-sessions", Static).content
        assert screen.query_one("#runtime-access-lock-current", Button).disabled
        assert screen.query_one("#runtime-access-deny-key", Button).disabled
        assert "private-transport-error-canary" not in str(screen.query_one("#runtime-access-status", Static).content)


@pytest.mark.asyncio
async def test_foreign_recovery_client_is_closed_without_receiving_proof() -> None:
    client = _RuntimeClient(uuid4(), admitted=True)
    foreign = _RuntimeClient(uuid4(), admitted=False)

    async def open_recovery() -> RuntimeFrontendClient:
        return foreign

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        password = screen.query_one("#runtime-access-password", Input)
        password.value = "private-test-proof"
        screen.query_one("#runtime-access-resume", Button).press()
        await _until(pilot, lambda: foreign.closed)
        assert foreign.proof_seen is None
        assert password.value == ""
        assert not client.closed


@pytest.mark.asyncio
async def test_selected_session_revoke_preserves_current_access_unless_cascade_retires_it() -> None:
    profile_id = uuid4()
    client = _RuntimeClient(profile_id, admitted=True)
    own_session_id = client.session_id
    selected_id = uuid4()
    child_id = uuid4()
    client.selected_cascade = (selected_id, child_id)

    async def open_recovery() -> RuntimeFrontendClient:
        raise AssertionError("recovery was not requested")

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        screen.query_one("#runtime-access-target", Input).value = str(selected_id)
        screen.query_one("#runtime-access-lock-selected", Button).press()
        await _until(pilot, lambda: len(client.selected_targets) == 1 and not screen._busy)
        assert client.selected_targets == [selected_id]
        assert client.selected_cascade == (selected_id, child_id)
        assert client.session_id == own_session_id
        assert not screen.query_one("#runtime-access-lock-selected", Button).disabled

        client.selected_cascade = (selected_id, own_session_id)
        screen.query_one("#runtime-access-target", Input).value = str(selected_id)
        screen.query_one("#runtime-access-lock-selected", Button).press()
        await _until(pilot, lambda: screen._access_lost)
        assert client.selected_targets == [selected_id, selected_id]
        assert screen.query_one("#runtime-access-lock-selected", Button).disabled
        assert not screen.query_one("#runtime-access-close", Button).disabled


@pytest.mark.asyncio
async def test_real_unmount_drains_recovery_and_wipes_proof_without_closing_borrowed_client() -> None:
    client = _RuntimeClient(uuid4(), admitted=True)
    recovery = _RuntimeClient(client.profile_id, admitted=False)
    recovery.release_proof.clear()
    recovery.wipe_in_port = False

    async def open_recovery() -> RuntimeFrontendClient:
        return recovery

    screen = _UnmountNotifiedScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        screen.query_one("#runtime-access-password", Input).value = "unmount-private-proof"
        screen.query_one("#runtime-access-resume", Button).press()
        await _until(pilot, recovery.proof_started.is_set)
        pilot.app.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), 2)
        assert not recovery.closed
        assert not client.closed
        recovery.release_proof.set()

        def settled() -> bool:
            return recovery.closed

        async with asyncio.timeout(6):
            while not settled():
                await asyncio.sleep(0.01)
        assert recovery.proof_buffer is not None and not any(recovery.proof_buffer)
        assert not client.closed


@pytest.mark.asyncio
async def test_unmount_during_recovery_open_closes_late_client_without_delivering_proof() -> None:
    client = _RuntimeClient(uuid4(), admitted=True)
    recovery = _RuntimeClient(client.profile_id, admitted=False)
    opening = asyncio.Event()
    release = asyncio.Event()

    async def open_recovery() -> RuntimeFrontendClient:
        opening.set()
        await release.wait()
        return recovery

    screen = _UnmountNotifiedScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        password = screen.query_one("#runtime-access-password", Input)
        password.value = "late-private-proof"
        screen.query_one("#runtime-access-resume", Button).press()
        await asyncio.wait_for(opening.wait(), 2)
        pilot.app.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), 2)
        assert not recovery.closed
        release.set()

        def settled() -> bool:
            return recovery.closed

        async with asyncio.timeout(6):
            while not settled():
                await asyncio.sleep(0.01)
        assert recovery.proof_seen is None
        assert password.value == ""
        assert not client.closed


@pytest.mark.asyncio
async def test_recovery_refusal_keeps_primary_and_retryable_close_owner() -> None:
    client = _RuntimeClient(uuid4(), admitted=True)
    recovery = _RuntimeClient(client.profile_id, admitted=False)
    refusal = RuntimeFrontendRefusedError("profile_session_expired")
    recovery.proof_failure = refusal
    recovery.close_failures_remaining = 1
    recovery.wipe_in_port = False

    async def open_recovery() -> RuntimeFrontendClient:
        return recovery

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        password = bytearray(b"private-refused-proof")
        with pytest.raises(RuntimeFrontendRefusedError) as caught:
            await screen._recover_owned(password, frozenset())
        assert caught.value is refusal
        assert not any(password)
        assert not recovery.closed
        assert recovery.close_calls == 1
        cleanup = refusal.__dict__.get("async_cleanup_error")
        assert isinstance(cleanup, AsyncResourceCleanupError)
        await cleanup.retry_cleanup()
        assert recovery.closed
    assert recovery.close_calls == 2
    assert client.close_calls == 0


@pytest.mark.asyncio
async def test_successful_recovery_failed_close_is_retried_on_unmount() -> None:
    client = _RuntimeClient(uuid4(), admitted=True)
    recovery = _RuntimeClient(client.profile_id, admitted=False)
    recovery.close_failures_remaining = 1
    recovery.wipe_in_port = False

    async def open_recovery() -> RuntimeFrontendClient:
        return recovery

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        screen.query_one("#runtime-access-password", Input).value = "private-successful-proof"
        await screen._perform("resume")
        assert recovery.proof_seen == b"private-successful-proof"
        assert recovery.proof_buffer is not None and not any(recovery.proof_buffer)
        assert not recovery.closed
        assert recovery.close_calls == 1
        presentation = str(screen.query_one("#runtime-access-status", Static).content)
        assert tr("tui.runtime_access.completed") in presentation
        assert tr("tui.runtime_access.refused") not in presentation
        assert RuntimeRefusalCode.UNAVAILABLE.value in presentation
        assert screen._resume_receipt is not None and screen._resume_receipt.profile_id == client.profile_id
        assert screen._recovery_clients
        await _assert_resume_replay_fenced(screen, recovery)
        assert recovery.close_calls == 1
        with pytest.raises(RuntimeFrontendRefusedError):
            _ = recovery.session_id
        assert "private-close-error-canary" not in presentation
        assert "private-successful-proof" not in presentation
    assert recovery.closed
    assert recovery.close_calls == 2
    assert client.close_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("receipt_fault", ["foreign_profile", "extra_grant", "missing_grant"])
async def test_recovery_mismatched_receipt_is_unknown_and_cannot_replay(receipt_fault: str) -> None:
    client = _RuntimeClient(uuid4(), admitted=True)
    original_session = client.session_id
    selected_grant = uuid4()
    selected = frozenset({selected_grant})
    recovery = _RuntimeClient(client.profile_id, admitted=False)
    recovery.recovery_outcome = AutomationResumeReceipt(
        request_id=uuid4(),
        profile_id=uuid4() if receipt_fault == "foreign_profile" else client.profile_id,
        revision=2,
        lock_generation=1,
        reactivated_grants=selected
        if receipt_fault == "foreign_profile"
        else selected | {uuid4()}
        if receipt_fault == "extra_grant"
        else frozenset(),
    )

    async def open_recovery() -> RuntimeFrontendClient:
        return recovery

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        screen.query_one("#runtime-access-password", Input).value = "private-receipt-proof"
        screen.query_one("#runtime-access-grants", Input).value = str(selected_grant)
        await screen._perform("resume")
        presentation = str(screen.query_one("#runtime-access-status", Static).content)
        assert tr("tui.runtime_management.availability.unknown") in presentation
        assert RuntimeRefusalCode.INVALID_FRAME.value in presentation
        assert tr("tui.runtime_access.completed") not in presentation
        assert "private-receipt-proof" not in presentation
        assert recovery.closed and recovery.proof_calls == 1
        assert recovery.proof_buffer is not None and not any(recovery.proof_buffer)
        assert screen._resume_receipt is None
        await _assert_resume_replay_fenced(screen, recovery)
        assert client.session_id == original_session and not client.closed
        with pytest.raises(RuntimeFrontendRefusedError):
            _ = recovery.session_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED),
        RuntimeFrontendRefusedError(RuntimeRefusalCode.CONNECTION_CLOSED.value),
        OSError("private-dispatch-error-canary"),
    ],
)
async def test_dispatched_recovery_transport_failure_is_unknown_and_fences_replay(failure: Exception) -> None:
    client = _RuntimeClient(uuid4(), admitted=True)
    recovery = _RuntimeClient(client.profile_id, admitted=False)
    recovery.proof_failure = failure
    recovery.wipe_in_port = False

    async def open_recovery() -> RuntimeFrontendClient:
        return recovery

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        screen.query_one("#runtime-access-password", Input).value = "private-dispatch-proof"
        await screen._perform("resume")
        presentation = str(screen.query_one("#runtime-access-status", Static).content)
        assert tr("tui.runtime_management.availability.unknown") in presentation
        assert "private-dispatch-error-canary" not in presentation and "private-dispatch-proof" not in presentation
        assert recovery.closed and recovery.proof_buffer is not None and not any(recovery.proof_buffer)
        await _assert_resume_replay_fenced(screen, recovery)
        assert not client.closed


@pytest.mark.asyncio
async def test_recovery_pre_dispatch_failure_and_domain_refusal_allow_fresh_proof_retry() -> None:
    client = _RuntimeClient(uuid4(), admitted=True)
    original_session = client.session_id
    refused = _RuntimeClient(client.profile_id, admitted=False)
    refused.proof_failure = RuntimeFrontendRefusedError("profile_session_expired")
    recovered = _RuntimeClient(client.profile_id, admitted=False)
    openings = 0

    async def open_recovery() -> RuntimeFrontendClient:
        nonlocal openings
        openings += 1
        if openings == 1:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        return refused if openings == 2 else recovered

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        for proof in ("private-before-dispatch-proof", "private-domain-refused-proof"):
            screen.query_one("#runtime-access-password", Input).value = proof
            await screen._perform("resume")
            presentation = str(screen.query_one("#runtime-access-status", Static).content)
            assert tr("tui.runtime_access.refused") in presentation
            assert tr("tui.runtime_management.availability.unknown") not in presentation
            assert not screen.query_one("#runtime-access-resume", Button).disabled
            assert screen.query_one("#runtime-access-password", Input).value == ""
            assert proof not in presentation
        assert refused.closed and refused.proof_calls == 1 and recovered.proof_calls == 0
        screen.query_one("#runtime-access-password", Input).value = "private-fresh-proof"
        await screen._perform("resume")
        assert recovered.proof_seen == b"private-fresh-proof" and recovered.closed
        assert screen._resume_receipt is not None
        assert screen._resume_receipt.profile_id == client.profile_id
        assert screen._resume_receipt.reactivated_grants == frozenset()
        assert openings == 3 and client.session_id == original_session and not client.closed


@pytest.mark.asyncio
async def test_recovery_settled_proof_is_wiped_before_blocked_close_and_cancel_keeps_known_receipt() -> None:
    client = _RuntimeClient(uuid4(), admitted=True)
    original_session = client.session_id
    recovery = _RuntimeClient(client.profile_id, admitted=False)
    recovery.wipe_in_port = False
    recovery.release_close.clear()

    async def open_recovery() -> RuntimeFrontendClient:
        return recovery

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        screen.query_one("#runtime-access-password", Input).value = "private-blocked-close-proof"
        recovering = asyncio.create_task(screen._perform("resume"))
        try:
            await _until(pilot, recovery.close_started.is_set)
            assert recovery.proof_buffer is not None and not any(recovery.proof_buffer)
            assert screen._resume_receipt is not None
            assert not recovering.done() and not recovery.closed
            recovering.cancel()
            recovering.cancel()
            assert not recovering.done()
        finally:
            recovery.release_close.set()
        with pytest.raises(asyncio.CancelledError):
            await recovering
        presentation = str(screen.query_one("#runtime-access-status", Static).content)
        assert tr("tui.runtime_access.completed") in presentation
        assert tr("tui.runtime_management.availability.unknown") not in presentation
        assert recovery.closed and screen._resume_receipt is not None
        await _assert_resume_replay_fenced(screen, recovery)
        assert client.session_id == original_session and not client.closed
        with pytest.raises(RuntimeFrontendRefusedError):
            _ = recovery.session_id


@pytest.mark.asyncio
async def test_cancelled_failed_recovery_preserves_body_and_retries_close_on_unmount() -> None:
    client = _RuntimeClient(uuid4(), admitted=True)
    recovery = _RuntimeClient(client.profile_id, admitted=False)
    refusal = RuntimeFrontendRefusedError("profile_session_expired")
    recovery.proof_failure = refusal
    recovery.close_failures_remaining = 1
    recovery.wipe_in_port = False
    recovery.release_proof.clear()

    async def open_recovery() -> RuntimeFrontendClient:
        return recovery

    screen = RuntimeAccessManagementScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        screen.query_one("#runtime-access-password", Input).value = "private-cancelled-proof"
        task = asyncio.create_task(screen._perform("resume"))
        await _until(pilot, recovery.proof_started.is_set)
        task.cancel()
        task.cancel()
        assert not task.done()
        assert not recovery.closed
        recovery.release_proof.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        assert caught.value.__dict__.get("cleanup_error") is refusal
        assert isinstance(refusal.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
        assert recovery.proof_buffer is not None and not any(recovery.proof_buffer)
        assert screen.query_one("#runtime-access-password", Input).value == ""
        assert not recovery.closed
        assert recovery.close_calls == 1
        assert tr("tui.runtime_management.availability.unknown") in str(
            screen.query_one("#runtime-access-status", Static).content
        )
        await _assert_resume_replay_fenced(screen, recovery)
    assert recovery.closed
    assert recovery.close_calls == 2
    assert client.close_calls == 0


@pytest.mark.asyncio
async def test_unmount_drains_failed_recovery_then_retries_owned_close() -> None:
    client = _RuntimeClient(uuid4(), admitted=True)
    recovery = _RuntimeClient(client.profile_id, admitted=False)
    recovery.proof_failure = RuntimeFrontendRefusedError("profile_session_expired")
    recovery.close_failures_remaining = 1
    recovery.wipe_in_port = False
    recovery.release_proof.clear()

    async def open_recovery() -> RuntimeFrontendClient:
        return recovery

    screen = _UnmountNotifiedScreen(client, open_recovery_client=open_recovery)
    async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
        await _until(pilot, lambda: not screen._busy)
        screen.query_one("#runtime-access-password", Input).value = "private-unmounted-proof"
        screen.query_one("#runtime-access-resume", Button).press()
        await _until(pilot, recovery.proof_started.is_set)
        pilot.app.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), 2)
        assert not recovery.closed
        assert recovery.close_calls == 0
        recovery.release_proof.set()
        await _until(pilot, lambda: recovery.closed)
        assert recovery.proof_buffer is not None and not any(recovery.proof_buffer)
    assert recovery.close_calls == 2
    assert client.close_calls == 0
