"""Runtime account controls retain the exact admitted TUI lease."""

from __future__ import annotations

import asyncio
import threading
from typing import cast, override
from uuid import UUID, uuid4

import pytest

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.profile_password_rotation import ProfileRotationCompletion
from ....application.operations.registry import OperationFrontendProjection
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.profile_access import RuntimeSessionsLocked
from ....application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
from .. import runtime_account
from ..account import (
    AccountDirectSessionActionV1,
    AccountFactoriesV1,
    AccountProfileFactoryV1,
    AccountRecomposeReasonV1,
)
from ..runtime_access_management import RuntimeAccessManagementScreen
from ..runtime_account import compose_runtime_account_factories
from ..secret.passphrase import PassphraseScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _StrictClient(RuntimeFrontendClient):
    """A lease-aware fault port, without claiming native security acceptance."""

    def __init__(self) -> None:
        self._profile_id = uuid4()
        self._test_session_id = uuid4()
        self._frontend = OperationFrontendProjection.TUI
        self.lock_calls = 0
        self.lock_thread: int | None = None
        self.lock_started = threading.Event()
        self.release_lock = threading.Event()
        self.release_lock.set()
        self.lock_finished = threading.Event()
        self.acknowledge_original = True
        self.close_calls = 0

    @property
    @override
    def profile_id(self) -> UUID:
        """Expose the selected profile."""
        return self._profile_id

    @property
    @override
    def session_id(self) -> UUID:
        """Expose the current lease, which a test may rebind."""
        return self._test_session_id

    @property
    @override
    def frontend(self) -> OperationFrontendProjection:
        """Expose the current frontend, which a test may rebind."""
        return self._frontend

    @override
    def lock(self, *, timeout: float = 5) -> RuntimeSessionsLocked:
        """Record the owning thread and return an exact or faulted receipt."""
        self.lock_calls += 1
        self.lock_thread = threading.get_ident()
        original = self._test_session_id
        self.lock_started.set()
        if not self.release_lock.wait(5):
            raise TimeoutError("test lock was not released")
        self.lock_finished.set()
        return RuntimeSessionsLocked(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            session_ids=(original,) if self.acknowledge_original else (uuid4(),),
        )

    @override
    def close(self) -> None:
        self.close_calls += 1


def _factories(client: _StrictClient) -> AccountFactoriesV1:
    async def open_recovery_client() -> RuntimeFrontendClient:
        return client

    def unavailable_profile(_context: object) -> object:
        raise AssertionError("the unrelated profile screen must not be opened")

    return compose_runtime_account_factories(
        client,
        profile=cast(AccountProfileFactoryV1, unavailable_profile),
        open_recovery_client=open_recovery_client,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action_name", "reason"),
    [
        ("sign_out", AccountRecomposeReasonV1.SIGNED_OUT),
        ("change_user", AccountRecomposeReasonV1.CHANGE_USER),
    ],
)
async def test_direct_actions_lock_original_session_once_off_ui_thread(
    action_name: str, reason: AccountRecomposeReasonV1
) -> None:
    client = _StrictClient()
    factories = _factories(client)
    action = getattr(factories, action_name)()
    assert isinstance(action, AccountDirectSessionActionV1)

    outcome = await action.complete()

    assert outcome.reason is reason
    assert outcome.profile_id is None and outcome.profile_label is None
    assert client.lock_calls == 1
    assert client.lock_thread != threading.get_ident()


