"""Real installed workers and synthetic encrypted profiles, without a native key store."""

from __future__ import annotations

import sys
import time
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import (
    AccessSession,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError
from cadrumo.core.bucket_pointer import read_pointer
from cadrumo.core.time.clock import now

from ..profile_worker import ProfileWorkerProcess
from .profile_worker_support import PROFILE_INPUT, changed, lease, worker_profiles

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.fixture
def profiles(tmp_path: Path):
    with worker_profiles(tmp_path) as subjects:
        yield subjects


def test_concurrent_profiles_never_retarget_and_disconnect_is_isolated(profiles) -> None:
    root, ((first, first_key), (second, second_key)) = profiles
    with ExitStack() as cleanup:
        a = ProfileWorkerProcess(first, storage_root=root)
        cleanup.callback(a.close)
        b = ProfileWorkerProcess(second, storage_root=root)
        cleanup.callback(b.close)
        a_lease, b_lease = lease(first), lease(second)
        a_buffer, b_buffer = bytearray(first_key), bytearray(second_key)
        a.install(a_lease, a_buffer)
        b.install(b_lease, b_buffer)
        assert not any(a_buffer) and not any(b_buffer)
        assert a.status().sessions == (a_lease.session_id,)
        assert b.status().sessions == (b_lease.session_id,)
        # A foreign profile's valid DEK cannot switch this process to B.
        with pytest.raises(AutomationCustodyError):
            a.install(b_lease, bytearray(second_key))
        assert a.status().sessions == (a_lease.session_id,)
        assert b.status().sessions == (b_lease.session_id,)
        b.retire(b_lease.session_id)
        assert not b.status().sessions
        fresh = lease(second)
        b.install(fresh, bytearray(second_key))
        assert b.status().sessions == (fresh.session_id,)


def test_worker_rejects_wrong_dek_before_acknowledging_custody(profiles) -> None:
    root, ((identity, key), (_other, wrong_key)) = profiles
    worker = ProfileWorkerProcess(identity, storage_root=root)
    try:
        secret = bytearray(wrong_key)
        with pytest.raises(AutomationCustodyError):
            worker.install(lease(identity), secret)
        assert not any(secret)
        admitted = lease(identity)
        worker.install(admitted, bytearray(key))
        assert worker.status().sessions == (admitted.session_id,)
    finally:
        worker.close()


def test_refresh_and_idle_expiry_release_only_the_affected_leases(profiles) -> None:
    root, ((identity, key), _) = profiles
    worker = ProfileWorkerProcess(identity, storage_root=root)
    try:
        short, independent = lease(identity, seconds=2), lease(identity)
        worker.install(short, bytearray(key))
        worker.install(independent, bytearray(key))
        refreshed = changed(
            short, issued_at=now(), issued_monotonic=time.monotonic(), expires_at=now() + timedelta(seconds=4)
        )
        worker.refresh(refreshed)
        worker.retire(independent.session_id)
        assert worker.status().sessions == (short.session_id,)
        deadline = time.monotonic() + 6
        while worker.status().sessions and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not worker.status().sessions
        with pytest.raises(AutomationCustodyError):
            worker.refresh(
                changed(
                    refreshed,
                    issued_at=now(),
                    issued_monotonic=time.monotonic(),
                    expires_at=now() + timedelta(seconds=30),
                )
            )
    finally:
        worker.close()


def test_password_candidate_does_not_replace_agents_or_select_another_profile(profiles) -> None:
    root, ((identity, key), _) = profiles
    selected = read_pointer(root)
    worker = ProfileWorkerProcess(identity, storage_root=root)
    try:
        api = lease(identity)
        worker.install(api, bytearray(key))
        password = bytearray(PROFILE_INPUT.encode())
        with worker.authenticate_human(password) as outcome:
            assert outcome.bucket_id == str(identity.binding.profile_id) and not outcome.session_persisted
            assert worker.status().sessions == (api.session_id,)
            human = AccessSession(
                session_id=uuid4(),
                binding=identity.binding,
                profile_lock_generation=0,
                runtime_boot_id=identity.runtime_boot_id,
                connection_id=uuid4(),
                client_id=uuid4(),
                kind=SessionKind.HUMAN,
                originating_login_id="synthetic-login",
                state=SessionState.ACTIVE,
                scope=api.scope,
                issued_at=now(),
                issued_monotonic=time.monotonic(),
                expires_at=min(outcome.idle_deadline, outcome.absolute_deadline),
            )
            worker.bind_human(human)
        assert not any(password)
        assert set(worker.status().sessions) == {api.session_id, human.session_id}
        worker.retire(human.session_id)
        assert worker.status().sessions == (api.session_id,)
        wrong = bytearray(b"wrong-synthetic-worker-input")
        with pytest.raises(AutomationCustodyError), worker.authenticate_human(wrong):
            pytest.fail("incorrect password must not create a candidate")
        assert not any(wrong)
        assert worker.status().sessions == (api.session_id,)
        assert read_pointer(root) == selected
    finally:
        worker.close()
