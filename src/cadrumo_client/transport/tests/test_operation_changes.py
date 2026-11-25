"""Async cue subscriptions remain reusable and coalesce bursts before dispatch."""

import asyncio
from collections.abc import Callable

import pytest

from ..operation_changes import AsyncOperationChanges

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class _Cues:
    def __init__(self) -> None:
        self.receivers: list[Callable[[], None]] = []

    def subscribe_operation_changes(self, receive: Callable[[], None]) -> Callable[[], None]:
        self.receivers.append(receive)
        return lambda: self.receivers.remove(receive)

    def emit(self) -> None:
        for receive in tuple(self.receivers):
            receive()


@pytest.mark.asyncio
async def test_rearming_after_close_subscribes_again() -> None:
    source = _Cues()
    changes = AsyncOperationChanges(source)
    changes.arm()
    changes.close()
    try:
        changes.arm()
        assert len(source.receivers) == 1
        source.emit()
        await changes.wait(1)
    finally:
        changes.close()


@pytest.mark.asyncio
async def test_a_cue_burst_queues_one_loop_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _Cues()
    loop = asyncio.get_running_loop()
    queued: list[Callable[[], None]] = []
    with AsyncOperationChanges(source) as changes:
        changes.arm()
        with monkeypatch.context() as patch:
            patch.setattr(loop, "call_soon_threadsafe", queued.append)
            for _ in range(1000):
                source.emit()
        assert len(queued) == 1
        queued.pop()()
        await changes.wait(1)


@pytest.mark.asyncio
async def test_rearming_discards_queued_old_cues(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _Cues()
    loop = asyncio.get_running_loop()
    queued: list[Callable[[], None]] = []
    with AsyncOperationChanges(source) as changes:
        changes.arm()
        with monkeypatch.context() as patch:
            patch.setattr(loop, "call_soon_threadsafe", queued.append)
            source.emit()
            changes.arm()
        for deliver in queued:
            deliver()
        waiting = asyncio.create_task(changes.wait(float("inf")))
        barrier = loop.create_future()
        loop.call_soon(barrier.set_result, None)
        await barrier
        assert not waiting.done(), "a cue preceding arm cannot satisfy the next wait"
        source.emit()
        await asyncio.wait_for(waiting, 1)


@pytest.mark.asyncio
async def test_cancellation_does_not_consume_a_later_reader_thread_cue() -> None:
    source = _Cues()
    with AsyncOperationChanges(source) as changes:
        changes.arm()
        waiting = asyncio.create_task(changes.wait(float("inf")))
        barrier = asyncio.get_running_loop().create_future()
        asyncio.get_running_loop().call_soon(barrier.set_result, None)
        await barrier
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        changes.arm()
        await asyncio.to_thread(source.emit)
        await asyncio.wait_for(changes.wait(float("inf")), 1)