@pytest.mark.asyncio
async def test_rebound_lease_or_frontend_cannot_close_or_borrow_access() -> None:
    client = _StrictClient()
    factories = _factories(client)
    action = factories.sign_out()
    assert isinstance(action, AccountDirectSessionActionV1)

    client._test_session_id = uuid4()
    with pytest.raises(RuntimeRefusalError) as refusal:
        await action.complete()
    assert refusal.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert client.lock_calls == 0
    access = factories.access
    assert access is not None
    with pytest.raises(RuntimeRefusalError):
        access()

    client = _StrictClient()
    factories = _factories(client)
    client._frontend = OperationFrontendProjection.CLI
    with pytest.raises(RuntimeRefusalError) as refusal:
        await factories.change_user().complete()
    assert refusal.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert client.lock_calls == 0
    access = factories.access
    assert access is not None
    with pytest.raises(RuntimeRefusalError):
        access()
    with pytest.raises(RuntimeRefusalError) as refusal:
        _factories(client)
    assert refusal.value.reason is RuntimeRefusalCode.INVALID_FRAME


@pytest.mark.asyncio
async def test_missing_original_session_acknowledgement_refuses_recomposition() -> None:
    client = _StrictClient()
    client.acknowledge_original = False
    action = _factories(client).sign_out()
    assert isinstance(action, AccountDirectSessionActionV1)

    with pytest.raises(RuntimeRefusalError) as refusal:
        await action.complete()

    assert refusal.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert client.lock_calls == 1


@pytest.mark.asyncio
async def test_cancelled_direct_action_waits_for_blocked_lock_to_finish() -> None:
    client = _StrictClient()
    client.release_lock.clear()
    action = _factories(client).sign_out()
    assert isinstance(action, AccountDirectSessionActionV1)
    pending = asyncio.ensure_future(action.complete())
    try:
        assert await asyncio.to_thread(client.lock_started.wait, 5)
        pending.cancel()
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(pending), 0.02)
        assert not client.lock_finished.is_set()
    finally:
        client.release_lock.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(pending, 5)
    assert client.lock_calls == 1
    assert client.lock_finished.is_set()


def test_password_and_access_screens_bind_exact_borrowed_client() -> None:
    client = _StrictClient()
    factories = _factories(client)

    password = factories.password
    assert password is not None
    assert isinstance(password(), PassphraseScreen)
    access = factories.access
    assert access is not None
    screen = access()
    assert isinstance(screen, RuntimeAccessManagementScreen)
    assert screen._client is client
    assert screen._profile_id == client.profile_id
    assert screen._session_id == client.session_id

    client._test_session_id = uuid4()
    with pytest.raises(RuntimeRefusalError) as refusal:
        password()
    assert refusal.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED


def test_password_factory_borrows_original_and_supplies_distinct_fresh_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    client, fresh = _StrictClient(), _StrictClient()
    fresh._profile_id = client.profile_id

    async def open_fresh() -> RuntimeFrontendClient:
        return fresh

    def unavailable_profile(_context: object) -> object:
        raise AssertionError("password factory must not open the profile screen")

    outcome = ProfilePassphraseRotationOutcome(
        profile_id=str(client.profile_id),
        password_generation=2,
        dek_epoch_preserved=True,
        recovery_enrollment_retained=False,
    )

    def rotation(
        borrowed: RuntimeFrontendClient,
        *,
        current_passphrase: bytearray,
        new_passphrase: bytearray,
        new_passphrase_confirmation: bytearray,
        fresh_client,
    ) -> ProfileRotationCompletion:
        assert borrowed is client
        assert bytes(current_passphrase) == b"current-password"
        assert bytes(new_passphrase) == bytes(new_passphrase_confirmation) == b"replacement-password"
        reader = fresh_client()
        assert reader is fresh and reader is not client
        reader.close()
        return ProfileRotationCompletion(operation_id="a" * 64, outcome=outcome)

    monkeypatch.setattr(runtime_account, "run_profile_password_rotation", rotation)
    factories = compose_runtime_account_factories(
        client,
        profile=cast(AccountProfileFactoryV1, unavailable_profile),
        open_recovery_client=open_fresh,
    )
    password = factories.password
    assert password is not None
    attempt = password()._rotate_passphrase("current-password", "replacement-password", "replacement-password")
    assert attempt.outcome == outcome
    assert client.close_calls == 0 and fresh.close_calls == 1
