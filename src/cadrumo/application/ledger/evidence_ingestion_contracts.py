"""Canonical public and encrypted contracts for ledger evidence ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...domain.iva.classification import InvoiceKind
from ..operations.public_scalar import PublicNamedScalar, project_facts, restore_facts
from ..operator_actions.projection import PreconditionVerdictSnapshot
from .batch_ingest import (
    BatchItemResult,
    BatchItemStatus,
    BatchRunResult,
    InferencePause,
    UnresolvedBatchSource,
)
from .invoice_evidence_operation_dtos import LabelReadingFallbackProjectionV1

LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID = "ledger.evidence.batch"
_Path = Annotated[str, Field(min_length=1, max_length=4096)]


class LedgerEvidenceBatchRequest(BaseModel):
    """Local source references kept exclusively in encrypted operand custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    sources: Annotated[tuple[_Path, ...], Field(min_length=1)]
    source_directory: _Path
    direction: InvoiceKind

    @model_validator(mode="after")
    def _absolute_directory(self) -> LedgerEvidenceBatchRequest:
        if not Path(self.source_directory).is_absolute():
            raise ValueError("source directory must be absolute")
        return self


class LedgerEvidenceBatchItemSnapshot(BaseModel):
    """Lossless canonical row with a closed precondition projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    content_address: ContentDigest
    identity: str
    direction: InvoiceKind
    source_name: str
    status: BatchItemStatus
    refusal_code: str | None
    refusal_verdict: PreconditionVerdictSnapshot | None
    needed_inference: bool
    label_reading_fallback: LabelReadingFallbackProjectionV1 | None

    @classmethod
    def from_item(cls, item: BatchItemResult) -> LedgerEvidenceBatchItemSnapshot:
        """Copy canonical identity and outcome without exception text."""
        return cls(
            **item.model_dump(exclude={"refusal_verdict", "label_reading_fallback"}),
            refusal_verdict=PreconditionVerdictSnapshot.from_verdict(item.refusal_verdict)
            if item.refusal_verdict is not None
            else None,
            label_reading_fallback=LabelReadingFallbackProjectionV1.from_fallback(item.label_reading_fallback)
            if item.label_reading_fallback is not None
            else None,
        )

    def to_item(self) -> BatchItemResult:
        """Restore canonical row invariants for the existing human presenter."""
        return BatchItemResult(
            **self.model_dump(exclude={"refusal_verdict", "label_reading_fallback"}),
            refusal_verdict=self.refusal_verdict.to_verdict() if self.refusal_verdict is not None else None,
            label_reading_fallback=self.label_reading_fallback.to_fallback()
            if self.label_reading_fallback is not None
            else None,
        )

    @model_validator(mode="after")
    def _canonical(self) -> LedgerEvidenceBatchItemSnapshot:
        self.to_item()
        return self


class LedgerEvidenceUnresolvedSnapshot(BaseModel):
    """An unreadable source retains its exact canonical refusal facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_name: str
    refusal_code: str
    refusal_verdict: PreconditionVerdictSnapshot


class LedgerEvidenceInferencePauseSnapshot(BaseModel):
    """Canonical inference admission facts represented as immutable scalars."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    facts: tuple[PublicNamedScalar, ...]
    precondition_verdict: PreconditionVerdictSnapshot


class LedgerEvidenceBatchSnapshot(BaseModel):
    """Complete ordered batch result; canonical service derives all summaries."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    items: tuple[LedgerEvidenceBatchItemSnapshot, ...]
    unresolved: tuple[LedgerEvidenceUnresolvedSnapshot, ...]
    inference_pause: LedgerEvidenceInferencePauseSnapshot | None

    @classmethod
    def from_run(cls, run: BatchRunResult) -> LedgerEvidenceBatchSnapshot:
        """Project every original row and inference fact without truncation."""
        pause = run.inference_pause
        return cls(
            items=tuple(LedgerEvidenceBatchItemSnapshot.from_item(item) for item in run.items),
            unresolved=tuple(
                LedgerEvidenceUnresolvedSnapshot(
                    source_name=row.source_name,
                    refusal_code=row.refusal_code,
                    refusal_verdict=PreconditionVerdictSnapshot.from_verdict(row.refusal_verdict),
                )
                for row in run.unresolved
            ),
            inference_pause=LedgerEvidenceInferencePauseSnapshot(
                facts=project_facts(pause.facts),
                precondition_verdict=PreconditionVerdictSnapshot.from_verdict(pause.precondition_verdict),
            )
            if pause is not None
            else None,
        )

    def to_run(self) -> BatchRunResult:
        """Restore the canonical service report and its existing count semantics."""
        pause = self.inference_pause
        return BatchRunResult(
            items=tuple(item.to_item() for item in self.items),
            unresolved=tuple(
                UnresolvedBatchSource(
                    source_name=row.source_name,
                    refusal_code=row.refusal_code,
                    refusal_verdict=row.refusal_verdict.to_verdict(),
                )
                for row in self.unresolved
            ),
            inference_pause=InferencePause.model_validate(
                {
                    "facts": restore_facts(pause.facts),
                    "precondition_verdict": pause.precondition_verdict.to_verdict(),
                }
            )
            if pause is not None
            else None,
        )

    @model_validator(mode="after")
    def _canonical(self) -> LedgerEvidenceBatchSnapshot:
        self.to_run()
        return self


class _WriteReceipt(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    write_count: int = Field(ge=0)
    effect: OperationEffect

    @model_validator(mode="after")
    def _write_truth(self) -> _WriteReceipt:
        if self.effect not in {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.PARTIAL}:
            raise ValueError("successful evidence results require certain concrete writer outcomes")
        if (self.write_count == 0) != (self.effect is OperationEffect.NONE):
            raise ValueError("evidence effect contradicts its concrete writer count")
        return self


class LedgerEvidenceBatchProjection(_WriteReceipt):
    """Whole protected batch report and actual custody write receipt."""

    direction: InvoiceKind
    run: LedgerEvidenceBatchSnapshot

    @model_validator(mode="after")
    def _direction(self) -> LedgerEvidenceBatchProjection:
        if any(row.direction is not self.direction for row in self.run.items):
            raise ValueError("batch row belongs to another declared direction")
        return self


class LedgerEvidenceBatchExecutionResult(BaseModel):
    """Encrypted batch execution document."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: LedgerEvidenceBatchProjection
