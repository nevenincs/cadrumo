"""Closed registered-operation projections for ledger tracking facts."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core.filing_year import FilingYear
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.modelos.participation_index import (
    TransactionRevisionParticipation,
    TransactionRevisionParticipationIndex,
)
from ...domain.transactions.models import Transaction
from ..operations.public_period import PublicPeriod
from .models import LedgerTransactionTrackingPayload


class LedgerTrackingEvidenceProjection(BaseModel):
    """One JSON-stable evidence-link lineage fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    evidence_id: str
    evidence_kind: str
    actor: str
    source_command: str
    linked_at: str
    bucket_event_id: str | None


class LedgerTrackingEditProjection(BaseModel):
    """One JSON-stable manual-correction lineage fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    previous_transaction_id: TransactionId
    actor: str
    source_command: str
    edited_at: str
    bucket_event_id: str | None


class LedgerTrackingLifecycleProjection(BaseModel):
    """One JSON-stable lifecycle-transition lineage fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    previous_state: str
    state: str
    actor: str
    source_command: str
    changed_at: str
    reason: str
    bucket_event_id: str | None


class LedgerTrackingProjection(BaseModel):
    """Closed lineage projection of the canonical tracking payload.

    The canonical payload owns domain validation. This model carries only its
    JSON facts, so runtime result contracts do not import the domain lineage
    validators or reinterpret timestamps and lifecycle states.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId
    created_event_id: str | None
    evidence_provenance: tuple[LedgerTrackingEvidenceProjection, ...]
    edit_lineage: tuple[LedgerTrackingEditProjection, ...]
    lifecycle_state: str
    lifecycle_lineage: tuple[LedgerTrackingLifecycleProjection, ...]

    @classmethod
    def from_payload(cls, payload: LedgerTransactionTrackingPayload) -> LedgerTrackingProjection:
        """Copy validated lineage facts with the canonical JSON encoding."""
        return cls.model_validate_json(payload.model_dump_json())


class LedgerParticipationProjection(BaseModel):
    """Closed JSON facts for one finalized-revision participation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    modelo: str
    filing_year: FilingYear
    period: PublicPeriod
    revision_state: str
    filing_record_id: FilingRecordId | None
    justificante_reference: str | None

    @classmethod
    def from_participation(cls, participation: TransactionRevisionParticipation) -> LedgerParticipationProjection:
        """Copy canonical facts, using the CLI's explicit ModeloCode string form."""
        return cls(
            calculation_revision_id=participation.calculation_revision_id,
            work_unit_id=participation.work_unit_id,
            modelo=str(participation.modelo),
            filing_year=participation.filing_year,
            period=PublicPeriod.from_period(participation.period),
            revision_state=participation.revision_state,
            filing_record_id=participation.filing_record_id,
            justificante_reference=participation.justificante_reference,
        )

    @classmethod
    def from_index(
        cls,
        index: TransactionRevisionParticipationIndex,
    ) -> tuple[LedgerParticipationProjection, ...] | None:
        """Project every stored row in order, retaining track's empty ``None``."""
        if not index.participations:
            return None
        return tuple(cls.from_participation(item) for item in index.participations)


class LedgerImportedProvenanceProjection(BaseModel):
    """Imported-row facts used by track's JSON fields and text lines.

    The source path is deliberately reduced to its filename. Raw source columns
    and the source digest remain inside the domain record and never enter this
    transport projection.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    provider_name: str = Field(min_length=1)
    source_filename: str = Field(min_length=1)
    source_row_index: int = Field(ge=1)
    ingested_at: str = Field(min_length=1)
    import_fingerprint: str | None

    @classmethod
    def from_transaction(cls, transaction: Transaction) -> LedgerImportedProvenanceProjection | None:
        """Project imported provenance exactly when the CLI exposes it."""
        if transaction.created_event_id is not None:
            return None
        provenance = transaction.raw.provenance
        return cls(
            provider_name=provenance.provider_name,
            source_filename=provenance.source_path.name,
            source_row_index=provenance.source_row_index,
            ingested_at=provenance.ingested_at.isoformat(),
            import_fingerprint=transaction.import_fingerprint,
        )


__all__ = [
    "LedgerImportedProvenanceProjection",
    "LedgerParticipationProjection",
    "LedgerTrackingEditProjection",
    "LedgerTrackingEvidenceProjection",
    "LedgerTrackingLifecycleProjection",
    "LedgerTrackingProjection",
]
