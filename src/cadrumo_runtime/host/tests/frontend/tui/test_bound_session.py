"""A bound session stays valid only while its identity, its runtime status and its expiry all hold."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from datetime import timedelta
from typing import override
from uuid import UUID, uuid4

import pytest
from textual.app import App

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessDenialCode,
    AccessScope,
    Availability,
    EffectiveScopeSummary,
    ProfileAccessStatus,
)
from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.transport.frontend_client import FrontendClient

from ....frontend.tui.bound_session import BoundSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TASK = "test-bound-session-status"


class _Client(FrontendClient):
    """A client whose identity and status reply the test sets directly."""

    def __init__(self) -> None:
        self._profile_id = uuid4()
        self._session_id = uuid4()
        self._frontend = OperationFrontendProjection.TUI
        self.reported_profile_id: UUID = self._profile_id
        self.reported_session_id: UUID = self._session_id
        self.expires_at = now() + timedelta(minutes=5)
        self.denial: AccessDenialCode | None = None
        self.failure: Exception | None = None
        self.retirement: Callable[[], None] | None = None

    def rebind_session(self) -> None:
        self._session_id = uuid4()

    @override
    def subscribe_session_retirement(self, receive: Callable[[], None]) -> Callable[[], None]:
        self.retirement = receive

        def unsubscribe() -> None:
            self.retirement = None

        return unsubscribe

    @override
    def status(self, *, timeout: float = 5) -> ProfileStatus:
        if self.failure is not None:
            raise self.failure
        return ProfileStatus(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            status=ProfileAccessStatus(
                connected=True,
                credential_authenticated=True,
                profile_id=self.reported_profile_id,
                session_id=self.reported_session_id,
                session_expires_at=self.expires_at,
                grant_state=None,
                grant_expires_at=None,
                grant_valid=False,
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
                denial=self.denial,
            ),
        )


def test_identity_holds_until_the_client_is_bound_to_another_session() -> None:
    client = _Client()
    binding = BoundSession(client)

    assert binding.identity_holds()
    client.rebind_session()
    assert not binding.identity_holds()
    assert binding.lifetime_ended()


def test_lifetime_ends_only_when_a_known_expiry_has_passed() -> None:
    client = _Client()

    assert not BoundSession(client).lifetime_ended()
    assert not BoundSession(client, known_expires_at=now() + timedelta(minutes=1)).lifetime_ended()
    assert BoundSession(client, known_expires_at=now() - timedelta(seconds=1)).lifetime_ended()


@pytest.mark.asyncio
async def test_a_confirmed_status_records_the_expiry_the_runtime_reported() -> None:
    client = _Client()
    binding = BoundSession(client)

    assert await binding.confirm_with_runtime(task_name=_TASK)
    assert binding.known_expires_at == client.expires_at


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["other_profile", "other_session", "expired", "denied", "failed"])
async def test_a_status_that_does_not_match_the_pinned_session_is_not_confirmed(fault: str) -> None:
    client = _Client()
    binding = BoundSession(client)
    if fault == "other_profile":
        client.reported_profile_id = uuid4()
    elif fault == "other_session":
        client.reported_session_id = uuid4()
    elif fault == "expired":
        client.expires_at = now() - timedelta(seconds=1)
    elif fault == "denied":
        client.denial = AccessDenialCode.PROFILE_MISMATCH
    else:
        client.failure = RuntimeError("runtime unreachable")

    assert not await binding.confirm_with_runtime(task_name=_TASK)
    assert binding.known_expires_at is None


@pytest.mark.asyncio
async def test_a_client_rebound_before_the_question_is_not_asked_at_all() -> None:
    client = _Client()
    binding = BoundSession(client)
    client.rebind_session()
    client.failure = AssertionError("the runtime must not be asked about a session the client left")

    assert not await binding.confirm_with_runtime(task_name=_TASK)


@pytest.mark.asyncio
async def test_a_watch_checks_at_the_known_expiry_and_on_a_pushed_retirement_but_never_on_an_interval() -> None:
    client = _Client()
    binding = BoundSession(client, known_expires_at=now() + timedelta(milliseconds=500))
    checks: list[float] = []
    app: App[None] = App()
    async with app.run_test() as pilot:
        stop = binding.watch(app, lambda: checks.append(now().timestamp()))
        await asyncio.sleep(0.3)
        await pilot.pause()
        assert checks == [], "the watch checked before anything could have ended"
        await asyncio.sleep(0.6)
        await pilot.pause()
        assert len(checks) == 1, "the known expiry was not checked once it passed"

        retirement = client.retirement
        assert retirement is not None
        # The client pushes retirement from its reader thread.
        pushing = threading.Thread(target=retirement)
        pushing.start()
        pushing.join()
        await pilot.pause()
        assert len(checks) == 2, "a pushed retirement did not reach the owner's loop"

        with pytest.raises(InternalInvariantError):
            binding.watch(app, lambda: None)

        stop()
        assert client.retirement is None
        binding.known_expires_at = now() + timedelta(milliseconds=100)
        await asyncio.sleep(0.3)
        await pilot.pause()
        assert len(checks) == 2, "a stopped watch still checked"
