"""Closed request and result contracts for ledger lifecycle operations."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..review.filter import LedgerReviewStatus
from .models import LedgerRemovalBlocker
from .transaction_projection import LedgerTransactionProjection

LEDGER_ARCHIVE_OPERATION_DEFINITION_ID = "ledger.archive"

LEDGER_STASH_OPERATION_DEFINITION_ID = "ledger.stash"

LEDGER_RESTORE_OPERATION_DEFINITION_ID = "ledger.restore"

LEDGER_EXCLUDE_OPERATION_DEFINITION_ID = "ledger.exclude"

LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE = "REFUSED_LEDGER_LIFECYCLE_VALIDATION"

LedgerLifecycleOperationId = Literal["ledger.archive", "ledger.stash", "ledger.restore", "ledger.exclude"]

LEDGER_LIFECYCLE_MAX_RESULT_BYTES = 256 * 1024

LEDGER_LIFECYCLE_MAX_VALIDATION_MESSAGE_LENGTH = 2048

LEDGER_LIFECYCLE_MAX_RECOVERY_TRANSACTION_IDS = 256

_TransactionPrefix = Annotated[str, Field(min_length=1, max_length=96)]

_Actor = Annotated[str, Field(min_length=1, max_length=64)]

_Reason = Annotated[str, Field(max_length=500)]

_EventIds = Annotated[tuple[Hex64Str, ...], Field(min_length=1, max_length=1)]

_ValidationMessage = Annotated[
    str,
    Field(min_length=1, max_length=LEDGER_LIFECYCLE_MAX_VALIDATION_MESSAGE_LENGTH),
]

_RecoveryTransactionIds = Annotated[
    tuple[Hex64Str, ...],
    Field(max_length=LEDGER_LIFECYCLE_MAX_RECOVERY_TRANSACTION_IDS),
]


class LedgerLifecycleMutationRequest(BaseModel):
    """Private exact-profile request shared by the four lifecycle operations."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: _TransactionPrefix
    actor: _Actor | None = None
    reason: _Reason = ""


class LedgerLifecycleBlockerProjection(BaseModel):
    """The first finalized reference and recovery facts published by its guard."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    work_unit_id: Hex64Str
    calculation_revision_id: Hex64Str
    revision_state: str | None = Field(default=None, min_length=1, max_length=64)
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: FilingYear
    period: str = Field(min_length=1, max_length=16)

    @classmethod
    def from_blocker(cls, blocker: LedgerRemovalBlocker) -> LedgerLifecycleBlockerProjection:
        """Retain the canonical blocker without widening its recovery facts."""
        return cls(
            work_unit_id=blocker.work_unit_id,
            calculation_revision_id=blocker.calculation_revision_id,
            revision_state=blocker.revision_state,
            modelo=blocker.modelo,
            filing_year=blocker.filing_year,
            period=blocker.period,
        )


class LedgerLifecycleValidationProjection(BaseModel):
    """Bounded canonical refusal details, including available safe recovery keys."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    messages: Annotated[tuple[_ValidationMessage, ...], Field(min_length=1, max_length=16)]
    transaction_id: Hex64Str | None = None
    transaction_ids: _RecoveryTransactionIds = ()
    transaction_ids_omitted_count: int = Field(default=0, ge=0)
    blocking_reference: LedgerLifecycleBlockerProjection | None = None
    blocking_reference_count: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _coherent_blocker_facts(self) -> LedgerLifecycleValidationProjection:
        if self.blocking_reference is None and self.blocking_reference_count is not None:
            raise ValueError("lifecycle refusal blocker count requires its canonical blocker")
        if self.blocking_reference is not None and self.blocking_reference_count is None:
            raise ValueError("lifecycle refusal blocker requires the canonical reference count")
        return self


class LedgerLifecycleMutationProjection(BaseModel):
    """Full canonical transaction, review classification, and appended event."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    operation_id: LedgerLifecycleOperationId
    transaction: LedgerTransactionProjection
    review_status: LedgerReviewStatus
    bucket_event_ids: _EventIds


class LedgerLifecycleOperationResult(BaseModel):
    """Success projection or a typed, guaranteed pre-write refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["updated", "validation_error"]
    profile_id: UUID
    operation_id: LedgerLifecycleOperationId
    result: LedgerLifecycleMutationProjection | None = None
    validation: LedgerLifecycleValidationProjection | None = None

    @model_validator(mode="after")
    def _complete_outcome(self) -> LedgerLifecycleOperationResult:
        if self.outcome == "updated":
            if (
                self.result is None
                or self.result.profile_id != self.profile_id
                or self.result.operation_id != self.operation_id
                or self.validation is not None
            ):
                raise ValueError("lifecycle success projection is incomplete or mismatched")
        elif self.result is not None or self.validation is None:
            raise ValueError("lifecycle refusal requires only bounded validation evidence")
        return self


class LedgerLifecycleExecutionResult(BaseModel):
    """Private encrypted operand whose projection is checked against its receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: LedgerLifecycleOperationResult


__all__ = [
    "LEDGER_ARCHIVE_OPERATION_DEFINITION_ID",
    "LEDGER_EXCLUDE_OPERATION_DEFINITION_ID",
    "LEDGER_LIFECYCLE_MAX_RECOVERY_TRANSACTION_IDS",
    "LEDGER_LIFECYCLE_MAX_RESULT_BYTES",
    "LEDGER_LIFECYCLE_MAX_VALIDATION_MESSAGE_LENGTH",
    "LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE",
    "LEDGER_RESTORE_OPERATION_DEFINITION_ID",
    "LEDGER_STASH_OPERATION_DEFINITION_ID",
    "LedgerLifecycleBlockerProjection",
    "LedgerLifecycleExecutionResult",
    "LedgerLifecycleMutationProjection",
    "LedgerLifecycleMutationRequest",
    "LedgerLifecycleOperationId",
    "LedgerLifecycleOperationResult",
    "LedgerLifecycleValidationProjection",
]
