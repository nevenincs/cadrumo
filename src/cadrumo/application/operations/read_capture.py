"""Capture one blocking local read as an operation result that leaves no effect."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect
from ...core.time.clock import now
from .owner import OperationExecutorContext


async def capture_read_result(
    context: OperationExecutorContext, read: Callable[[], BaseModel], *, task_name: str
) -> str:
    """Run ``read`` off the event loop, store its result and declare no effect.

    The read, the confidential result write and the no-effect declaration finish
    as one task named ``task_name`` before a caller's cancellation is re-raised,
    so a cancelled executor never leaves a stored result without its effect.
    Returns the stored result's reference.
    """

    async def capture() -> str:
        result = await asyncio.to_thread(read)
        reference = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return reference

    return await await_cancellation_complete(capture(), task_name=task_name)
