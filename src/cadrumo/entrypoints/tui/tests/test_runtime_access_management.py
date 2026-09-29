"""The standalone access screen uses exact runtime doors and owns recovery proof."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Event
from typing import override
from uuid import UUID, uuid4

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Input, Static

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....application.operations.registry import OperationFrontendProjection
from ....application.runtime.profile_access import RuntimeProfileStatus, RuntimeSessionsLocked
from ....application.user_profile.access_contracts import (
    AccessScope,
    AuthorityState,
    Availability,
    ProfileAccessStatus,
    SessionKind,
    SessionState,
)
from ....application.user_profile.access_projections import PublicAccessSession
from ....application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from ....application.user_profile.automation_lifecycle_service import AutomationResumeReceipt
from ..components.host import ScreenHostApp
from ..runtime_access_management import RecoveryClientOpener, RuntimeAccessManagementScreen

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
        self.inventory = (_session(profile_id, self._session_id),) if self._session_id is not None else ()
        self.proof_seen: bytes | None = None
        self.proof_buffer: bytearray | None = None
        self.wipe_in_port = True
        self.grants_seen: frozenset[UUID] | None = None
        self.proof_started = Event()
        self.release_proof = Event()
        self.release_proof.set()

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
        self.proof_seen = bytes(password)
        self.proof_buffer = password
        self.grants_seen = grants
        self.proof_started.set()
        if not self.release_proof.wait(5):
            raise TimeoutError("test proof release was not signalled")
        if self.wipe_in_port:
            password[:] = bytes(len(password))
        return AutomationResumeReceipt(
            request_id=uuid4(),
            profile_id=self.profile_id,
            revision=2,
            lock_generation=1,
            reactivated_grants=grants,
        )

    @override
    def close(self) -> None:
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
        assert screen.query_one("#runtime-access-close", Button).disabled
        recovery.release_proof.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert recovery.closed
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
