"""Frontend-neutral invocation boundary for registered operation executors.

The supervisor supplies this context.  Executors can publish typed facts and
work with supervisor-owned resources through it, but cannot mutate the generic
operation envelope or obtain concrete persistence and frontend adapters.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from ...core import OperationEffect
from ...core.async_cleanup import AsyncCloseable
from ...core.identity import ContentDigest
from ._events import OperationDiagnosticReference, OperationEventCode, OperationLogSeverity
from ._models import OperationIdentity, OperationReference, OperationRequest


@runtime_checkable
class OperationCancellationScope(Protocol):
    """Cooperative cancellation view controlled by the supervisor."""

    @property
    def cancellation_requested(self) -> bool:
        """Whether the supervisor has requested a safe stop."""
        ...

    async def acknowledge_cancellation(self) -> None:
        """Record that the executor stopped at a cancellation-safe boundary."""
        ...


@runtime_checkable
class OperationDeadlineAccess(Protocol):
    """Read-only aggregate and cleanup deadlines supplied by the supervisor."""

    @property
    def execution_deadline(self) -> datetime | None:
        """UTC aggregate execution deadline, or ``None`` when undeclared."""
        ...

    @property
    def cleanup_deadline(self) -> datetime | None:
        """UTC cleanup-escalation deadline, or ``None`` when undeclared."""
        ...


@runtime_checkable
class OperationEventEmitter(Protocol):
    """Publish typed facts while leaving identity and ordering to the supervisor."""

    async def phase(self, phase_code: OperationEventCode) -> None:
        """Publish a transition to a definition-declared phase."""
        ...

    async def progress(self, *, completed: int, total: int, unit_code: OperationEventCode | None = None) -> None:
        """Publish bounded unit progress."""
        ...

    async def log(
        self,
        *,
        code: OperationEventCode,
        severity: OperationLogSeverity,
        diagnostic_ref: OperationDiagnosticReference | None = None,
    ) -> None:
        """Publish a structured safe-log fact without prose or exceptions."""
        ...

    async def effect(self, effect: OperationEffect) -> None:
        """Publish the executor's current truthful effect fact."""
        ...

    async def notice(self, notice_code: OperationEventCode) -> None:
        """Publish a stable notice identity for frontend projection."""
        ...

    async def diagnostic(self, diagnostic_ref: OperationDiagnosticReference) -> None:
        """Publish an opaque reference to canonical redacted diagnostics."""
        ...


@runtime_checkable
class OperationSecureOperandLookup(Protocol):
    """Resolve confidential operands by canonical content digest."""

    async def resolve[OperandT: BaseModel](
        self,
        reference: ContentDigest,
        operand_type: type[OperandT],
    ) -> OperandT:
        """Return the validated operand of the requested application model type."""
        ...


@runtime_checkable
class OperationCleanupOwner(Protocol):
    """Transfer asynchronous resource ownership to supervisor settlement."""

    def own(self, resource: AsyncCloseable) -> None:
        """Register a resource that must close before terminal settlement."""
        ...


@runtime_checkable
class OperationExecutorContext(Protocol):
    """Narrow capabilities available to one running operation executor."""

    @property
    def identity(self) -> OperationIdentity:
        """Identity of the invocation receiving emitted facts and resources."""
        ...

    @property
    def cancellation(self) -> OperationCancellationScope:
        """Supervisor-owned cooperative cancellation scope."""
        ...

    @property
    def deadlines(self) -> OperationDeadlineAccess:
        """Supervisor-owned aggregate and cleanup deadline view."""
        ...

    @property
    def events(self) -> OperationEventEmitter:
        """Typed event boundary; executors never sequence or persist events."""
        ...

    @property
    def operands(self) -> OperationSecureOperandLookup:
        """Secure lookup boundary for digest-addressed confidential operands."""
        ...

    @property
    def cleanup(self) -> OperationCleanupOwner:
        """Resource ownership boundary settled by the supervisor."""
        ...


@runtime_checkable
class OperationExecutor[RequestPayloadT: BaseModel](Protocol):
    """Application-owned executor invoked only through the operation supervisor."""

    async def execute(
        self,
        request: OperationRequest[RequestPayloadT],
        context: OperationExecutorContext,
    ) -> OperationReference | None:
        """Run one request and return an optional domain-owned result reference."""
        ...


__all__ = [
    "OperationCancellationScope",
    "OperationCleanupOwner",
    "OperationDeadlineAccess",
    "OperationEventEmitter",
    "OperationExecutor",
    "OperationExecutorContext",
    "OperationSecureOperandLookup",
]
