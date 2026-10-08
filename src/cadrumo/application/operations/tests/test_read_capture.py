"""Capturing one blocking local read as a no-effect operation result."""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Any, cast

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect
from ..read_capture import capture_read_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Projection(BaseModel):
    value: int


class _Operands:
    def __init__(self, journal: list[object]) -> None:
        self._journal = journal

    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        self._journal.append(("put", operand, written_at.tzinfo is not None))
        return "sha256:" + "a" * 64


class _Events:
    def __init__(self, journal: list[object]) -> None:
        self._journal = journal

    async def effect(self, effect: OperationEffect) -> None:
        self._journal.append(("effect", effect))


def _context(journal: list[object]) -> Any:
    class _Context:
        operands = _Operands(journal)
        events = _Events(journal)

    return cast(Any, _Context())


def test_the_read_result_is_stored_before_no_effect_is_declared() -> None:
    journal: list[object] = []
    projection = _Projection(value=7)

    reference = asyncio.run(capture_read_result(_context(journal), lambda: projection, task_name="test-read"))

    assert reference == "sha256:" + "a" * 64
    assert journal == [("put", projection, True), ("effect", OperationEffect.NONE)]


def test_the_read_runs_off_the_event_loop_thread() -> None:
    journal: list[object] = []
    threads: list[int] = []

    def read() -> _Projection:
        threads.append(threading.get_ident())
        return _Projection(value=1)

    async def run() -> int:
        await capture_read_result(_context(journal), read, task_name="test-read")
        return threading.get_ident()

    loop_thread = asyncio.run(run())

    assert threads and threads[0] != loop_thread


def test_a_cancelled_caller_still_finishes_the_capture_before_cancellation_propagates() -> None:
    journal: list[object] = []
    started = threading.Event()
    release = threading.Event()

    def read() -> _Projection:
        started.set()
        release.wait(timeout=5)
        return _Projection(value=2)

    async def run() -> None:
        task = asyncio.create_task(capture_read_result(_context(journal), read, task_name="test-read"))
        await asyncio.to_thread(started.wait, 5)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())

    assert journal == [("put", _Projection(value=2), True), ("effect", OperationEffect.NONE)]
