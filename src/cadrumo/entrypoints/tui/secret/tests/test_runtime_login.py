"""Runtime login retains exact client and proof through Textual cancellation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Event, get_ident
from typing import override
from uuid import UUID, uuid4

import pytest
from textual.app import App
from textual.await_complete import AwaitComplete
from textual.pilot import Pilot
from textual.widgets import Button, Input, Select

from .....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from .....application.operations.registry import OperationFrontendProjection
from .....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .....application.runtime.profile_access import RuntimeProfileStatus
from .....application.user_profile.access_contracts import (
    AccessScope,
    AuthorityState,
    Availability,
    ProfileAccessStatus,
)
from .....application.user_profile.automation_lifecycle_service import AutomationResumeReceipt
from .....application.user_profile.login_interaction import ProfileLoginChoice
from .....application.user_profile.login_session import ProfileReceiptRefusedError
from .....core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from .....core.profile_session import ProfileSessionRefusalReason
from ...components.status import PinnedStatusBar
from ..runtime_login import (
    RuntimeClientOpener,
    RuntimeCredentialClientOpener,
    RuntimeLoginAcceptor,
    RuntimeLoginHandoff,
    RuntimeLoginMethod,
    RuntimeLoginScreen,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _Client(RuntimeFrontendClient):
    """An explicit UI fault port; native admission has separate acceptance."""

    def __init__(self, profile_id: UUID) -> None:
        self._profile_id = profile_id
        self._frontend = OperationFrontendProjection.TUI
        self._session_id: UUID | None = None
        self.password_calls = 0
        self.api_calls = 0
        self.receipt_calls = 0
        self.status_calls = 0
        self.receipt_thread: int | None = None
        self.receipt_refusal: ProfileSessionRefusalReason | None = None
        self.proof_before_wipe: bytes | None = None
        self.proof_buffer: bytearray | None = None
        self.closed = False
        self.started = Event()
        self.release = Event()
        self.release.set()
        self.refuse = False
        self.close_calls = 0
        self.close_failures_remaining = 0

    def _login_fault(self, proof: bytearray, *, api_key: bool) -> RuntimeProfileStatus:
        self.proof_buffer = proof
        self.proof_before_wipe = bytes(proof)
        self.started.set()
        if not self.release.wait(5):
            raise TimeoutError("test login release was not signalled")
        if self.refuse:
            raise RuntimeFrontendRefusedError("credential_rejected")
        return self._status(api_key=api_key)

    def _status(self, *, api_key: bool) -> RuntimeProfileStatus:
        """Return only the synthetic admitted status for this fault port."""
        self._session_id = uuid4()
        return RuntimeProfileStatus(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            status=ProfileAccessStatus(
                connected=True,
                credential_authenticated=True,
                profile_id=self.profile_id,
                session_id=self.session_id,
                session_expires_at=datetime.now(UTC) + timedelta(minutes=10),
                grant_state=AuthorityState.ACTIVE if api_key else None,
                grant_expires_at=datetime.now(UTC) + timedelta(minutes=10) if api_key else None,
                grant_valid=api_key,
                profile_bound=True,
                storage=Availability.AVAILABLE,
                automation_custody=Availability.AVAILABLE,
                published_authority=Availability.AVAILABLE,
                provider=Availability.NOT_REQUIRED,
                effective_scope=AccessScope(
                    operations=frozenset(),
                    actions=frozenset(),
                    disclosures=frozenset(),
                    periods=None,
                    allow_period_independent=True,
                    allow_delegation=False,
                ),
                denial=None,
            ),
        )

    @override
    def login_password(
        self, secret: bytearray, *, timeout: float = 20, persist_receipt: bool = False
    ) -> RuntimeProfileStatus:
        assert not persist_receipt
        self.password_calls += 1
        return self._login_fault(secret, api_key=False)

    @override
    def login_api_key(self, secret: bytearray, *, timeout: float = 20) -> RuntimeProfileStatus:
        self.api_calls += 1
        return self._login_fault(secret, api_key=True)

    @override
    def resume_receipt(self, *, timeout: float = 20) -> RuntimeProfileStatus:
        """Model existing protected-receipt availability without an input secret."""
        self.receipt_calls += 1
        self.receipt_thread = get_ident()
        self.started.set()
        if not self.release.wait(5):
            raise TimeoutError("test receipt release was not signalled")
        if self.receipt_refusal is not None:
            raise ProfileReceiptRefusedError(self.receipt_refusal)
        return self._status(api_key=False)

    @override
    def status(self, *, timeout: float = 5) -> RuntimeProfileStatus:
        """Inspect a synthetically preadmitted stored-reference connection."""
        self.status_calls += 1
        return self._status(api_key=True)

    @override
    def close(self) -> None:
        self.close_calls += 1
        if self.close_failures_remaining:
            self.close_failures_remaining -= 1
            raise OSError("private-reference-close-canary")
        self.closed = True


class _ClientCleanup:
    """Explicit native-close boundary port for failed admission detector cases."""

    def __init__(self, client: _Client) -> None:
        self._client = client

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)


class _RecoveryClient(_Client):
    """Explicit recovery wire boundary; this port grants no authenticated session."""

    def __init__(self, profile_id: UUID) -> None:
        super().__init__(profile_id)
        self.resume_calls = 0
        self.grants_seen: frozenset[UUID] | None = None
        self.recovery_failure: BaseException | None = None
        self.recovery_thread: int | None = None
        self.close_threads: list[int] = []

    @override
    def recover_profile(
        self, password: bytearray, *, grants: frozenset[UUID] = frozenset(), timeout: float = 20
    ) -> AutomationResumeReceipt:
        assert self._session_id is None
        self.resume_calls += 1
        self.grants_seen = grants
        self.recovery_thread = get_ident()
        self.proof_before_wipe = bytes(password)
        self.proof_buffer = password
        self.started.set()
        if not self.release.wait(5):
            raise TimeoutError("test recovery release was not signalled")
        if self.recovery_failure is not None:
            raise self.recovery_failure
        return AutomationResumeReceipt(
            request_id=uuid4(), profile_id=self.profile_id, revision=2, lock_generation=1, reactivated_grants=grants
        )

    @override
    def close(self) -> None:
        self.close_threads.append(get_ident())
        if self.proof_buffer is not None:
            assert not any(self.proof_buffer), "recovery proof must be wiped before native close"
        super().close()


async def _failed_reference_admission(client: _Client, refusal: RuntimeFrontendRefusedError) -> RuntimeFrontendClient:
    try:
        raise refusal
    except BaseException as error:
        await close_async_resources(
            _ClientCleanup(client), task_name="test-reference-admission-close", primary_error=error
        )
        raise


class _Host(App[None]):
    def __init__(self, screen: RuntimeLoginScreen) -> None:
        super().__init__()
        self.login_screen = screen
        self.handoff: RuntimeLoginHandoff | None = None

    async def _present(self) -> None:
        self.handoff = await self.push_screen_wait(self.login_screen)

    def on_mount(self) -> None:
        self.run_worker(self._present())


class _NoReceiverHost(App[None]):
    def __init__(self, screen: RuntimeLoginScreen) -> None:
        super().__init__()
        self.login_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self.login_screen)


class _HandoffOwner:
    def __init__(self, *, allow: bool = True) -> None:
        self.allow = allow
        self.accepted: RuntimeLoginHandoff | None = None

    def accept(self, handoff: RuntimeLoginHandoff) -> bool:
        if not self.allow or self.accepted is not None:
            return False
        self.accepted = handoff
        return True


class _UnmountNotifiedScreen(RuntimeLoginScreen):
    def __init__(
        self,
        *,
        choices: tuple[ProfileLoginChoice, ...],
        open_client: RuntimeClientOpener,
        open_credential_client: RuntimeCredentialClientOpener | None = None,
        accept_handoff: RuntimeLoginAcceptor,
    ) -> None:
        super().__init__(
            choices=choices,
            open_client=open_client,
            open_credential_client=open_credential_client,
            accept_handoff=accept_handoff,
        )
        self.unmounting = asyncio.Event()

    @override
    async def on_unmount(self) -> None:
        self.unmounting.set()
        await super().on_unmount()


class _RejectedDismissalScreen(RuntimeLoginScreen):
    @override
    def dismiss(self, result: RuntimeLoginHandoff | None = None) -> AwaitComplete:
        raise RuntimeError("test handoff callback was not accepted")


async def _until(pilot: Pilot[None], predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(6):
        while not predicate():
            await pilot.pause(0.02)


def _choices() -> tuple[ProfileLoginChoice, ProfileLoginChoice]:
    return (
        ProfileLoginChoice(profile_id=str(uuid4()), label="First profile"),
        ProfileLoginChoice(profile_id=str(uuid4()), label="Second profile"),
    )


@pytest.mark.asyncio
async def test_password_default_transfers_only_exact_selected_verified_client() -> None:
    choices = _choices()
    selected = UUID(choices[1].profile_id)
    client = _Client(selected)
    opened: list[UUID] = []

    async def open_client(profile_id: UUID) -> RuntimeFrontendClient:
        opened.append(profile_id)
        return client

    owner = _HandoffOwner()
    proof_cleared_at_transfer: list[bool] = []

    def accept(handoff: RuntimeLoginHandoff) -> bool:
        proof_cleared_at_transfer.append(client.proof_buffer is not None and not any(client.proof_buffer))
        return owner.accept(handoff)

    screen = RuntimeLoginScreen(
        choices=choices,
        preselected=choices[1].profile_id,
        open_client=open_client,
        accept_handoff=accept,
    )
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert screen.query_one("#runtime-login-method", Select).value is RuntimeLoginMethod.PASSWORD
        field = screen.query_one("#runtime-login-credential", Input)
        assert field.password
        field.value = "synthetic-password-proof"
        screen.action_submit()
        assert field.value == ""
        await _until(pilot, lambda: host.handoff is not None)
        assert host.handoff is not None
        assert host.handoff.profile_id == selected
        assert host.handoff.profile_label == choices[1].label
        assert host.handoff.client is client
        assert owner.accepted is host.handoff
        assert proof_cleared_at_transfer == [True]
        assert host.handoff.status.status.session_id == client.session_id
        assert "_Client" not in repr(host.handoff)
        assert opened == [selected]
        assert client.password_calls == 1 and client.api_calls == 0
        assert client.proof_before_wipe == b"synthetic-password-proof"
        assert client.proof_buffer is not None and not any(client.proof_buffer)
        assert not client.closed
    client.close()


@pytest.mark.asyncio
async def test_api_key_is_explicit_and_refusal_never_falls_back_to_password() -> None:
    choices = _choices()
    profile_id = UUID(choices[0].profile_id)
    first = _Client(profile_id)
    first.refuse = True
    second = _Client(profile_id)
    candidates = iter((first, second))

    async def open_client(selected: UUID) -> RuntimeFrontendClient:
        assert selected == profile_id
        return next(candidates)

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        field = screen.query_one("#runtime-login-credential", Input)
        field.value = "old-password-candidate"
        screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.API_KEY
        await _until(pilot, lambda: field.value == "")
        field.value = "synthetic-api-key-proof"
        screen.action_submit()
        await _until(pilot, lambda: first.closed and not screen._busy)
        assert first.api_calls == 1 and first.password_calls == 0
        assert first.proof_buffer is not None and not any(first.proof_buffer)
        assert host.handoff is None
        assert screen.is_mounted
        assert screen.query_one("#runtime-login-method", Select).value is RuntimeLoginMethod.API_KEY
        field.value = "fresh-api-key-proof"
        screen.action_submit()
        await _until(pilot, lambda: host.handoff is not None)
        assert second.api_calls == 1 and second.password_calls == 0
        assert host.handoff is not None and host.handoff.client is second
        assert owner.accepted is host.handoff
    second.close()


@pytest.mark.asyncio
async def test_stored_api_reference_uses_only_its_separate_opener_and_restricted_handoff() -> None:
    choices = _choices()
    selected = UUID(choices[1].profile_id)
    reference = uuid4()
    client = _Client(selected)
    opened: list[tuple[UUID, UUID]] = []

    async def open_client(_selected: UUID) -> RuntimeFrontendClient:
        raise AssertionError("stored-reference mode must not open the unadmitted proof path")

    async def open_reference(profile_id: UUID, credential_reference: UUID) -> RuntimeFrontendClient:
        opened.append((profile_id, credential_reference))
        return client

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(
        choices=choices,
        preselected=choices[1].profile_id,
        open_client=open_client,
        open_credential_client=open_reference,
        accept_handoff=owner.accept,
    )
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        method = screen.query_one("#runtime-login-method", Select)
        proof_field = screen.query_one("#runtime-login-credential", Input)
        reference_field = screen.query_one("#runtime-login-reference", Input)
        assert not reference_field.display and proof_field.password
        proof_field.value = "discarded-password"
        method.value = RuntimeLoginMethod.API_REFERENCE
        await _until(pilot, lambda: reference_field.display and proof_field.value == "")
        assert not reference_field.password and not proof_field.display
        reference_field.value = "not-a-uuid"
        screen.action_submit()
        assert reference_field.value == "" and not opened
        reference_field.value = str(reference)
        screen.action_submit()
        assert reference_field.value == ""
        await _until(pilot, lambda: host.handoff is not None)
        assert opened == [(selected, reference)]
        assert host.handoff is owner.accepted
        assert host.handoff is not None and host.handoff.method is RuntimeLoginMethod.API_REFERENCE
        assert host.handoff.client is client and host.handoff.profile_id == selected
        assert client.status_calls == 1 and client.password_calls == client.api_calls == client.receipt_calls == 0
        assert client.proof_buffer is None and screen._pending_proof is None
        assert not client.closed
    client.close()


@pytest.mark.asyncio
async def test_stored_reference_refusal_does_not_open_other_proof_method() -> None:
    choices = _choices()
    selected = UUID(choices[0].profile_id)
    attempted: list[UUID] = []

    async def open_client(_selected: UUID) -> RuntimeFrontendClient:
        raise AssertionError("stored-reference refusal must not fall back")

    async def open_reference(profile_id: UUID, _reference: UUID) -> RuntimeFrontendClient:
        attempted.append(profile_id)
        raise RuntimeFrontendRefusedError("credential_rejected")

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(
        choices=choices,
        open_client=open_client,
        open_credential_client=open_reference,
        accept_handoff=owner.accept,
    )
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.API_REFERENCE
        await _until(pilot, lambda: screen.query_one("#runtime-login-reference", Input).display)
        screen.query_one("#runtime-login-reference", Input).value = str(uuid4())
        screen.action_submit()
        await _until(pilot, lambda: len(attempted) == 1 and not screen._busy)
        assert attempted == [selected]
        assert host.handoff is None and owner.accepted is None
        assert screen.is_mounted


@pytest.mark.asyncio
async def test_unmount_during_stored_reference_open_closes_after_open_settles() -> None:
    choices = _choices()
    client = _Client(UUID(choices[0].profile_id))
    started, release = asyncio.Event(), asyncio.Event()

    async def open_client(_selected: UUID) -> RuntimeFrontendClient:
        raise AssertionError("stored-reference opening must not use the password path")

    async def open_reference(_selected: UUID, _reference: UUID) -> RuntimeFrontendClient:
        started.set()
        await release.wait()
        return client

    owner = _HandoffOwner()
    screen = _UnmountNotifiedScreen(
        choices=choices,
        open_client=open_client,
        open_credential_client=open_reference,
        accept_handoff=owner.accept,
    )
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.API_REFERENCE
        await _until(pilot, lambda: screen.query_one("#runtime-login-reference", Input).display)
        screen.query_one("#runtime-login-reference", Input).value = str(uuid4())
        screen.action_submit()
        await asyncio.wait_for(started.wait(), 2)
        host.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), 2)
        assert not client.closed and host.handoff is None
        release.set()
        await _until(pilot, lambda: client.closed)
        assert owner.accepted is None and client.status_calls == 0


@pytest.mark.asyncio
async def test_explicit_receipt_resume_uses_no_supplied_proof_and_transfers_exact_client() -> None:
    choices = _choices()
    profile_id = UUID(choices[0].profile_id)
    client = _Client(profile_id)

    async def open_client(selected: UUID) -> RuntimeFrontendClient:
        assert selected == profile_id
        return client

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = _Host(screen)
    ui_thread = get_ident()
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        field = screen.query_one("#runtime-login-credential", Input)
        field.value = "old-password-must-be-discarded"
        screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.RECEIPT
        await _until(pilot, lambda: field.value == "" and not field.display)
        assert field.disabled
        field.value = "injected-value-must-not-be-read"

        screen.action_submit()
        assert field.value == ""
        await _until(pilot, lambda: host.handoff is not None)

        assert host.handoff is owner.accepted
        assert host.handoff is not None
        assert host.handoff.method is RuntimeLoginMethod.RECEIPT
        assert host.handoff.profile_id == profile_id and host.handoff.client is client
        assert client.receipt_calls == 1 and client.receipt_thread != ui_thread
        assert client.password_calls == client.api_calls == 0
        assert client.proof_buffer is None and client.proof_before_wipe is None
        assert screen._pending_proof is None
        assert not client.closed
    client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "receipt_refusal", (ProfileSessionRefusalReason.ABSENT, ProfileSessionRefusalReason.KEYRING_UNAVAILABLE)
)
async def test_receipt_refusal_keeps_manual_password_available(
    receipt_refusal: ProfileSessionRefusalReason,
) -> None:
    choices = _choices()
    profile_id = UUID(choices[0].profile_id)
    first = _Client(profile_id)
    first.receipt_refusal = receipt_refusal
    second = _Client(profile_id)
    candidates = iter((first, second))

    async def open_client(selected: UUID) -> RuntimeFrontendClient:
        assert selected == profile_id
        return next(candidates)

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        method = screen.query_one("#runtime-login-method", Select)
        field = screen.query_one("#runtime-login-credential", Input)
        method.value = RuntimeLoginMethod.RECEIPT
        await _until(pilot, lambda: not field.display)
        screen.action_submit()
        await _until(pilot, lambda: first.closed)
        assert first.receipt_calls == 1 and first.password_calls == first.api_calls == 0
        assert first.proof_buffer is None
        assert host.handoff is None and screen.is_mounted
        assert method.value is RuntimeLoginMethod.RECEIPT

        method.value = RuntimeLoginMethod.PASSWORD
        await _until(pilot, lambda: field.display and not field.disabled)
        field.value = "fresh-password-after-receipt-refusal"
        screen.action_submit()
        await _until(pilot, lambda: host.handoff is not None)
        assert host.handoff is owner.accepted
        assert host.handoff is not None and host.handoff.method is RuntimeLoginMethod.PASSWORD
        assert second.password_calls == 1 and second.receipt_calls == second.api_calls == 0
        assert second.proof_buffer is not None and not any(second.proof_buffer)
        assert not second.closed
    second.close()


@pytest.mark.asyncio
async def test_unmount_during_blocked_receipt_resume_owns_call_until_close() -> None:
    choices = _choices()
    client = _Client(UUID(choices[0].profile_id))
    client.release.clear()

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        return client

    owner = _HandoffOwner()
    screen = _UnmountNotifiedScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.RECEIPT
        await _until(pilot, lambda: not screen.query_one("#runtime-login-credential", Input).display)
        screen.action_submit()
        await _until(pilot, client.started.is_set)
        host.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), 2)
        assert not client.closed and owner.accepted is None
        client.release.set()
        await _until(pilot, lambda: client.closed)
        assert client.receipt_calls == 1 and client.password_calls == client.api_calls == 0
        assert client.proof_buffer is None and screen._pending_proof is None
        assert host.handoff is None


@pytest.mark.asyncio
async def test_unmount_during_blocking_login_closes_only_after_call_settles() -> None:
    choices = _choices()
    client = _Client(UUID(choices[0].profile_id))
    client.release.clear()

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        return client

    owner = _HandoffOwner()
    screen = _UnmountNotifiedScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        field = screen.query_one("#runtime-login-credential", Input)
        field.value = "bounded-proof"
        screen.action_submit()
        await _until(pilot, client.started.is_set)
        host.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), 2)
        assert not client.closed
        assert host.handoff is None
        assert owner.accepted is None
        client.release.set()
        await _until(pilot, lambda: client.closed)
        assert client.proof_buffer is not None and not any(client.proof_buffer)
        assert host.handoff is None


@pytest.mark.asyncio
async def test_unmount_during_open_closes_late_acquired_client_without_proof() -> None:
    choices = _choices()
    client = _Client(UUID(choices[0].profile_id))
    opening = asyncio.Event()
    release = asyncio.Event()

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        opening.set()
        await release.wait()
        return client

    owner = _HandoffOwner()
    screen = _UnmountNotifiedScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen.query_one("#runtime-login-credential", Input).value = "unread-proof"
        screen.action_submit()
        await _until(pilot, opening.is_set)
        host.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), 2)
        assert not client.closed
        release.set()
        await _until(pilot, lambda: client.closed)
        assert client.password_calls == 0 and client.api_calls == 0
        assert host.handoff is None
        assert owner.accepted is None


@pytest.mark.asyncio
async def test_wrong_profile_opener_is_closed_before_any_proof_delivery() -> None:
    choices = _choices()
    foreign = _Client(uuid4())

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        return foreign

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        field = screen.query_one("#runtime-login-credential", Input)
        field.value = "private-candidate"
        screen.action_submit()
        await _until(pilot, lambda: foreign.closed)
        assert field.value == ""
        assert foreign.password_calls == 0 and foreign.api_calls == 0
        assert host.handoff is None
        assert owner.accepted is None
        assert screen.is_mounted


@pytest.mark.asyncio
async def test_accepted_handoff_survives_failed_screen_dismissal() -> None:
    choices = _choices()
    client = _Client(UUID(choices[0].profile_id))

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        return client

    owner = _HandoffOwner()
    screen = _RejectedDismissalScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen.query_one("#runtime-login-credential", Input).value = "one-shot-proof"
        screen.action_submit()
        await _until(pilot, lambda: owner.accepted is not None)
        assert host.handoff is None
        assert screen.is_mounted
        assert client.password_calls == 1
        assert client.proof_buffer is not None and not any(client.proof_buffer)
        assert not client.closed
    client.close()


@pytest.mark.asyncio
async def test_real_screen_stack_without_accepting_owner_closes_client() -> None:
    choices = _choices()
    client = _Client(UUID(choices[0].profile_id))

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        return client

    owner = _HandoffOwner(allow=False)
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = _NoReceiverHost(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert host.screen is screen
        screen.query_one("#runtime-login-credential", Input).value = "abandoned-proof"
        screen.action_submit()
        await _until(pilot, lambda: client.closed)
        assert owner.accepted is None
        assert client.proof_buffer is not None and not any(client.proof_buffer)
        assert host.screen is screen
        await host.pop_screen()


@pytest.mark.asyncio
async def test_reference_refusal_retains_failed_owner_without_closing_later_handoff() -> None:
    choices = _choices()
    profile_id = UUID(choices[0].profile_id)
    failed = _Client(profile_id)
    failed.close_failures_remaining = 1
    admitted = _Client(profile_id)
    refusal = RuntimeFrontendRefusedError("credential_rejected")
    attempts = 0

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        raise AssertionError("reference admission cannot fall back")

    async def open_reference(_profile_id: UUID, _reference: UUID) -> RuntimeFrontendClient:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return await _failed_reference_admission(failed, refusal)
        return admitted

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(
        choices=choices,
        open_client=open_client,
        open_credential_client=open_reference,
        accept_handoff=owner.accept,
    )
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.API_REFERENCE
        await _until(pilot, lambda: screen.query_one("#runtime-login-reference", Input).display)
        screen.query_one("#runtime-login-reference", Input).value = str(uuid4())
        screen.action_submit()
        await _until(pilot, lambda: attempts == 1 and not screen._busy)
        assert screen.is_mounted and host.handoff is None
        status = screen.query_one("#runtime-login-status", PinnedStatusBar)
        assert "credential_rejected" in status.message
        assert "private-reference-close-canary" not in status.message
        assert isinstance(refusal.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
        assert failed.close_calls == 1 and not failed.closed
        screen.query_one("#runtime-login-reference", Input).value = str(uuid4())
        screen.action_submit()
        await _until(pilot, lambda: host.handoff is not None and failed.closed)
        assert host.handoff is owner.accepted
        assert host.handoff is not None and host.handoff.client is admitted
        assert failed.close_calls == 2
        assert admitted.close_calls == 0
    assert failed.close_calls == 2
    assert admitted.close_calls == 0
    admitted.close()


@pytest.mark.asyncio
async def test_repeated_cancellation_of_failed_reference_open_preserves_cleanup_and_primary() -> None:
    choices = _choices()
    profile_id = UUID(choices[0].profile_id)
    failed = _Client(profile_id)
    failed.close_failures_remaining = 1
    refusal = RuntimeFrontendRefusedError("credential_rejected")
    started, release = asyncio.Event(), asyncio.Event()

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        raise AssertionError("reference admission cannot fall back")

    async def open_reference(_profile_id: UUID, _reference: UUID) -> RuntimeFrontendClient:
        started.set()
        await release.wait()
        return await _failed_reference_admission(failed, refusal)

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(
        choices=choices,
        open_client=open_client,
        open_credential_client=open_reference,
        accept_handoff=owner.accept,
    )
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        task = asyncio.create_task(
            screen._attempt(profile_id, choices[0].label, RuntimeLoginMethod.API_REFERENCE, None, uuid4())
        )
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        task.cancel()
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        assert caught.value.__dict__.get("cleanup_error") is refusal
        assert isinstance(refusal.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
        assert failed.close_calls == 1 and not failed.closed
        assert host.handoff is None and owner.accepted is None
    assert failed.closed and failed.close_calls == 2


@pytest.mark.asyncio
async def test_unmount_during_failed_reference_open_drains_then_retries_cleanup() -> None:
    choices = _choices()
    profile_id = UUID(choices[0].profile_id)
    failed = _Client(profile_id)
    failed.close_failures_remaining = 1
    refusal = RuntimeFrontendRefusedError("credential_rejected")
    started, release = asyncio.Event(), asyncio.Event()

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        raise AssertionError("reference admission cannot fall back")

    async def open_reference(_profile_id: UUID, _reference: UUID) -> RuntimeFrontendClient:
        started.set()
        await release.wait()
        return await _failed_reference_admission(failed, refusal)

    owner = _HandoffOwner()
    screen = _UnmountNotifiedScreen(
        choices=choices,
        open_client=open_client,
        open_credential_client=open_reference,
        accept_handoff=owner.accept,
    )
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.API_REFERENCE
        await _until(pilot, lambda: screen.query_one("#runtime-login-reference", Input).display)
        screen.query_one("#runtime-login-reference", Input).value = str(uuid4())
        screen.action_submit()
        await asyncio.wait_for(started.wait(), 2)
        host.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), 2)
        assert failed.close_calls == 0
        release.set()
        await _until(pilot, lambda: failed.closed)
        assert isinstance(refusal.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
        assert host.handoff is None and owner.accepted is None
    assert failed.close_calls == 2


@pytest.mark.asyncio
async def test_returned_reference_status_refusal_keeps_primary_and_retries_failed_close() -> None:
    refusal = RuntimeFrontendRefusedError("credential_rejected")

    class RefusingStatusClient(_Client):
        @override
        def status(self, *, timeout: float = 5) -> RuntimeProfileStatus:
            self.status_calls += 1
            raise refusal

    choices = _choices()
    client = RefusingStatusClient(UUID(choices[0].profile_id))
    client.close_failures_remaining = 1

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        raise AssertionError("reference admission cannot fall back")

    async def open_reference(_profile_id: UUID, _reference: UUID) -> RuntimeFrontendClient:
        return client

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(
        choices=choices,
        open_client=open_client,
        open_credential_client=open_reference,
        accept_handoff=owner.accept,
    )
    async with _Host(screen).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.API_REFERENCE
        await _until(pilot, lambda: screen.query_one("#runtime-login-reference", Input).display)
        screen.query_one("#runtime-login-reference", Input).value = str(uuid4())
        screen.action_submit()
        await _until(pilot, lambda: client.close_calls == 1 and not screen._busy)
        assert isinstance(refusal.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
        assert "credential_rejected" in screen.query_one("#runtime-login-status", PinnedStatusBar).message
        assert client.status_calls == 1 and not client.closed
        assert owner.accepted is None
        assert screen.is_mounted
    assert client.closed and client.close_calls == 2


@pytest.mark.asyncio
async def test_denied_handoff_failed_close_remains_owned_until_unmount_retry() -> None:
    choices = _choices()
    client = _Client(UUID(choices[0].profile_id))
    client.close_failures_remaining = 1

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        return client

    owner = _HandoffOwner(allow=False)
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    proof = bytearray(b"private-denied-handoff-proof")
    async with _NoReceiverHost(screen).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        with pytest.raises(AsyncResourceCleanupError):
            await screen._attempt(client.profile_id, choices[0].label, RuntimeLoginMethod.PASSWORD, proof, None)
        assert not any(proof)
        assert owner.accepted is None
        assert client.close_calls == 1 and not client.closed
        assert not screen._busy
        assert (
            "private-reference-close-canary" not in screen.query_one("#runtime-login-status", PinnedStatusBar).message
        )
    assert client.closed and client.close_calls == 2


@pytest.mark.asyncio
async def test_cancelled_returned_candidate_failed_close_preserves_cancellation_and_retry() -> None:
    choices = _choices()
    client = _Client(UUID(choices[0].profile_id))
    client.close_failures_remaining = 1
    client.release.clear()

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        return client

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    proof = bytearray(b"private-cancelled-candidate-proof")
    async with _Host(screen).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        task = asyncio.create_task(
            screen._attempt(client.profile_id, choices[0].label, RuntimeLoginMethod.PASSWORD, proof, None)
        )
        await _until(pilot, client.started.is_set)
        task.cancel()
        task.cancel()
        assert not task.done() and client.close_calls == 0
        client.release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        assert isinstance(caught.value.__dict__.get("cleanup_error"), AsyncResourceCleanupError)
        assert not any(proof)
        assert client.close_calls == 1 and not client.closed
        assert owner.accepted is None
    assert client.closed and client.close_calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("select_grants", [False, True], ids=["human_only", "selected_grants"])
async def test_cold_profile_resume_stays_unadmitted_and_next_login_uses_fresh_client(select_grants: bool) -> None:
    choices = _choices()
    profile_id = UUID(choices[1].profile_id)
    recovery = _RecoveryClient(profile_id)
    login = _Client(profile_id)
    selected = frozenset({uuid4(), uuid4()}) if select_grants else frozenset[UUID]()
    opened: list[UUID] = []

    async def open_client(selected_profile: UUID) -> RuntimeFrontendClient:
        opened.append(selected_profile)
        return recovery if len(opened) == 1 else login

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(
        choices=choices, preselected=choices[1].profile_id, open_client=open_client, accept_handoff=owner.accept
    )
    host = _Host(screen)
    ui_thread = get_ident()
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        password = screen.query_one("#runtime-login-resume-password", Input)
        assert password.password
        password.value = "synthetic-recovery-proof"
        screen.query_one("#runtime-login-resume-grants", Input).value = ", ".join(map(str, selected))
        screen.query_one("#runtime-login-resume", Button).press()
        await _until(pilot, lambda: recovery.closed and not screen._busy)
        assert password.value == ""
        assert recovery.resume_calls == 1 and recovery.grants_seen == selected
        assert recovery._session_id is None
        assert recovery.password_calls == recovery.api_calls == recovery.receipt_calls == recovery.status_calls == 0
        assert recovery.recovery_thread != ui_thread and all(thread != ui_thread for thread in recovery.close_threads)
        assert recovery.proof_buffer is not None and not any(recovery.proof_buffer)
        assert screen.query_one("#runtime-login-resume-grants", Input).value == ""
        assert host.screen is screen and host.handoff is None and owner.accepted is None
        assert "synthetic-recovery-proof" not in screen.query_one("#runtime-login-status", PinnedStatusBar).message
        screen.query_one("#runtime-login-credential", Input).value = "separate-login-proof"
        screen.action_submit()
        await _until(pilot, lambda: host.handoff is not None)
        assert opened == [profile_id, profile_id]
        assert recovery.close_calls == 1 and login.close_calls == 0
        assert login.password_calls == 1 and login.proof_before_wipe == b"separate-login-proof"
        assert host.handoff is not None and host.handoff.client is login
    assert recovery.close_calls == 1
    login.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("selection", ["not-a-uuid", "duplicate", "trailing_separator"])
async def test_invalid_resume_grants_clear_proof_before_any_native_connection(selection: str) -> None:
    choices = _choices()
    opened = 0

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        nonlocal opened
        opened += 1
        raise AssertionError("invalid consent must not open native recovery")

    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=_HandoffOwner().accept)
    identity = uuid4()
    raw = (
        f"{identity},{identity}"
        if selection == "duplicate"
        else f"{identity},"
        if selection == "trailing_separator"
        else selection
    )
    async with _Host(screen).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen.query_one("#runtime-login-resume-password", Input).value = "private-invalid-consent-proof"
        screen.query_one("#runtime-login-resume-grants", Input).value = raw
        screen.action_resume()
        assert opened == 0
        assert screen.query_one("#runtime-login-resume-password", Input).value == ""
        assert screen.query_one("#runtime-login-resume-grants", Input).value == ""
        assert not screen._busy and screen.is_mounted
        assert "private-invalid-consent-proof" not in screen.query_one("#runtime-login-status", PinnedStatusBar).message


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["unsupported", "credential_rejected"])
async def test_resume_typed_refusal_preserves_failed_close_for_unmount_retry(code: str) -> None:
    choices = _choices()
    recovery = _RecoveryClient(UUID(choices[0].profile_id))
    refusal = RuntimeFrontendRefusedError(code)
    recovery.recovery_failure = refusal
    recovery.close_failures_remaining = 1

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        return recovery

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    async with _Host(screen).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen.query_one("#runtime-login-resume-password", Input).value = "private-refused-recovery-proof"
        screen.action_resume()
        await _until(pilot, lambda: recovery.close_calls == 1 and not screen._busy)
        assert recovery.resume_calls == 1 and not recovery.closed
        assert isinstance(refusal.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
        status = screen.query_one("#runtime-login-status", PinnedStatusBar)
        assert code in status.message
        assert (
            "private-refused-recovery-proof" not in status.message
            and "private-reference-close-canary" not in status.message
        )
        assert recovery.proof_buffer is not None and not any(recovery.proof_buffer)
        assert not screen.query_one("#runtime-login-resume", Button).disabled
        assert owner.accepted is None
    assert recovery.closed and recovery.close_calls == 2 and recovery.resume_calls == 1


@pytest.mark.asyncio
async def test_resume_timeout_fences_mutation_replay_while_separate_login_remains_available() -> None:
    choices = _choices()
    recovery = _RecoveryClient(UUID(choices[0].profile_id))
    recovery.recovery_failure = RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    opened = 0

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        nonlocal opened
        opened += 1
        return recovery

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    async with _Host(screen).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen.query_one("#runtime-login-resume-password", Input).value = "private-timeout-proof"
        screen.action_resume()
        await _until(pilot, lambda: recovery.closed and not screen._busy)
        assert "runtime_deadline_exceeded" in screen.query_one("#runtime-login-status", PinnedStatusBar).message
        assert screen.query_one("#runtime-login-resume", Button).disabled
        assert not screen.query_one("#runtime-login-submit", Button).disabled
        screen.query_one("#runtime-login-resume-password", Input).value = "private-blind-replay-proof"
        screen.action_resume()
        assert recovery.resume_calls == 1 and opened == 1
        assert screen.query_one("#runtime-login-resume-password", Input).value == ""
        assert owner.accepted is None and screen.is_mounted
    assert recovery.close_calls == 1


@pytest.mark.asyncio
async def test_successful_resume_failed_close_keeps_outcome_and_retries_only_cleanup() -> None:
    choices = _choices()
    recovery = _RecoveryClient(UUID(choices[0].profile_id))
    recovery.close_failures_remaining = 1

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        return recovery

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    async with _Host(screen).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen.query_one("#runtime-login-resume-password", Input).value = "synthetic-completed-recovery-proof"
        screen.action_resume()
        await _until(pilot, lambda: recovery.close_calls == 1 and not screen._busy)
        status = screen.query_one("#runtime-login-status", PinnedStatusBar)
        assert status.tone == "warning" and "runtime_unavailable" in status.message
        assert "private-reference-close-canary" not in status.message
        assert recovery.resume_calls == 1 and not recovery.closed
        assert owner.accepted is None and screen.is_mounted
    assert recovery.closed and recovery.close_calls == 2 and recovery.resume_calls == 1


@pytest.mark.asyncio
async def test_cancelled_resume_keeps_body_refusal_and_failed_close_until_unmount_retry() -> None:
    choices = _choices()
    recovery = _RecoveryClient(UUID(choices[0].profile_id))
    refusal = RuntimeFrontendRefusedError("credential_rejected")
    recovery.recovery_failure = refusal
    recovery.close_failures_remaining = 1
    recovery.release.clear()

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        return recovery

    owner = _HandoffOwner()
    screen = RuntimeLoginScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    proof = bytearray(b"private-cancelled-recovery-proof")
    async with _Host(screen).run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        task = asyncio.create_task(screen._resume_attempt(recovery.profile_id, proof, frozenset()))
        await _until(pilot, recovery.started.is_set)
        task.cancel()
        task.cancel()
        assert not task.done() and recovery.close_calls == 0
        recovery.release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
        assert caught.value.__dict__.get("body_error") is refusal
        assert isinstance(caught.value.__dict__.get("cleanup_error"), AsyncResourceCleanupError)
        assert not any(proof) and recovery.close_calls == 1 and not recovery.closed
        assert owner.accepted is None
    assert recovery.closed and recovery.close_calls == 2 and recovery.resume_calls == 1


@pytest.mark.asyncio
async def test_unmount_during_resume_drains_native_call_before_failed_close_retry() -> None:
    choices = _choices()
    recovery = _RecoveryClient(UUID(choices[0].profile_id))
    recovery.close_failures_remaining = 1
    recovery.release.clear()

    async def open_client(_profile_id: UUID) -> RuntimeFrontendClient:
        return recovery

    owner = _HandoffOwner()
    screen = _UnmountNotifiedScreen(choices=choices, open_client=open_client, accept_handoff=owner.accept)
    host = _Host(screen)
    async with host.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen.query_one("#runtime-login-resume-password", Input).value = "private-unmount-recovery-proof"
        screen.action_resume()
        await _until(pilot, recovery.started.is_set)
        host.pop_screen()
        await asyncio.wait_for(screen.unmounting.wait(), 2)
        assert recovery.close_calls == 0
        recovery.release.set()
        await _until(pilot, lambda: recovery.closed)
        assert recovery.proof_buffer is not None and not any(recovery.proof_buffer)
        assert owner.accepted is None
    assert recovery.close_calls == 2 and recovery.resume_calls == 1
