"""Strict transport snapshot of the canonical local filing receipt."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.hashing import canonical_json_bytes
from ...core.i18n.render import tr
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.filing_evidence import FilingEvidenceReference
from ...domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    IvaSettlementRefundState,
    IvaSettlementSnapshot,
    ModeloRecord,
    ModeloRecordStatus,
)
from ...domain.modelos.filing_text import FilingNotes, ModeloActorLabel
from ..operations.public_period import PublicPeriod
from .declarations_workspace_contracts import DeclarationsWorkspaceFilingRefV1


class ModeloRelatedFilingProjection(BaseModel):
    """Exact navigation targets with independently worded filing and confirmation state."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    filing_record_id: FilingRecordId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    modelo: str
    filing_year: FilingYear
    period: str
    member_nif: str | None
    filed_at: datetime
    declaration_kind: FilingDeclarationKind
    confirmation: AeatConfirmationState
    status: ModeloRecordStatus
    origin: FilingOrigin
    amends_filing_record_id: FilingRecordId | None
    superseded_by_filing_record_id: FilingRecordId | None
    kind_words: str
    confirmation_words: str
    status_words: str

    @classmethod
    def from_reference(cls, record: DeclarationsWorkspaceFilingRefV1, language: OutputLanguage) -> Self:
        """Word an admitted catalogue reference without inferring a legal transition."""
        return cls(
            filing_record_id=record.filing_record_id,
            work_unit_id=record.work_unit_id,
            calculation_revision_id=record.calculation_revision_id,
            modelo=str(record.modelo),
            filing_year=record.filing_year,
            period=record.period.registry_token,
            member_nif=record.member_nif,
            filed_at=record.filed_at,
            declaration_kind=record.declaration_kind,
            confirmation=record.confirmation,
            status=record.local_status,
            origin=record.origin,
            amends_filing_record_id=record.amends_filing_record_id,
            superseded_by_filing_record_id=record.superseded_by_filing_record_id,
            kind_words=tr(
                f"workspace.declarations.declaration_kind.{record.declaration_kind.value}", locale=language.value
            ),
            confirmation_words=tr(
                f"workspace.declarations.confirmation.{record.confirmation.value}", locale=language.value
            ),
            status_words=tr(f"workspace.declarations.filing_state.{record.local_status.value}", locale=language.value),
        )


class ModeloRegisterSnapshot(BaseModel):
    """Wire fields of a canonical external register reference."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    expediente_id: str | None
    csv: str | None
    justificante_number: str | None
    tipo_solicitud: str | None
    presented_at: datetime | None


class ModeloEvidenceSnapshot(BaseModel):
    """External evidence metadata; the evidence bytes remain in custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: ExternalEvidenceKind
    reference_id: str
    imported_at: datetime


class ModeloPaymentEvidenceSnapshot(BaseModel):
    """One payment fact using an ordinary wire timestamp."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    reference: FilingEvidenceReference
    amount: str
    effective_at: datetime


class ModeloCreditSnapshot(BaseModel):
    """Exact decimal spellings of the canonical filed credit equation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    opening_amount: str
    generated_amount: str
    applied_amount: str
    remaining_amount: str


class ModeloSettlementSnapshot(BaseModel):
    """Settlement facts validated together with their canonical receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    calculation_revision_id: CalculationRevisionId
    declared_liability: str
    payment_evidence: tuple[ModeloPaymentEvidenceSnapshot, ...]
    refund_election_intent: bool
    refund_state: IvaSettlementRefundState
    refund_requested_amount: str
    refund_approved_amount: str
    refund_paid_amount: str
    refund_approval_evidence_reference: FilingEvidenceReference | None
    refund_approval_effective_at: datetime | None
    refund_payment_evidence_reference: FilingEvidenceReference | None
    refund_payment_effective_at: datetime | None
    credit_snapshot: ModeloCreditSnapshot

    def to_settlement(self) -> IvaSettlementSnapshot:
        """Validate exact amounts and evidence through the canonical model."""
        return IvaSettlementSnapshot.model_validate_json(self.model_dump_json())


class ModeloFilingRecordSnapshot(BaseModel):
    """One immutable receipt with wire primitives for domain value objects."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    filing_record_id: FilingRecordId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: Annotated[str, Field(min_length=1, max_length=16)]
    filing_year: FilingYear
    period: PublicPeriod
    member_nif: Annotated[str, Field(min_length=1, max_length=32)] | None
    filed_at: datetime
    filed_by: ModeloActorLabel
    notes: FilingNotes | None
    origin: FilingOrigin
    confirmation: AeatConfirmationState
    declaration_kind: FilingDeclarationKind
    aeat_register: ModeloRegisterSnapshot | None
    status: ModeloRecordStatus
    superseded_at: datetime | None
    superseded_by_filing_record_id: FilingRecordId | None
    external_evidence: ModeloEvidenceSnapshot | None
    amends_filing_record_id: FilingRecordId | None
    settlement: ModeloSettlementSnapshot | None
    source_transaction_ids: tuple[TransactionId, ...]

    @classmethod
    def from_record(cls, record: ModeloRecord) -> Self:
        """Capture the writer's returned receipt without another storage read.

        Parameter types: ``record`` (:class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`).
        """
        return cls.model_validate_json(
            canonical_json_bytes(
                record.model_dump(mode="json")
                | {
                    "modelo": str(record.modelo),
                    "period": PublicPeriod.from_period(record.period).model_dump(mode="json"),
                }
            )
        )

    def to_record(self) -> ModeloRecord:
        """Restore the exact canonical receipt for existing frontend rendering."""
        return ModeloRecord.model_validate(
            self.model_dump(mode="python")
            | {
                "period": self.period.to_period(),
                "settlement": self.settlement.to_settlement() if self.settlement is not None else None,
            }
        )

    @model_validator(mode="after")
    def _canonical_record(self) -> Self:
        self.to_record()
        return self
