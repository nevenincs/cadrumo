"""Ordered, presentation-free event contracts for supervised operations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from ....core import STRICT_FROZEN_CONFIG, Hex64Str, OperationEffect, OperationEventKind
from ....core.identity import ContentDigest
from ....core.time import validate_utc_aware
from ..events import OperationEventCode, OperationEventSequence, OperationLogSeverity
from ..models import (
    OperationDiagnosticReference,
    OperationIdentity,
    OperationReconciliationOutcome,
    OperationRevision,
    OperationTerminalReceipt,
)


class _OperationEventBase(BaseModel):
    """Identity and ordering shared by every operation event variant."""

    model_config = STRICT_FROZEN_CONFIG

    identity: OperationIdentity
    revision: OperationRevision
    sequence: OperationEventSequence
    timestamp: datetime
    code: OperationEventCode

    @model_validator(mode="after")
    def _validate_timestamp(self) -> _OperationEventBase:
        validate_utc_aware(self.timestamp)
        return self


class OperationPhaseEvent(_OperationEventBase):
    """Record an operation phase transition at one durable event sequence."""

    kind: Literal[OperationEventKind.PHASE] = OperationEventKind.PHASE
    phase_code: OperationEventCode


class OperationProgressEvent(_OperationEventBase):
    """Record bounded progress for one operation revision."""

    kind: Literal[OperationEventKind.PROGRESS] = OperationEventKind.PROGRESS
    completed: Annotated[int, Field(ge=0)]
    total: Annotated[int, Field(gt=0)]
    unit_code: OperationEventCode | None = None

    @model_validator(mode="after")
    def _validate_progress(self) -> OperationProgressEvent:
        if self.completed > self.total:
            raise ValueError("operation progress completed count cannot exceed total")
        return self


class OperationLogRecord(_OperationEventBase):
    """Structured log event carrying no prose or exception payload."""

    kind: Literal[OperationEventKind.LOG] = OperationEventKind.LOG
    severity: OperationLogSeverity
    diagnostic_ref: OperationDiagnosticReference | None = None


class OperationEffectEvent(_OperationEventBase):
    """Record the externally visible effect reached by an operation."""

    kind: Literal[OperationEventKind.EFFECT] = OperationEventKind.EFFECT
    effect: OperationEffect


class OperationNoticeEvent(_OperationEventBase):
    """Stable notice identity; localized message text is a projection."""

    kind: Literal[OperationEventKind.NOTICE] = OperationEventKind.NOTICE
    notice_code: OperationEventCode


class OperationReconciliationEvent(_OperationEventBase):
    """One credential-free durable classification of startup reconciliation."""

    kind: Literal[OperationEventKind.RECONCILIATION] = OperationEventKind.RECONCILIATION
    outcome: OperationReconciliationOutcome
    lease_evidence_ref: ContentDigest


class OperationDiagnosticEvent(_OperationEventBase):
    """Reference existing redacted diagnostics without duplicating capture."""

    kind: Literal[OperationEventKind.DIAGNOSTIC] = OperationEventKind.DIAGNOSTIC
    diagnostic_ref: OperationDiagnosticReference


class OperationInteractionEvent(_OperationEventBase):
    """Safe lifecycle fact that identifies a pending or consumed interaction."""

    kind: Literal[OperationEventKind.INTERACTION] = OperationEventKind.INTERACTION
    interaction_id: Hex64Str


class OperationTerminalEvent(_OperationEventBase):
    """Record the terminal receipt that settles an operation."""

    kind: Literal[OperationEventKind.TERMINAL] = OperationEventKind.TERMINAL
    receipt: OperationTerminalReceipt

    @model_validator(mode="after")
    def _validate_receipt(self) -> OperationTerminalEvent:
        if self.receipt.identity != self.identity:
            raise ValueError("terminal event receipt identity does not match event")
        if self.receipt.revision != self.revision:
            raise ValueError("terminal event receipt revision does not match event")
        if self.receipt.settled_at != self.timestamp:
            raise ValueError("terminal event timestamp must equal receipt settlement time")
        return self


type OperationEvent = Annotated[
    OperationPhaseEvent
    | OperationProgressEvent
    | OperationLogRecord
    | OperationEffectEvent
    | OperationNoticeEvent
    | OperationReconciliationEvent
    | OperationDiagnosticEvent
    | OperationInteractionEvent
    | OperationTerminalEvent,
    Field(discriminator="kind"),
]

__all__ = [
    "OperationDiagnosticEvent",
    "OperationEffectEvent",
    "OperationEvent",
    "OperationInteractionEvent",
    "OperationLogRecord",
    "OperationNoticeEvent",
    "OperationPhaseEvent",
    "OperationProgressEvent",
    "OperationReconciliationEvent",
    "OperationTerminalEvent",
]
