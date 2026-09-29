"""A TUI login handoff remains owned through root failure and normal exit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import override
from uuid import UUID, uuid4

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, Select

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.operations.registry import OperationFrontendProjection
from ....application.runtime.profile_access import RuntimeProfileStatus
from ....application.user_profile.access_contracts import AccessScope, AuthorityState, Availability, ProfileAccessStatus
from ....application.user_profile.login_interaction import ProfileLoginChoice
from ..runtime_admission import runtime_login_session
from ..secret.runtime_login import RuntimeLoginMethod

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
