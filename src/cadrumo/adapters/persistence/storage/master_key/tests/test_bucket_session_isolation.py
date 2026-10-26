"""The per-test bucket-session boundary restores each binding layer it observed."""

from __future__ import annotations

from contextvars import Context
from datetime import timedelta

import pytest

from ......core.time.clock import now
from ..active_session import (
    activate_session,
    bind_active_bucket_session,
    close_active_bucket_session,
    current_active_bucket_session,
)
from ..bucket_session import BucketSession
from .bucket_session_isolation import evict_bucket_sessions_bound_since, observe_bucket_session_binding
from .session_scope import suspend_active_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _open_session(bucket_id: str) -> BucketSession:
    opened_at = now()
    return BucketSession.open_resumed(
        bucket_id=bucket_id,
        dek=b"I" * 32,
        idle_minutes=30,
        opened_at=opened_at,
        idle_deadline=opened_at + timedelta(minutes=30),
        absolute_deadline=opened_at + timedelta(minutes=240),
    )


def _published() -> BucketSession | None:
    return Context().run(current_active_bucket_session)


def test_a_login_under_a_scoped_runtime_does_not_publish_that_runtime_past_its_scope() -> None:
    """The leak this boundary exists for: the scoped runtime must not become the process's session."""
    runtime = _open_session("0b8f5a2e-6c1d-4e7f-9a3b-2c4d6e8f0a1b")
    login = _open_session("5d7e9f1a-3b5c-4d6e-8f0a-1b2c3d4e5f6a")
    try:
        with activate_session(runtime):
            before = observe_bucket_session_binding()
            bind_active_bucket_session(login)

            assert evict_bucket_sessions_bound_since(before) == (login,)
            assert login.sealed
            assert current_active_bucket_session() is runtime
            assert _published() is None
        assert current_active_bucket_session() is None
    finally:
        runtime.close()
        login.close()


def test_a_session_published_outside_this_context_is_evicted() -> None:
    """A login bound from a thread worker is published without being visible here."""
    login = _open_session("7f9a1b3c-5d7e-4f8a-9b1c-3d5e7f9a1b3c")
    try:
        with suspend_active_session():
            before = observe_bucket_session_binding()
            Context().run(bind_active_bucket_session, login)
            assert current_active_bucket_session() is None

            assert evict_bucket_sessions_bound_since(before) == (login,)
        assert login.sealed
        assert _published() is None
    finally:
        login.close()


def test_an_inherited_session_is_left_open_and_bound() -> None:
    inherited = _open_session("9b1c3d5e-7f9a-4b1c-8d3e-5f7a9b1c3d5e")
    bind_active_bucket_session(inherited)
    try:
        before = observe_bucket_session_binding()

        assert evict_bucket_sessions_bound_since(before) == ()
        assert not inherited.sealed
        assert current_active_bucket_session() is inherited
        assert _published() is inherited
    finally:
        close_active_bucket_session()
