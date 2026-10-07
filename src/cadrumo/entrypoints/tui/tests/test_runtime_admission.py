"""A TUI login handoff remains owned through root failure and normal exit."""

from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager, AbstractContextManager, nullcontext
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import override
from uuid import UUID, uuid4

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, Select

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....adapters.local_runtime.runtime_transport_cleanup import RuntimeTransportCleanup
from ....application.operations.registry import OperationFrontendProjection, OperationRegistry
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.profile_access import RuntimeProfileStatus
from ....application.user_profile.access_contracts import AccessScope, AuthorityState, Availability, ProfileAccessStatus
from ....application.user_profile.automation_operations import (
    build_automation_operation_definitions,
    build_automation_operation_registrations,
)
from ....application.user_profile.login_interaction import (
    ProfileLoginChoice,
    ProfileLoginInventoryState,
    ProfileLoginInventoryV1,
)
from ....core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from .. import installed_session
from ..runtime_admission import runtime_login_session
from ..secret.runtime_login_contracts import (
    RuntimeLoginHandoff,
    RuntimeLoginMethod,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _RootFailureError(Exception):
    pass


class _OwnedClient(RuntimeFrontendClient):
    """Synthetic transport outcome; only frontend resource ownership is tested."""

    def __init__(self, profile_id: UUID) -> None:
        self._profile_id = profile_id
        self._frontend = OperationFrontendProjection.TUI
        self._session_id: UUID | None = None
        self.closed = 0

    @override
    def login_password(
        self, secret: bytearray, *, timeout: float = 20, persist_receipt: bool = False
    ) -> RuntimeProfileStatus:
        assert not persist_receipt
        assert secret == b"synthetic-proof"
        secret[:] = bytes(len(secret))
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
                session_expires_at=datetime.now(UTC) + timedelta(minutes=5),
                grant_state=None,
                grant_expires_at=None,
                grant_valid=False,
                profile_bound=True,
                storage=Availability.AVAILABLE,
                automation_custody=Availability.UNAVAILABLE,
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
    def close(self) -> None:
        self.closed += 1
        self._session_id = None

    @override
    def status(self, *, timeout: float = 5) -> RuntimeProfileStatus:
        """Return an admitted restricted session from the explicit reference opener."""
        return RuntimeProfileStatus(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            status=ProfileAccessStatus(
                connected=True,
                credential_authenticated=True,
                profile_id=self.profile_id,
                session_id=self.session_id,
                session_expires_at=datetime.now(UTC) + timedelta(minutes=5),
                grant_state=AuthorityState.ACTIVE,
                grant_expires_at=datetime.now(UTC) + timedelta(minutes=5),
                grant_valid=True,
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


@pytest.mark.asyncio
@pytest.mark.parametrize("root_fails", [False, True])
async def test_login_scope_keeps_one_exact_client_until_frontend_finishes(root_fails: bool) -> None:
    profile_id = uuid4()
    client = _OwnedClient(profile_id)

    async def open_client(selected: UUID) -> RuntimeFrontendClient:
        assert selected == profile_id
        return client

    async def sign_in(pilot: Pilot[object]) -> None:
        await pilot.resize_terminal(140, 60)
        await pilot.pause()
        pilot.app.screen.query_one("#runtime-login-credential", Input).value = "synthetic-proof"
        await pilot.click("#runtime-login-submit")

    seen = False
    try:
        async with runtime_login_session(
            choices=(ProfileLoginChoice(profile_id=str(profile_id), label="Owned profile"),),
            open_client=open_client,
            headless=True,
            auto_pilot=sign_in,
        ) as handoff:
            assert handoff is not None
            assert handoff.client is client
            assert handoff.profile_id == profile_id
            assert handoff.status.status.session_id == client.session_id
            assert client.closed == 0
            seen = True
            if root_fails:
                raise _RootFailureError()
    except _RootFailureError:
        assert root_fails
    assert seen
    assert client.closed == 1


@pytest.mark.asyncio
async def test_explicit_preselected_profile_resumes_before_password_prompt() -> None:
    profile_id = uuid4()

    class ResumeClient(_OwnedClient):
        @override
        def resume_receipt(self, *, timeout: float = 20) -> RuntimeProfileStatus:
            return super().login_password(bytearray(b"synthetic-proof"))

    client = ResumeClient(profile_id)

    async def open_client(selected: UUID) -> RuntimeFrontendClient:
        assert selected == profile_id
        return client

    async with asyncio.timeout(10):
        async with runtime_login_session(
            choices=(ProfileLoginChoice(profile_id=str(profile_id), label="Saved profile"),),
            preselected=str(profile_id),
            open_client=open_client,
            headless=True,
        ) as handoff:
            assert handoff is not None and handoff.method is RuntimeLoginMethod.RECEIPT
            assert handoff.client is client and client.closed == 0
    assert client.closed == 1


@pytest.mark.asyncio
async def test_cancelled_login_does_not_create_or_transfer_a_client() -> None:
    profile_id = uuid4()

    async def open_client(selected: UUID) -> RuntimeFrontendClient:
        raise AssertionError("abandoning the form must not open a connection")

    async def abandon(pilot: Pilot[object]) -> None:
        await pilot.pause()
        await pilot.press("escape")

    async with runtime_login_session(
        choices=(ProfileLoginChoice(profile_id=str(profile_id), label="Unused profile"),),
        open_client=open_client,
        headless=True,
        auto_pilot=abandon,
    ) as handoff:
        assert handoff is None


@pytest.mark.asyncio
async def test_stored_reference_handoff_stays_owned_through_restricted_session_scope() -> None:
    profile_id, reference = uuid4(), uuid4()
    client = _OwnedClient(profile_id)
    calls: list[tuple[UUID, UUID]] = []

    async def open_client(_selected: UUID) -> RuntimeFrontendClient:
        raise AssertionError("reference mode must not open the password connection")

    async def open_reference(selected: UUID, credential_reference: UUID) -> RuntimeFrontendClient:
        calls.append((selected, credential_reference))
        client._session_id = uuid4()
        return client

    async def sign_in(pilot: Pilot[object]) -> None:
        await pilot.resize_terminal(140, 60)
        await pilot.pause()
        pilot.app.screen.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.API_REFERENCE
        await pilot.pause()
        pilot.app.screen.query_one("#runtime-login-reference", Input).value = str(reference)
        await pilot.click("#runtime-login-submit")

    async with runtime_login_session(
        choices=(ProfileLoginChoice(profile_id=str(profile_id), label="Restricted profile"),),
        open_client=open_client,
        open_credential_client=open_reference,
        headless=True,
        auto_pilot=sign_in,
    ) as handoff:
        assert handoff is not None and handoff.method is RuntimeLoginMethod.API_REFERENCE
        assert handoff.client is client and handoff.profile_id == profile_id
        assert handoff.status.status.grant_valid and client.closed == 0
    assert calls == [(profile_id, reference)]
    assert client.closed == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["normal", "failure", "cancellation"])
async def test_accepted_handoff_failed_close_retains_owner_and_exact_body(body: str) -> None:
    profile_id = uuid4()

    class FailingClient(_OwnedClient):
        def __init__(self) -> None:
            super().__init__(profile_id)
            self.attempts = 0
            self.refuse_close = True
            self.close_error = OSError("synthetic persistent native release failure")

        @override
        def close(self) -> None:
            self.attempts += 1
            if self.refuse_close:
                raise self.close_error
            super().close()

    client = FailingClient()
    primary = (
        asyncio.CancelledError("synthetic frontend cancellation")
        if body == "cancellation"
        else _RootFailureError("synthetic frontend body failure")
        if body == "failure"
        else None
    )

    async def open_client(selected: UUID) -> RuntimeFrontendClient:
        assert selected == profile_id
        return client

    async def sign_in(pilot: Pilot[object]) -> None:
        await pilot.pause()
        await pilot.resize_terminal(140, 60)
        pilot.app.screen.query_one("#runtime-login-credential", Input).value = "synthetic-proof"
        await pilot.click("#runtime-login-submit")

    expected = type(primary) if primary is not None else AsyncResourceCleanupError
    with pytest.raises(expected) as caught:
        async with runtime_login_session(
            choices=(ProfileLoginChoice(profile_id=str(profile_id), label="Owned profile"),),
            open_client=open_client,
            headless=True,
            auto_pilot=sign_in,
        ) as handoff:
            assert handoff is not None and handoff.client is client
            assert handoff.profile_id == profile_id and client.closed == client.attempts == 0
            if primary is not None:
                raise primary
    if primary is not None:
        assert caught.value is primary
        cleanup = primary.__dict__.get("async_cleanup_error")
        if not isinstance(cleanup, AsyncResourceCleanupError):
            cleanup = primary.__dict__.get("cleanup_error")
    else:
        cleanup = caught.value
    assert isinstance(cleanup, AsyncResourceCleanupError)
    assert client.attempts == 1 and client.closed == 0
    with pytest.raises(AsyncResourceCleanupError) as persistent:
        await cleanup.retry_cleanup()
    assert client.attempts == 2 and client.closed == 0
    client.refuse_close = False
    await persistent.value.retry_cleanup()
    assert client.attempts == 3 and client.closed == 1
    await cleanup.retry_cleanup()
    await persistent.value.retry_cleanup()
    assert client.attempts == 3 and client.closed == 1


@pytest.mark.parametrize("frontend_refusal", [False, True])
@pytest.mark.parametrize("attachment", [None, "async_cleanup_error", "cleanup_error"])
def test_installed_exit_mapping_preserves_cleanup_bearing_refusal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], frontend_refusal: bool, attachment: str | None
) -> None:
    profile_id = uuid4()
    primary = (
        RuntimeFrontendRefusedError("authentication_required")
        if frontend_refusal
        else RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    )

    class NativeRelease:
        def __init__(self) -> None:
            self.attempts = 0
            self.refuse_close = True

        def close(self) -> None:
            self.attempts += 1
            if self.refuse_close:
                raise OSError("synthetic retained native owner")

    native = NativeRelease()
    owner = RuntimeTransportCleanup(native)
    if attachment is not None:

        async def attach_cleanup() -> None:
            try:
                raise primary
            finally:
                await close_async_resources(owner, task_name="installed-tui-fault", primary_error=primary)

        with pytest.raises(type(primary)) as original:
            asyncio.run(attach_cleanup())
        assert original.value is primary
        cleanup = primary.__dict__.pop("async_cleanup_error")
        assert isinstance(cleanup, AsyncResourceCleanupError)
        primary.__dict__[attachment] = cleanup

    class RefusingLogin(AbstractAsyncContextManager[RuntimeLoginHandoff | None]):
        @override
        async def __aenter__(self) -> RuntimeLoginHandoff | None:
            raise primary

        @override
        async def __aexit__(
            self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
        ) -> None:
            return None

    def refuse_login(**_options: object) -> RefusingLogin:
        return RefusingLogin()

    def bootstrap_ports() -> AbstractContextManager[None]:
        return nullcontext()

    def release_bootstrap() -> None:
        return None

    def inventory() -> ProfileLoginInventoryV1:
        return ProfileLoginInventoryV1(
            state=ProfileLoginInventoryState.RECOGNIZED,
            choices=(ProfileLoginChoice(profile_id=str(profile_id), label="Synthetic profile"),),
            preselected_profile_id=str(profile_id),
        )

    definitions = build_automation_operation_definitions()
    registry = OperationRegistry(
        definitions=definitions,
        public_registrations=tuple(
            sorted(build_automation_operation_registrations(definitions), key=lambda row: row.contract.definition_id)
        ),
    )

    def operation_registry() -> OperationRegistry:
        return registry

    monkeypatch.setattr(installed_session, "profile_adapter_composition", bootstrap_ports)
    monkeypatch.setattr(installed_session, "close_active_profile_record_session", release_bootstrap)
    monkeypatch.setattr(installed_session, "close_active_bucket_session", release_bootstrap)
    monkeypatch.setattr(installed_session, "observe_profile_login_inventory", inventory)
    monkeypatch.setattr(installed_session, "build_production_operation_registry", operation_registry)
    monkeypatch.setattr(installed_session, "runtime_login_session", refuse_login)
    if attachment is None:
        assert installed_session.run_installed_workbench_session() == installed_session.SESSION_INVENTORY_UNAVAILABLE
        assert capsys.readouterr().err.strip() == (
            primary.reason if isinstance(primary, RuntimeFrontendRefusedError) else primary.reason.value
        )
        assert native.attempts == 0
    else:
        with pytest.raises(type(primary)) as caught:
            installed_session.run_installed_workbench_session()
        assert caught.value is primary and native.attempts == 1
        assert capsys.readouterr().err == ""
        retained = primary.__dict__.get(attachment)
        assert isinstance(retained, AsyncResourceCleanupError)
        native.refuse_close = False
        asyncio.run(retained.retry_cleanup())
        asyncio.run(retained.retry_cleanup())
        assert native.attempts == 2 and owner.released
