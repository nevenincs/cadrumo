"""Publish typed read results and mutation results under the operation fence."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from ...core.operations import OperationEffect
from ...core.time.clock import now
from .owner import OperationExecutorContext


async def publish_fenced_result[ResultT: BaseModel](
    context: OperationExecutorContext,
    *,
    run_action: Callable[[], Awaitable[ResultT]],
    is_read: bool,
    result_changed: Callable[[ResultT], bool],
) -> str:
    """Record effects in order and store the result before releasing a mutation fence.

    Reads publish no effect after the action returns. Mutations announce an
    unknown effect before entering the action; a failure therefore preserves
    uncertainty, while a successful result declares whether state changed.
    """
    if is_read:
        result = await run_action()
        await context.events.effect(OperationEffect.NONE)
        return await context.operands.put(result, written_at=now())
    async with context.cancellation.irreversible_section():
        await context.events.effect(OperationEffect.UNKNOWN)
        result = await run_action()
        await context.events.effect(OperationEffect.UPDATED if result_changed(result) else OperationEffect.NONE)
        return await context.operands.put(result, written_at=now())
