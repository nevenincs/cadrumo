"""Canonical public and encrypted contracts for ledger evidence ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...domain.attachments.enums import DocumentLinkSource
from ...domain.iva.classification import InvoiceKind
from ..operations.public_scalar import PublicNamedScalar, project_facts, restore_facts
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..review.filter import LedgerReviewStatus
from ..runtime.submission_payload import SUBMISSION_PAYLOAD_MAX_BYTES
from .attachment_mutation_operation import LedgerAttachmentStaleRevisionProjection
from .batch_ingest import (
    BatchItemResult,
    BatchItemStatus,
    BatchRunResult,
    InferencePause,
    UnresolvedBatchSource,
)
from .evidence_sweep import EvidenceSweepRefusal
from .invoice_evidence_operation_dtos import LabelReadingFallbackProjectionV1
from .transaction_projection import LedgerTransactionProjection

LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID = "ledger.evidence.batch"
LEDGER_EVIDENCE_PULL_OPERATION_DEFINITION_ID = "ledger.evidence.pull"
LEDGER_EVIDENCE_PULL_ALL_OPERATION_DEFINITION_ID = "ledger.evidence.pull_all"
LEDGER_EVIDENCE_INGESTION_OPERATION_IDS = (
    LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_PULL_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_PULL_ALL_OPERATION_DEFINITION_ID,
)
_Path = Annotated[str, Field(min_length=1, max_length=4096)]
_Reference = Annotated[str, Field(min_length=1, max_length=SUBMISSION_PAYLOAD_MAX_BYTES)]
_Note = Annotated[str, Field(max_length=SUBMISSION_PAYLOAD_MAX_BYTES)]
_Actor = Annotated[str, Field(min_length=1, max_length=SUBMISSION_PAYLOAD_MAX_BYTES)]
_Prefix = Annotated[str, Field(min_length=1, max_length=64)]


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


class LedgerEvidencePullRequest(BaseModel):
    """Human-supplied document reference and target ledger handle."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    transaction_id: _Prefix
    source: DocumentLinkSource
    reference: _Reference
    note: _Note = ""
    actor: _Actor | None = None


class LedgerEvidencePullAllRequest(BaseModel):
    """Human-supplied folder reference and retained attachment annotation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    folder: _Reference
    note: _Note = ""


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


class LedgerEvidencePullProjection(_WriteReceipt):
    """Full canonical ledger mutation result after document custody and linking."""

    requested_transaction_id: _Prefix
    transaction_id: ContentDigest
    transaction: LedgerTransactionProjection
    review_status: LedgerReviewStatus
    bucket_event_ids: tuple[str, ...]
    stale_finalized_revisions: tuple[LedgerAttachmentStaleRevisionProjection, ...]

    @model_validator(mode="after")
    def _identity(self) -> LedgerEvidencePullProjection:
        if self.transaction.transaction_id != self.transaction_id or self.effect is not OperationEffect.UPDATED:
            raise ValueError("document pull result contradicts its transaction or writer receipt")
        return self


class LedgerEvidencePullAllFileSnapshot(BaseModel):
    """One canonical sweep row; source metadata stays in human result custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    file_id: str
    name: str
    mime_type: str
    fetched: bool
    attachment_id: ContentDigest | None
    refusal_reason: EvidenceSweepRefusal | None

    @model_validator(mode="after")
    def _outcome(self) -> LedgerEvidencePullAllFileSnapshot:
        if self.fetched != (self.attachment_id is not None) or self.fetched == (self.refusal_reason is not None):
            raise ValueError("sweep row must be either fetched or refused")
        return self


class LedgerEvidencePullAllProjection(_WriteReceipt):
    """Complete canonical ordered sweep and its derived counts."""

    folder_id: str
    total_documents: int = Field(ge=0)
    fetched_count: int = Field(ge=0)
    refused_count: int = Field(ge=0)
    skipped_non_document_count: int = Field(ge=0)
    files: tuple[LedgerEvidencePullAllFileSnapshot, ...]

    @model_validator(mode="after")
    def _counts(self) -> LedgerEvidencePullAllProjection:
        if (
            self.total_documents != len(self.files)
            or self.fetched_count != sum(row.fetched for row in self.files)
            or self.refused_count != sum(not row.fetched for row in self.files)
        ):
            raise ValueError("sweep counts must cover its exact ordered rows")
        return self


class LedgerEvidenceBatchExecutionResult(BaseModel):
    """Encrypted batch execution document."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: LedgerEvidenceBatchProjection


class LedgerEvidencePullExecutionResult(BaseModel):
    """Encrypted single-document execution document."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: LedgerEvidencePullProjection


class LedgerEvidencePullAllExecutionResult(BaseModel):
    """Encrypted folder-sweep execution document."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: LedgerEvidencePullAllProjection
