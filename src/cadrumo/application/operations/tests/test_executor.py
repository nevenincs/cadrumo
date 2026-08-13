"""Direct contract proof for public operation-executor protocols."""

from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from ....core import STRICT_FROZEN_CONFIG
from .. import (
    OperationCancellationScope,
    OperationCleanupOwner,
    OperationDeadlineAccess,
    OperationEffect,
    OperationEventEmitter,
    OperationExecutor,
    OperationExecutorContext,
    OperationIdentity,
    OperationLogSeverity,
    OperationSecureOperandLookup,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class Operand(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: str


class CancellationScope:
    cancellation_requested = False

    async def acknowledge_cancellation(self) -> None:
        self.cancellation_requested = True


class DeadlineAccess:
    execution_deadline = datetime(2026, 8, 13, 19, tzinfo=UTC)
    cleanup_deadline = datetime(2026, 8, 13, 20, tzinfo=UTC)


class EventEmitter:
    async def phase(self, phase_code: str) -> None: ...

    async def progress(self, *, completed: int, total: int, unit_code: str | None = None) -> None: ...

    async def log(
        self,
        *,
        code: str,
        severity: OperationLogSeverity,
        diagnostic_ref: str | None = None,
    ) -> None: ...

    async def effect(self, effect: OperationEffect) -> None: ...

    async def notice(self, notice_code: str) -> None: ...

    async def diagnostic(self, diagnostic_ref: str) -> None: ...


class SecureOperandLookup:
    async def resolve(self, reference: str, operand_type: type[Operand]) -> Operand:
        return Operand(value=reference)


class Resource:
    async def close(self) -> None: ...


class CleanupOwner:
    def __init__(self) -> None:
        self.resource: Resource | None = None

    def own(self, resource: Resource) -> None:
        self.resource = resource


class ExecutorContext:
    def __init__(self) -> None:
        self.identity = OperationIdentity(operation_id="a" * 64, definition_id="profile.sync", subject_ref="profile:1")
        self.cancellation = CancellationScope()
        self.deadlines = DeadlineAccess()
        self.events = EventEmitter()
        self.operands = SecureOperandLookup()
        self.cleanup = CleanupOwner()


class Executor:
    async def execute(self, request: object, context: OperationExecutorContext) -> str | None:
        return context.identity.subject_ref


def test_public_protocols_accept_complete_structural_implementations() -> None:
    context = ExecutorContext()

    assert isinstance(context.cancellation, OperationCancellationScope)
    assert isinstance(context.deadlines, OperationDeadlineAccess)
    assert isinstance(context.events, OperationEventEmitter)
    assert isinstance(context.operands, OperationSecureOperandLookup)
    assert isinstance(context.cleanup, OperationCleanupOwner)
    assert isinstance(context, OperationExecutorContext)
    assert isinstance(Executor(), OperationExecutor)

    asyncio.run(context.cancellation.acknowledge_cancellation())
    operand = asyncio.run(context.operands.resolve("sha256:" + "b" * 64, Operand))
    resource = Resource()
    context.cleanup.own(resource)
    asyncio.run(context.events.phase("profile.sync.read"))
    asyncio.run(context.events.progress(completed=1, total=1, unit_code="profile"))
    asyncio.run(context.events.log(code="profile.sync.done", severity=OperationLogSeverity.INFO))
    asyncio.run(context.events.effect(OperationEffect.NONE))
    asyncio.run(context.events.notice("profile.sync.done"))
    asyncio.run(context.events.diagnostic("sha256:0123456789ab"))

    assert context.cancellation.cancellation_requested is True
    assert operand.value == "sha256:" + "b" * 64
    assert context.cleanup.resource is resource


def test_public_callable_parameters_retain_semantic_keyword_names() -> None:
    assert tuple(inspect.signature(OperationEventEmitter.phase).parameters) == ("self", "phase_code")
    assert tuple(inspect.signature(OperationEventEmitter.progress).parameters) == (
        "self",
        "completed",
        "total",
        "unit_code",
    )
    assert tuple(inspect.signature(OperationSecureOperandLookup.resolve).parameters) == (
        "self",
        "reference",
        "operand_type",
    )


def test_runtime_protocols_refuse_each_incomplete_surface() -> None:
    assert not isinstance(SimpleNamespace(), OperationCancellationScope)
    assert not isinstance(SimpleNamespace(execution_deadline=None), OperationDeadlineAccess)
    assert not isinstance(SimpleNamespace(phase=lambda: None), OperationEventEmitter)
    assert not isinstance(SimpleNamespace(), OperationSecureOperandLookup)
    assert not isinstance(SimpleNamespace(), OperationCleanupOwner)
    assert not isinstance(SimpleNamespace(identity=None), OperationExecutorContext)
    assert not isinstance(SimpleNamespace(), OperationExecutor)
