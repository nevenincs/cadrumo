"""Scripted clients and Textual hosts shared by the runtime login tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Event, get_ident
from typing import override
from uuid import UUID, uuid4

from textual.app import App
from textual.await_complete import AwaitComplete
from textual.pilot import Pilot
from textual.widgets import Input, Select

from cadrumo.application.user_profile.login_interaction import ProfileLoginChoice
from cadrumo.core.async_cleanup import close_async_resources
from cadrumo.core.operations import OperationFrontendProjection
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.entrypoints.tui.tests.settling import SETTLE_TIMEOUT_SECONDS, settle_until
from cadrumo_client.contracts.access_refusals import ProfileAccessStatus
from cadrumo_client.contracts.access_vocabulary import AccessScope, AuthorityState, Availability, EffectiveScopeSummary
from cadrumo_client.contracts.automation_lifecycle import AutomationResumeReceipt
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.contracts.session_events import LifecycleNotice
from cadrumo_client.contracts.sign_in_outcomes import ProfileReceiptRefusedError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .....frontend.tui.secret.runtime_login import RuntimeLoginScreen
from .....frontend.tui.secret.runtime_login_contracts import (
    RuntimeClientOpener,
    RuntimeCredentialClientOpener,
    RuntimeLoginAcceptor,
    RuntimeLoginHandoff,
    RuntimeLoginMethod,
)


class ScriptedClient(FrontendClient):
    """An explicit UI fault port; native admission has separate acceptance."""

    @override
    def subscribe_lifecycle_notices(self, receive: Callable[[LifecycleNotice], None]) -> Callable[[], None]:
        return lambda: None

    def __init__(self, profile_id: UUID) -> None:
        self._profile_id = profile_id
        self._frontend = OperationFrontendProjection.TUI
        self._session_id: UUID | None = None
        self.password_calls = 0
        self.persistence_requests: list[bool] = []
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

    def _login_fault(self, proof: bytearray, *, api_key: bool) -> ProfileStatus:
        self.proof_buffer = proof
        self.proof_before_wipe = bytes(proof)
        self.started.set()
        if not self.release.wait(SETTLE_TIMEOUT_SECONDS):
            raise TimeoutError("test login release was not signalled")
        if self.refuse:
            raise FrontendRefusedError("credential_rejected")
        return self._status(api_key=api_key)

    def _status(self, *, api_key: bool) -> ProfileStatus:
        """Return only the synthetic admitted status for this fault port."""
        self._session_id = uuid4()
        return ProfileStatus(
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
                effective_scope=EffectiveScopeSummary.summarize(
                    AccessScope(
                        operations=frozenset(),
                        actions=frozenset(),
                        disclosures=frozenset(),
                        periods=None,
                        allow_period_independent=True,
                        allow_delegation=False,
                    )
                ),
                denial=None,
            ),
        )

    @override
    def login_password(self, secret: bytearray, *, timeout: float = 20, persist_receipt: bool = False) -> ProfileStatus:
        self.persistence_requests.append(persist_receipt)
        self.password_calls += 1
        return self._login_fault(secret, api_key=False)

    @override
    def login_api_key(self, secret: bytearray, *, timeout: float = 20) -> ProfileStatus:
        self.api_calls += 1
        return self._login_fault(secret, api_key=True)

    @override
    def resume_receipt(self, *, timeout: float = 20, hand_over: bool = False) -> ProfileStatus:
        """Model existing protected-receipt availability without an input secret."""
        self.receipt_calls += 1
        self.receipt_thread = get_ident()
        self.started.set()
        if not self.release.wait(SETTLE_TIMEOUT_SECONDS):
            raise TimeoutError("test receipt release was not signalled")
        if self.receipt_refusal is not None:
            raise ProfileReceiptRefusedError(self.receipt_refusal)
        return self._status(api_key=False)

    @override
    def status(self, *, timeout: float = 5) -> ProfileStatus:
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


class ScriptedClientCleanup:
    """Explicit native-close boundary port for failed admission detector cases."""

    def __init__(self, client: ScriptedClient) -> None:
        self._client = client

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)


class ScriptedRecoveryClient(ScriptedClient):
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
        if not self.release.wait(SETTLE_TIMEOUT_SECONDS):
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


async def failed_reference_admission(client: ScriptedClient, refusal: FrontendRefusedError) -> FrontendClient:
    try:
        raise refusal
    except BaseException as error:
        await close_async_resources(
            ScriptedClientCleanup(client), task_name="test-reference-admission-close", primary_error=error
        )
        raise


class LoginHost(App[None]):
    def __init__(self, screen: RuntimeLoginScreen) -> None:
        super().__init__()
        self.login_screen = screen
        self.handoff: RuntimeLoginHandoff | None = None

    async def _present(self) -> None:
        self.handoff = await self.push_screen_wait(self.login_screen)

    def on_mount(self) -> None:
        self.run_worker(self._present())


class NoReceiverLoginHost(App[None]):
    def __init__(self, screen: RuntimeLoginScreen) -> None:
        super().__init__()
        self.login_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self.login_screen)


class HandoffOwner:
    def __init__(self, *, allow: bool = True) -> None:
        self.allow = allow
        self.accepted: RuntimeLoginHandoff | None = None

    def accept(self, handoff: RuntimeLoginHandoff) -> bool:
        if not self.allow or self.accepted is not None:
            return False
        self.accepted = handoff
        return True


class UnmountNotifiedScreen(RuntimeLoginScreen):
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


class RejectedDismissalScreen(RuntimeLoginScreen):
    @override
    def dismiss(self, result: RuntimeLoginHandoff | None = None) -> AwaitComplete:
        raise RuntimeError("test handoff callback was not accepted")


def login_choices() -> tuple[ProfileLoginChoice, ProfileLoginChoice]:
    return (
        ProfileLoginChoice(profile_id=str(uuid4()), label="First profile"),
        ProfileLoginChoice(profile_id=str(uuid4()), label="Second profile"),
    )


async def submit_stored_reference(pilot: Pilot[None], screen: RuntimeLoginScreen) -> None:
    """Choose the stored API reference method, enter a fresh reference and submit the screen."""
    screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.API_REFERENCE
    await settle_until(
        pilot,
        lambda: screen.query_one("#runtime-login-reference", Input).display,
        "screen.query_one('#runtime-login-reference', Input).display",
        workers=False,
    )
    screen.query_one("#runtime-login-reference", Input).value = str(uuid4())
    screen.action_submit()
