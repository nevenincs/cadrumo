"""Definition-bound execution context for application-owned operations."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime

from ...core import OperationEffect, OperationLifecycle
from ...core.async_cleanup import AsyncCloseable
from ._capabilities import OperationOwnedResource
from ._events import (
    OperationDiagnosticEvent,
    OperationDiagnosticReference,
    OperationEffectEvent,
    OperationEvent,
    OperationEventCode,
    OperationInteractionEvent,
    OperationLogRecord,
    OperationLogSeverity,
    OperationNoticeEvent,
    OperationPhaseEvent,
    OperationProgressEvent,
)
from ._interactions import OperationPendingInteraction
from ._journal import OperationPersistedSnapshot, OperationSecureReferenceStore
from ._models import OperationId
from ._registry import OperationRegistry


class _Cancellation:
    def __init__(self) -> None:
        self.cancellation_requested = False

    async def acknowledge_cancellation(self) -> None:
        self.cancellation_requested = True


class _Deadlines:
    execution_deadline: datetime | None = None
    cleanup_deadline: datetime | None = None


class DefinitionBoundContext:
    """One executor view whose declarations are checked before state mutation."""

    def __init__(
        self,
        *,
        snapshot: OperationPersistedSnapshot,
        registry: OperationRegistry,
        operands: OperationSecureReferenceStore,
        clock: Callable[[], datetime],
        resources: dict[OperationId, list[AsyncCloseable]],
        advance: Callable[..., Awaitable[OperationPersistedSnapshot]],
    ) -> None:
        self.registry = registry
        self.clock = clock
        self.resources = resources
        self.advance_transition = advance
        self.snapshot = snapshot
        self.identity = snapshot.identity
        self.cancellation = _Cancellation()
        self.deadlines = _Deadlines()
        self.events = _DefinitionBoundEvents(self)
        self.operands = operands
        self.cleanup = _DefinitionBoundCleanup(self)
        self.interactions = _DefinitionBoundInteractions(self)

    async def advance(
        self,
        *,
        lifecycle: OperationLifecycle,
        events: tuple[OperationEvent, ...] = (),
        pending: OperationPendingInteraction | None = None,
        effect: OperationEffect | None = None,
    ) -> None:
        self.snapshot = await self.advance_transition(
            self.snapshot,
            lifecycle=lifecycle,
            events=events,
            pending=pending,
            effect=effect,
        )


class _DefinitionBoundEvents:
    def __init__(self, context: DefinitionBoundContext) -> None:
        self._context = context

    async def phase(self, phase_code: OperationEventCode) -> None:
        definition = self._context.registry.lookup(self._context.identity.definition_id)
        if phase_code not in definition.phase_codes:
            raise ValueError("operation phase is not declared by its definition")
        event = OperationPhaseEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code=phase_code,
            phase_code=phase_code,
        )
        await self._context.advance(lifecycle=OperationLifecycle.RUNNING, events=(event,))

    async def progress(self, *, completed: int, total: int, unit_code: OperationEventCode | None = None) -> None:
        event = OperationProgressEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code="operation.progress",
            completed=completed,
            total=total,
            unit_code=unit_code,
        )
        await self._context.advance(lifecycle=OperationLifecycle.RUNNING, events=(event,))

    async def log(
        self,
        *,
        code: OperationEventCode,
        severity: OperationLogSeverity,
        diagnostic_ref: OperationDiagnosticReference | None = None,
    ) -> None:
        event = OperationLogRecord(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code=code,
            severity=severity,
            diagnostic_ref=diagnostic_ref,
        )
        await self._context.advance(lifecycle=OperationLifecycle.RUNNING, events=(event,))

    async def effect(self, effect: OperationEffect) -> None:
        definition = self._context.registry.lookup(self._context.identity.definition_id)
        if effect not in definition.capabilities.permitted_effects:
            raise ValueError("operation effect is not declared by its definition")
        event = OperationEffectEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code="operation.effect",
            effect=effect,
        )
        await self._context.advance(lifecycle=OperationLifecycle.RUNNING, events=(event,), effect=effect)

    async def notice(self, notice_code: OperationEventCode) -> None:
        event = OperationNoticeEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code=notice_code,
            notice_code=notice_code,
        )
        await self._context.advance(lifecycle=OperationLifecycle.RUNNING, events=(event,))

    async def diagnostic(self, diagnostic_ref: OperationDiagnosticReference) -> None:
        event = OperationDiagnosticEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code="operation.diagnostic",
            diagnostic_ref=diagnostic_ref,
        )
        await self._context.advance(lifecycle=OperationLifecycle.RUNNING, events=(event,))


class _DefinitionBoundCleanup:
    def __init__(self, context: DefinitionBoundContext) -> None:
        self._context = context

    def own(self, resource: AsyncCloseable, *, family: OperationOwnedResource) -> None:
        definition = self._context.registry.lookup(self._context.identity.definition_id)
        if family not in definition.capabilities.owned_resources:
            raise ValueError("operation resource family is not declared by its definition")
        self._context.resources.setdefault(self._context.identity.operation_id, []).append(resource)


class _DefinitionBoundInteractions:
    def __init__(self, context: DefinitionBoundContext) -> None:
        self._context = context

    async def request(self, pending: OperationPendingInteraction) -> None:
        definition = self._context.registry.lookup(self._context.identity.definition_id)
        if pending.request.kind not in definition.interaction_kinds:
            raise ValueError("operation interaction kind is not declared by its definition")
        if pending.request.identity != self._context.identity:
            raise ValueError("operation interaction identity does not match executor context")
        successor_revision = self._context.snapshot.revision + 1
        if pending.request.revision != successor_revision:
            raise ValueError("operation interaction revision does not match checkpoint revision")
        event = OperationInteractionEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code="operation.interaction.pending",
            interaction_id=pending.request.interaction_id,
        )
        await self._context.advance(
            lifecycle=OperationLifecycle.WAITING_FOR_INTERACTION,
            events=(event,),
            pending=pending,
        )


__all__ = ["DefinitionBoundContext"]
