"""Absent worker receipts remain explicit after native containment attempts."""

from __future__ import annotations

import time
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from ..profile_connections import RuntimeProfileConnections
from ..profile_host import RuntimeProfileHost

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _FailedWorker:
    def __init__(self) -> None:
        self.contained = False
        self.settled = False

    def drain(self, *, deadline: float) -> None:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)

    def close(self, *, deadline: float) -> None:
        self.contained = True

    def settle(self, *, deadline: float) -> None:
        self.settled = True


class _Owner:
    def __init__(self, worker: _FailedWorker | None, *, construction_settled: bool = True) -> None:
        self.worker = worker
        self.construction_settled = construction_settled

    def begin_drain(self) -> _FailedWorker | None:
        return self.worker

    def settle(self, *, deadline: float) -> None:
        if self.worker is not None:
            self.worker.settle(deadline=deadline)

    def wait_construction(self, *, deadline: float) -> bool:
        if not self.construction_settled:
            Event().wait(timeout=max(0.0, deadline - time.monotonic()))
        return self.construction_settled


def test_missing_receipt_is_reported_after_containment(tmp_path: Path) -> None:
    stop, profile_id = Event(), uuid4()
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="test-storage",
        runtime_boot_id=uuid4(),
        stop=stop,
    )
    worker = _FailedWorker()
    profiles._profiles[profile_id] = cast(
        "RuntimeProfileHost",
        SimpleNamespace(store=SimpleNamespace(binding=SimpleNamespace(profile_id=profile_id)), owner=_Owner(worker)),
    )

    result = profiles.drain(deadline=time.monotonic() + 1)

    assert stop.is_set()
    assert result.receipts == ()
    assert result.missing_receipts == (profile_id,)
    assert result.uncontained == result.unsettled == ()
    assert worker.contained and worker.settled


def test_stalled_constructor_keeps_profile_owned_without_waiting_past_deadline(tmp_path: Path) -> None:
    profile_id = uuid4()
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="test-storage",
        runtime_boot_id=uuid4(),
        stop=Event(),
    )
    profiles._profiles[profile_id] = cast(
        "RuntimeProfileHost",
        SimpleNamespace(
            store=SimpleNamespace(binding=SimpleNamespace(profile_id=profile_id)),
            owner=_Owner(None, construction_settled=False),
        ),
    )

    deadline = time.monotonic() + 0.05
    result = profiles.drain(deadline=deadline)

    assert time.monotonic() < deadline + 0.5
    assert result.uncontained == (profile_id,)
    assert profiles._profiles[profile_id].owner is not None
