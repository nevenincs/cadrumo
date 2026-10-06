"""Session-end containment ordering and retained parent settlement evidence."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast, override
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimeExitReason, RuntimeShutdownIncompleteError
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.runtime.profile_host import RuntimeProfileHost
from cadrumo.entrypoints.runtime.shutdown import RuntimeStop

from .test_runtime_drain_refusal import _EmptyApprovals, _FailedWorker, _Owner

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("confirmed", [False, True])
def test_session_end_settles_only_after_native_confirmation(tmp_path: Path, confirmed: bool) -> None:
    profile_id = uuid4()
    stop = RuntimeStop()
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="test-storage",
        runtime_boot_id=uuid4(),
        stop=stop,
    )
    profiles.prepare_registry()
    phases: list[str] = []

    class Worker(_FailedWorker):
        identity = ProfileWorkerIdentity(
            worker_id=uuid4(),
            runtime_boot_id=profiles.boot,
            binding=ProfileAccessBinding(
                profile_id=profile_id,
                installation_id=uuid4(),
                os_owner_id="test-owner",
                custody_generation=1,
                dek_epoch=uuid4(),
            ),
        )

        @override
        def drain(self, *, deadline: float) -> None:
            raise AssertionError("session end must terminate before protocol drain")

        @override
        def close(self, *, deadline: float) -> None:
            assert profiles._closed and stop.is_set()
            phases.append("contain")
            if not confirmed:
                raise RuntimeError("native containment unconfirmed")
            super().close(deadline=deadline)

        @override
        def settle(self, *, deadline: float) -> None:
            assert self.contained
            phases.append("callbacks")
            super().settle(deadline=deadline)

    worker = Worker()
    profiles._profiles[profile_id] = cast(
        RuntimeProfileHost,
        SimpleNamespace(
            owner=_Owner(worker),
            approvals=_EmptyApprovals(),
        ),
    )
    stop.request(RuntimeExitReason.SESSION_END_SETTLE)
    result = profiles.drain(deadline=time.monotonic() + 2)
    assert result.receipts == ()
    assert result.missing_receipts == (profile_id,)
    if confirmed:
        assert phases == ["contain", "callbacks"]
        assert result.parent_settled_profiles == (profile_id,)
        assert not result.lacks_settlement_evidence
        assert result.uncontained == result.unsettled == ()
        assert profiles._profiles == {}
    else:
        assert phases == ["contain"]
        assert result.parent_settled_profiles == ()
        assert result.lacks_settlement_evidence
        assert result.uncontained == (profile_id,)
        assert profile_id in profiles._profiles


def test_missing_registry_retains_contained_worker_for_settlement_retry(tmp_path: Path) -> None:
    # The registry is a required startup fact; losing it cannot be treated as
    # an empty operation inventory even after native containment succeeds.
    stop, profile_id = RuntimeStop(), uuid4()
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="test-storage",
        runtime_boot_id=uuid4(),
        stop=stop,
    )
    worker = _FailedWorker()
    profiles._profiles[profile_id] = cast(
        RuntimeProfileHost,
        SimpleNamespace(
            owner=_Owner(worker),
            approvals=_EmptyApprovals(),
        ),
    )
    stop.request(RuntimeExitReason.SESSION_END_SETTLE)
    result = profiles.drain(deadline=time.monotonic() + 2)
    assert worker.contained
    assert result.parent_settled_profiles == ()
    assert result.unsettled == (profile_id,)
    assert profile_id in profiles._profiles


def test_pending_parent_settlement_retains_original_attempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from cadrumo.entrypoints.runtime import profile_connection_drain

    entered, release = Event(), Event()
    attempts = []
    stop, profile_id = RuntimeStop(), uuid4()
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="test-storage",
        runtime_boot_id=uuid4(),
        stop=stop,
    )
    profiles.prepare_registry()
    worker = _FailedWorker()
    identity = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=profiles.boot,
        binding=ProfileAccessBinding(
            profile_id=profile_id,
            installation_id=uuid4(),
            os_owner_id="test-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )
    # Fault only the native worker boundary and delayed storage completion.
    owned_worker = SimpleNamespace(close=worker.close, settle=worker.settle, identity=identity)
    profiles._profiles[profile_id] = cast(
        RuntimeProfileHost,
        SimpleNamespace(
            owner=_Owner(cast(_FailedWorker, owned_worker)),
            approvals=_EmptyApprovals(),
        ),
    )

    async def pending(**_inputs: object) -> None:
        assert worker.contained
        attempts.append(identity.worker_id)
        entered.set()
        await asyncio.to_thread(release.wait)

    monkeypatch.setattr(profile_connection_drain, "settle_terminated_worker_operations", pending)
    stop.request(RuntimeExitReason.SESSION_END_SETTLE)
    try:
        first = profiles.drain(deadline=time.monotonic() + 0.1)
        assert entered.wait(timeout=1)
        assert first.unsettled == (profile_id,)
        assert profiles._drain_records is not None
        record = profiles._drain_records[profile_id]
        original = record.settlement
        assert original is not None and original.is_alive()
        with pytest.raises(RuntimeShutdownIncompleteError):
            profiles.close()
        second = profiles.drain(deadline=time.monotonic() + 0.1)
        assert second.unsettled == (profile_id,)
        assert record.settlement is original
        assert attempts == [identity.worker_id]
    finally:
        release.set()
    original.join(timeout=2)
    completed = profiles.drain(deadline=time.monotonic() + 2)
    assert completed.unsettled == ()
    assert completed.parent_settled_profiles == (profile_id,)
    assert attempts == [identity.worker_id]
