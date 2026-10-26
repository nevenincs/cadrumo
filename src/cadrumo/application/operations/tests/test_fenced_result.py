"""Result publication preserves mutation uncertainty and the cancellation fence."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import cast, override

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect
from ..fenced_result import publish_fenced_result
from ..owner import OperationExecutorContext
from .test_executor import CancellationScope, EventEmitter, ExecutorContext, SecureOperandLookup

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Result(BaseModel):
    changed: bool
    value: str = "persisted-result"


class _Fence(CancellationScope):
    active = False

    @override
    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        self.active = True
        try:
            yield
        finally:
            self.active = False


class _Events(EventEmitter):
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    @override
    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Operands(SecureOperandLookup):
    def __init__(self, fence: _Fence, *, is_read: bool, fail: bool) -> None:
        self._fence = fence
        self._is_read = is_read
        self._fail = fail

    @override
    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        assert self._fence.active is not self._is_read
        if self._fail:
            raise OSError("operand storage failed")
        return await super().put(operand, written_at=written_at)


@pytest.mark.parametrize("is_read", [True, False])
@pytest.mark.parametrize("changed", [True, False])
@pytest.mark.parametrize("failure", [None, "action", "storage"])
@pytest.mark.asyncio
async def test_effects_and_fence_survive_action_and_result_storage_failures(
    is_read: bool, changed: bool, failure: str | None
) -> None:
    context = ExecutorContext()
    fence = _Fence()
    events = _Events()
    context.cancellation = fence
    context.events = events
    context.operands = _Operands(fence, is_read=is_read, fail=failure == "storage")

    async def action() -> _Result:
        assert fence.active is not is_read
        assert events.effects == ([] if is_read else [OperationEffect.UNKNOWN])
        if failure == "action":
            raise OSError("action failed")
        return _Result(changed=changed)

    # CAST-RATIONALE-FENCED-RESULT-CONTEXT: the shared executor-contract fixture
    # supplies these three complete structural ports; unrelated authority is unused.
    invocation = publish_fenced_result(
        cast(OperationExecutorContext, cast(object, context)),
        run_action=action,
        is_read=is_read,
        result_changed=lambda result: result.changed,
    )
    if failure is None:
        assert _Result.model_validate_json(await invocation) == _Result(changed=changed)
    else:
        with pytest.raises(OSError, match=r"action failed|operand storage failed"):
            await invocation
    expected = [] if is_read else [OperationEffect.UNKNOWN]
    if failure != "action":
        expected.append(OperationEffect.NONE if is_read or not changed else OperationEffect.UPDATED)
    assert events.effects == expected
    assert not fence.active
