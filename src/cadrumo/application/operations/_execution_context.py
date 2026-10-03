"""Definition-bound execution context for application-owned operations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime

from ...core.async_cleanup import AsyncCloseable
from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import OperationEffect, OperationLifecycle
from ...core.operator_progress import OperatorDisplayCode
from .authorization import OperationExecutionAuthority
from .capabilities import OperationOwnedResource
from .errors import OperationDeclarationError
from .events import OperationEventCode, OperationLogSeverity
from .interactions import OperationPendingInteraction
from .models import OperationDiagnosticReference, OperationId
from .persistence.events import (
    OperationDiagnosticEvent,
    OperationEffectEvent,
    OperationEvent,
    OperationInteractionEvent,
    OperationLogRecord,
    OperationNoticeEvent,
    OperationPhaseEvent,
    OperationProgressEvent,
)
from .persistence.journal import OperationPersistedSnapshot, OperationSecureReferenceStore
from .registry import OperationRegistry


class _Cancellation:
    def __init__(
        self,
        *,
        context: DefinitionBoundContext,
        acknowledge: Callable[[OperationPersistedSnapshot], Awaitable[OperationPersistedSnapshot]],
        set_deferred: Callable[[OperationPersistedSnapshot, bool], Awaitable[OperationPersistedSnapshot]],
    ) -> None:
        self._context = context
        self._acknowledge = acknowledge
        self._set_deferred = set_deferred
        self._irreversible_section_depth = 0
        self._irreversible_owner: asyncio.Task[object] | None = None
        self._irreversible_lock = asyncio.Lock()

    @property
    def cancellation_requested(self) -> bool:
        return self._context.snapshot.cancellation_requested_at is not None

    async def acknowledge_cancellation(self) -> None:
        if not self.cancellation_requested:
            raise ValueError("cancellation acknowledgement requires a supervisor request")
        if self._irreversible_section_depth:
            raise ValueError("cancellation acknowledgement is unsafe within an irreversible section")
        self._context.snapshot = await self._acknowledge(self._context.snapshot)

    def record_request(self, snapshot: OperationPersistedSnapshot) -> None:
        """Synchronize a durably accepted supervisor request into this view."""
        if snapshot.identity != self._context.identity:
            raise ValueError("cancellation request identity does not match executor context")
        self._context.snapshot = snapshot

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        """Protect one executor-owned mutation boundary from an unsafe stop."""
        task = asyncio.current_task()
        if task is None:
            raise InternalInvariantError("irreversible section requires an owning async task")
        async with AsyncExitStack() as authority:
            if task is not self._irreversible_owner:
                await authority.enter_async_context(self._irreversible_lock)
            if self.cancellation_requested:
                raise ValueError("cancellation was requested before the irreversible section began")
            if self._irreversible_section_depth == 0:
                if self._context.execution_authority is not None:
                    await authority.enter_async_context(
                        self._context.execution_authority.commit_guard(self._context.identity)
                    )
                self._context.snapshot = await self._set_deferred(self._context.snapshot, True)
                self._irreversible_owner = task
            self._irreversible_section_depth += 1
            try:
                yield
            finally:
                self._irreversible_section_depth -= 1
                if self._irreversible_section_depth == 0:
                    try:
                        self._context.snapshot = await self._set_deferred(self._context.snapshot, False)
                    finally:
                        self._irreversible_owner = None


class _Deadlines:
    def __init__(self, context: DefinitionBoundContext) -> None:
        self._context = context

    @property
    def execution_deadline(self) -> datetime | None:
        return self._context.snapshot.execution_deadline

    @property
    def cleanup_deadline(self) -> datetime | None:
        return self._context.snapshot.cleanup_deadline


class DefinitionBoundContext:
    """One executor view whose declarations are checked before state mutation."""

    def __init__(
        self,
        *,
        snapshot: OperationPersistedSnapshot,
        registry: OperationRegistry,
        operands: OperationSecureReferenceStore | None,
        clock: Callable[[], datetime],
        resources: dict[OperationId, list[AsyncCloseable]],
        advance: Callable[..., Awaitable[OperationPersistedSnapshot]],
        acknowledge_cancellation: Callable[[OperationPersistedSnapshot], Awaitable[OperationPersistedSnapshot]],
        set_cancellation_deferred: Callable[[OperationPersistedSnapshot, bool], Awaitable[OperationPersistedSnapshot]],
        execution_authority: OperationExecutionAuthority | None = None,
    ) -> None:
        self.registry = registry
        self.clock = clock
        self.resources = resources
        self.advance_transition = advance
        self.snapshot = snapshot
        self.identity = snapshot.identity
        self.execution_authority = execution_authority
        self.cancellation = _Cancellation(
            context=self,
            acknowledge=acknowledge_cancellation,
            set_deferred=set_cancellation_deferred,
        )
        self.deadlines = _Deadlines(self)
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
            raise OperationDeclarationError("operation phase is not declared by its definition")
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
            raise OperationDeclarationError("operation effect is not declared by its definition")
        event = OperationEffectEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code="operation.effect",
            effect=effect,
        )
        await self._context.advance(lifecycle=OperationLifecycle.RUNNING, events=(event,), effect=effect)

    async def notice(
        self,
        notice_code: OperationEventCode,
        *,
        display_code: OperatorDisplayCode | None = None,
    ) -> None:
        event = OperationNoticeEvent(
            identity=self._context.identity,
            revision=0,
            sequence=1,
            timestamp=self._context.clock(),
            code=notice_code,
            notice_code=notice_code,
            display_code=display_code,
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
            raise OperationDeclarationError("operation resource family is not declared by its definition")
        self._context.resources.setdefault(self._context.identity.operation_id, []).append(resource)


class _DefinitionBoundInteractions:
    def __init__(self, context: DefinitionBoundContext) -> None:
        self._context = context

    async def request(self, pending: OperationPendingInteraction) -> None:
        definition = self._context.registry.lookup(self._context.identity.definition_id)
        if pending.request.kind not in definition.interaction_kinds:
            raise OperationDeclarationError("operation interaction kind is not declared by its definition")
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
