"""Exchange budgets decide when a slow worker reply contains the whole worker."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from threading import Event, RLock
from typing import override
from uuid import UUID, uuid4

import pytest

from ....application.operations.frontend_requests import OperationObservationRequestV1
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.profile_worker import ProfileWorkerIdentity, ProfileWorkerRefusal
from ....application.runtime.worker_authorization import AUTHORITY_SECTION_MAXIMUM_SECONDS
from ....application.user_profile.access_contracts import AccessDenialCode, ProfileAccessBinding
from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ..profile_worker import ProfileWorkerProcess
from ..runtime_frame_io import document_frame
from ..windows_channel import WindowsRuntimeChannel
from ..windows_process import WindowsProcessScope

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_IDENTITY = ProfileWorkerIdentity(
    worker_id=uuid4(),
    runtime_boot_id=uuid4(),
    binding=ProfileAccessBinding(
        profile_id=uuid4(),
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    ),
)


class _SlowWorkerChannel(WindowsRuntimeChannel):
    """A worker pipe whose reply to each request arrives ``latency`` seconds after it is sent.

    The reply is the worker's own typed refusal, so an exchange that waits long
    enough observes the worker's answer instead of a transport deadline.
    """

    def __init__(self, latency: float) -> None:
        self.latency = latency
        self.pending = bytearray()
        self.awaiting_reply = False

    @override
    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        request = json.loads(bytes(payload[5:]))
        reply = ProfileWorkerRefusal(
            identity=_IDENTITY,
            request_id=UUID(request["request_id"]),
            reason=AccessDenialCode.OPERATION_UNAVAILABLE,
        )
        self.pending.extend(document_frame(reply))
        self.awaiting_reply = True

    @override
    def read_exact(self, count: int, *, deadline: float) -> bytes:
        if self.awaiting_reply:
            if deadline - time.monotonic() < self.latency:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            self.awaiting_reply = False
        result = bytes(self.pending[:count])
        del self.pending[:count]
        return result

    @override
    def close(self) -> None:
        return None


class _Worker(ProfileWorkerProcess):
    """The real transport over in-memory channels; containment is recorded, not performed."""

    contained: bool

    @override
    def close(self, *, deadline: float | None = None) -> None:
        self.contained = True


def _worker(latency: float) -> _Worker:
    worker = _Worker.__new__(_Worker)
    worker.identity = _IDENTITY
    worker._lock = RLock()
    worker._operation_lock = RLock()
    worker._native_guard = RLock()
    worker._stopping = Event()
    # Not a Linux scope, so the exchange needs no native membership check.
    worker._scope = WindowsProcessScope.__new__(WindowsProcessScope)
    worker._channel = _SlowWorkerChannel(latency)
    worker._operation_channel = _SlowWorkerChannel(latency)
    worker.contained = False
    return worker


def _observe(worker: _Worker) -> None:
    worker.observe(
        uuid4(),
        OperationObservationRequestV1(operation_id="a" * 64, after_cursor=0, page_limit=1),
    )


def test_operation_reply_inside_the_worker_authority_budget_keeps_the_worker() -> None:
    """A reply slower than the control budget but inside the worker's own lease wait is still read."""
    worker = _worker(latency=AUTHORITY_SECTION_MAXIMUM_SECONDS + 5)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        _observe(worker)

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    assert not worker.contained
    assert not worker._stopping.is_set()


def test_operation_reply_beyond_the_worker_authority_budget_still_contains_the_worker() -> None:
    worker = _worker(latency=AUTHORITY_SECTION_MAXIMUM_SECONDS + 20)

    with pytest.raises(RuntimeRefusalError) as refused:
        _observe(worker)

    assert refused.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    assert worker.contained
    assert worker._stopping.is_set()


def test_control_reply_keeps_its_short_budget() -> None:
    worker = _worker(latency=11)

    with pytest.raises(RuntimeRefusalError) as refused:
        worker.status()

    assert refused.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    assert worker.contained


@pytest.mark.parametrize("reentrant", [False, True])
def test_expired_free_or_reentrant_exchange_sends_nothing_and_keeps_worker(reentrant: bool) -> None:
    worker = _worker(latency=0)
    channel = worker._channel
    assert isinstance(channel, _SlowWorkerChannel)

    with (
        worker._lock if reentrant else nullcontext(),
        pytest.raises(RuntimeRefusalError) as refused,
    ):
        worker.prepare_api_admission(deadline=time.monotonic() - 1)

    assert refused.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    assert not channel.pending and not channel.awaiting_reply
    assert not worker.contained and not worker._stopping.is_set()
    with pytest.raises(ProfileAccessRefusedError) as available:
        worker.status()
    assert available.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    assert not worker.contained


def test_expiry_while_acquiring_exchange_lock_releases_it_without_retiring_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker(latency=0)
    channel = worker._channel
    assert isinstance(channel, _SlowWorkerChannel)
    budget_checked = Event()
    instant = 100.0

    def monotonic() -> float:
        observed = instant
        budget_checked.set()
        return observed

    pool = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(time, "monotonic", monotonic)
    try:
        with worker._lock:
            response = pool.submit(worker.prepare_api_admission, deadline=105.0)
            assert budget_checked.wait(2), "queued caller did not check its original budget"
            instant = 106.0
        with pytest.raises(RuntimeRefusalError) as refused:
            response.result(timeout=2)
        assert refused.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
        assert not channel.pending and not channel.awaiting_reply
        assert not worker.contained and not worker._stopping.is_set()
        assert worker._lock.acquire(blocking=False), "expired borrower retained the exchange lock"
        worker._lock.release()
        with pytest.raises(ProfileAccessRefusedError) as available:
            worker.status()
        assert available.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
        assert not worker.contained
    finally:
        pool.shutdown(wait=True)
