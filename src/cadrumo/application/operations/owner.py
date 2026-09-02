"""Canonical owner-only invocation boundary for registered operation executors.

The supervisor supplies this context.  Executors can publish typed facts and
work with supervisor-owned resources through it, but cannot mutate the generic
operation envelope or obtain concrete persistence and frontend adapters.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from ...core.async_cleanup import AsyncCloseable
from ...core.identity import ContentDigest
from ...core.operations import OperationEffect
from .capabilities import OperationOwnedResource
from .events import OperationEventCode, OperationLogSeverity
from .financial_operand_submission import OperationFinancialOperandContextAccess
from .interactions import OperationResponseIntentValue
from .models import (
    OperationDiagnosticReference,
    OperationIdentity,
    OperationReference,
    OperationRequest,
    OperationRevision,
)
from .secret_submission import OperationEphemeralSecretAccess


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

    def irreversible_section(self) -> AbstractAsyncContextManager[None]:
        """Protect one executor-owned mutation boundary from an unsafe stop."""
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

    async def progress(
        self,
        *,
        completed: int,
        total: int,
        unit_code: OperationEventCode | None = None,
    ) -> None:
        """Publish bounded unit progress."""
        del unit_code

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
    """Persist and resolve confidential operands by canonical content digest."""

    async def put(self, operand: BaseModel, *, written_at: datetime) -> ContentDigest:
        """Persist one typed operand in supervisor-owned secure storage."""
        ...

    async def resolve[OperandT: BaseModel](
        self,
        reference: ContentDigest,
        operand_type: type[OperandT],
    ) -> OperandT:
        """Return the validated operand of the requested application model type."""
        del operand_type
        raise NotImplementedError


@runtime_checkable
class OperationCleanupOwner(Protocol):
    """Transfer asynchronous resource ownership to supervisor settlement."""

    def own(self, resource: AsyncCloseable, *, family: OperationOwnedResource) -> None:
        """Register a resource that must close before terminal settlement."""
        del family


@runtime_checkable
class OperationInteractionAccess(Protocol):
    """Persist one definition-declared interaction checkpoint before yielding."""

    async def publish_review(
        self,
        *,
        interaction_id: str,
        identity: OperationIdentity,
        revision: OperationRevision,
        presentation_code: OperationEventCode,
        response_schema_ref: OperationReference,
        continuation_digest: ContentDigest,
        expires_at: datetime | None,
        reviewed_operand: BaseModel,
        baseline_digest: ContentDigest | None = None,
        proposed_effect_digest: ContentDigest | None = None,
    ) -> None:
        """Secure a typed reviewed operand before publishing its digest-bound checkpoint."""
        ...


@runtime_checkable
class OperationResumeCheckpoint(Protocol):
    """Safe executor-facing view of one pending or consumed continuation."""

    @property
    def consumed(self) -> bool:
        """Whether the continuation response has already been consumed."""
        ...

    @property
    def reviewed_proposal_digest(self) -> ContentDigest:
        """Digest binding the checkpoint to its reviewed proposal."""
        ...

    @property
    def response_action(self) -> OperationResponseIntentValue | None:
        """Consumed response action, or ``None`` while still pending."""
        ...


@runtime_checkable
class OperationExecutorContext(Protocol):
    """Narrow capabilities available to one running operation executor."""

    @property
    def identity(self) -> OperationIdentity:
        """Identity of the invocation receiving emitted facts and resources."""
        ...

    @property
    def revision(self) -> OperationRevision:
        """Current authoritative revision for an exact successor transition."""
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
    def ephemeral_secret(self) -> OperationEphemeralSecretAccess:
        """One-shot scoped secret access declared for this operation."""
        ...

    @property
    def financial_operand(self) -> OperationFinancialOperandContextAccess:
        """Runtime-only transient financial operand surface for this operation."""
        ...

    @property
    def cleanup(self) -> OperationCleanupOwner:
        """Resource ownership boundary settled by the supervisor."""
        ...

    @property
    def interactions(self) -> OperationInteractionAccess:
        """Supervisor-owned typed interaction checkpoint boundary."""
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


@runtime_checkable
class OperationResumableExecutor[RequestPayloadT: BaseModel](Protocol):
    """Re-enter one declared pending-interaction checkpoint after owner recovery."""

    async def resume(
        self,
        request: OperationRequest[RequestPayloadT],
        checkpoint: OperationResumeCheckpoint,
        context: OperationExecutorContext,
    ) -> OperationReference | None:
        """Resume from the exact durable checkpoint under a new supervisor lease."""
        ...


__all__ = [
    "OperationCancellationScope",
    "OperationCleanupOwner",
    "OperationDeadlineAccess",
    "OperationEventEmitter",
    "OperationExecutor",
    "OperationExecutorContext",
    "OperationInteractionAccess",
    "OperationResumableExecutor",
    "OperationResumeCheckpoint",
    "OperationSecureOperandLookup",
]
