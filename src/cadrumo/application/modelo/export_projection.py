"""Public result of a locally written Modelo export, and the fichero-BOE receipt it carries."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest, PrefixedContentDigest
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.modelo_export_artefact import ModeloExportArtefact
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.payment_election import PaymentElection
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...core.result_disposition import ResultDisposition
from ...domain.filing.schema import ModeloCasillaProvenance
from ...domain.filing.software_identity import AeatSoftwareIdentityGrade
from ..calculations.observations_repository import PriorDomiciliationElectionProjection
from ..operations.public_period import PublicPeriod
from .export import ModeloExportResult, ModeloIvaWalletDecisionProvenance


class ModeloPriorDomiciliationPublicProvenance(BaseModel):
    """The canonical election and redacted baseline join, without coercive hooks."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    election: PriorDomiciliationElection
    baseline_filing_record_id: FilingRecordId | None = None
    baseline_evidence_reference_id: str | None = Field(default=None, min_length=1, max_length=128)
    baseline_result_disposition: ResultDisposition | None = None
    baseline_source_header_locator: str | None = Field(default=None, min_length=1, max_length=512)

    @model_validator(mode="after")
    def _canonical_election(self) -> Self:
        self.to_provenance()
        return self

    @classmethod
    def from_provenance(cls, source: PriorDomiciliationElectionProjection) -> Self:
        """Copy the canonical prior-election proof into strict wire fields."""
        return cls(
            election=source.election,
            baseline_filing_record_id=source.baseline_filing_record_id,
            baseline_evidence_reference_id=source.baseline_evidence_reference_id,
            baseline_result_disposition=source.baseline_result_disposition,
            baseline_source_header_locator=source.baseline_source_header_locator,
        )

    def to_provenance(self) -> PriorDomiciliationElectionProjection:
        """Restore the original election and its complete baseline proof."""
        return PriorDomiciliationElectionProjection(
            election=self.election,
            baseline_filing_record_id=self.baseline_filing_record_id,
            baseline_evidence_reference_id=self.baseline_evidence_reference_id,
            baseline_result_disposition=self.baseline_result_disposition,
            baseline_source_header_locator=self.baseline_source_header_locator,
        )


class ModeloIvaWalletDecisionPublicProvenance(BaseModel):
    """The redacted wallet audit join with a public period coordinate."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    decision_ref: PrefixedContentDigest
    selected_authority: str = Field(min_length=1, max_length=64)
    divergence: str = Field(min_length=1, max_length=64)
    target_year: FilingYear
    target_period: PublicPeriod
    authority_source_kinds: tuple[str, ...] = ()
    authority_source_refs: tuple[PrefixedContentDigest, ...] = ()

    @classmethod
    def from_provenance(cls, source: ModeloIvaWalletDecisionProvenance) -> Self:
        """Preserve every redacted wallet join field and convert its period."""
        return cls(
            decision_ref=source.decision_ref,
            selected_authority=source.selected_authority,
            divergence=source.divergence,
            target_year=source.target_year,
            target_period=PublicPeriod.from_period(source.target_period),
            authority_source_kinds=source.authority_source_kinds,
            authority_source_refs=source.authority_source_refs,
        )

    def to_provenance(self) -> ModeloIvaWalletDecisionProvenance:
        """Restore the canonical wallet join from public period coordinates."""
        return ModeloIvaWalletDecisionProvenance(
            decision_ref=self.decision_ref,
            selected_authority=self.selected_authority,
            divergence=self.divergence,
            target_year=self.target_year,
            target_period=self.target_period.to_period(),
            authority_source_kinds=self.authority_source_kinds,
            authority_source_refs=self.authority_source_refs,
        )


class ModeloFicheroBoePublicReceipt(BaseModel):
    """Complete canonical fichero-BOE receipt, excluding the locally written bytes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    bucket_id: BucketId
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: PublicPeriod
    output_path: str = Field(min_length=1)
    byte_size: NonNegativeInt
    file_sha256: ContentDigest
    format: str = Field(min_length=1)
    exported_at: datetime
    actor: str = Field(min_length=1, max_length=128)
    bucket_event_id: str = Field(min_length=1, max_length=128)
    resolved_result_disposition: ResultDisposition
    payment_election: PaymentElection | None
    refund_election: RefundElection | None
    prior_domiciliation_election: ModeloPriorDomiciliationPublicProvenance
    casilla_provenance: tuple[ModeloCasillaProvenance, ...]
    iva_wallet_decision_provenance: ModeloIvaWalletDecisionPublicProvenance | None
    local_evidence_status: str = Field(min_length=1)
    official_evidence_message: str = Field(min_length=1)
    completeness_unverified: bool
    software_identity_grade: AeatSoftwareIdentityGrade | None

    @classmethod
    def from_result(cls, result: ModeloExportResult) -> Self:
        """Retain every canonical receipt field in strict transport types."""
        return cls(
            calculation_revision_id=result.calculation_revision_id,
            work_unit_id=result.work_unit_id,
            bucket_id=result.bucket_id,
            modelo=result.modelo,
            filing_year=result.filing_year,
            period=PublicPeriod.from_period(result.period),
            output_path=str(result.output_path),
            byte_size=result.byte_size,
            file_sha256=result.file_sha256,
            format=result.format,
            exported_at=result.exported_at,
            actor=result.actor,
            bucket_event_id=result.bucket_event_id,
            resolved_result_disposition=result.resolved_result_disposition,
            payment_election=result.payment_election,
            refund_election=result.refund_election,
            prior_domiciliation_election=ModeloPriorDomiciliationPublicProvenance.from_provenance(
                result.prior_domiciliation_election
            ),
            casilla_provenance=result.casilla_provenance,
            iva_wallet_decision_provenance=(
                ModeloIvaWalletDecisionPublicProvenance.from_provenance(result.iva_wallet_decision_provenance)
                if result.iva_wallet_decision_provenance is not None
                else None
            ),
            local_evidence_status=result.local_evidence_status,
            official_evidence_message=result.official_evidence_message,
            completeness_unverified=result.completeness_unverified,
            software_identity_grade=result.software_identity_grade,
        )

    def to_result(self) -> ModeloExportResult:
        """Restore the canonical receipt for existing CLI/TUI rendering."""
        return ModeloExportResult(
            calculation_revision_id=self.calculation_revision_id,
            work_unit_id=self.work_unit_id,
            bucket_id=self.bucket_id,
            modelo=self.modelo,
            filing_year=self.filing_year,
            period=self.period.to_period(),
            output_path=Path(self.output_path),
            byte_size=self.byte_size,
            file_sha256=self.file_sha256,
            format=self.format,
            exported_at=self.exported_at,
            actor=self.actor,
            bucket_event_id=self.bucket_event_id,
            resolved_result_disposition=self.resolved_result_disposition,
            payment_election=self.payment_election,
            refund_election=self.refund_election,
            prior_domiciliation_election=self.prior_domiciliation_election.to_provenance(),
            casilla_provenance=self.casilla_provenance,
            iva_wallet_decision_provenance=(
                self.iva_wallet_decision_provenance.to_provenance()
                if self.iva_wallet_decision_provenance is not None
                else None
            ),
            local_evidence_status=self.local_evidence_status,
            official_evidence_message=self.official_evidence_message,
            completeness_unverified=self.completeness_unverified,
            software_identity_grade=self.software_identity_grade,
        )


class ModeloExportEvidenceStatus(StrEnum):
    """What one exported artefact is worth as evidence, in the export service's own terms.

    Neither artefact is official AEAT evidence; the two members keep apart the
    filing file an operator may present and the calculation record that can
    never be presented, because the remedy an operator reads differs.

    Attributes:
        LOCAL_EXPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE: The filing file's own
            status token. Official evidence comes from AEAT only after filing.
        LOCAL_CALCULATION_REPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE: A calculation
            report, whose receipt always carries the local-calculation notice
            saying it is not official AEAT filing evidence.
    """

    LOCAL_EXPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE = "local_export_not_official_aeat_filing_evidence"
    LOCAL_CALCULATION_REPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE = (
        "local_calculation_report_not_official_aeat_filing_evidence"
    )


class ModeloExportCompleteness(StrEnum):
    """What one export's receipt says about whether every required casilla reached the file.

    The export service states completeness only as a warning: it flags a
    fixed-width filing file whose revision declares no completeness manifest,
    because the structural-parity check could not run. Its silence is not a
    verification, so it keeps its own member rather than reading as verified.

    Attributes:
        UNVERIFIED: The receipt flags the filing file as not completeness-verified.
        NOT_FLAGGED: The filing file's receipt raises no completeness warning.
        NOT_ASSESSED: A calculation report, which makes no completeness statement.
    """

    UNVERIFIED = "unverified"
    NOT_FLAGGED = "not_flagged"
    NOT_ASSESSED = "not_assessed"


class ModeloExportPublicResultV2(BaseModel):
    """Evidence that one export happened and what it could establish, without the exported material.

    Custody of the artefact is the operator's from the moment it lands: this
    result names the file and fingerprints it so a later reader can prove which
    bytes were produced, and carries none of them. It also carries the three
    facts an operator needs before relying on the file -- its evidence status,
    its completeness and the grade of the software identity in its header -- so
    an incomplete or development-grade export is stated, never implied.

    A fichero-BOE export also carries the service's complete receipt, so a
    frontend reached through the runtime renders the same receipt the export
    service returned instead of re-deriving it from the summary.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

    result_version: int = 2
    calculation_revision_id: Annotated[str, Field(min_length=1, max_length=128)]
    artefact: ModeloExportArtefact
    #: The receipt's own format token: ``fichero-boe`` or the report's
    #: serialisation, exactly as the command line prints it.
    export_format: Annotated[str, Field(min_length=1, max_length=64)]
    #: ``pattern=r"\S"`` refuses an all-whitespace destination, which
    #: ``min_length`` alone admits. NOT stripped: a path must stay byte-exact,
    #: and silently trimming one would mask a typo rather than surface it.
    output_path: Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]
    byte_size: NonNegativeInt
    file_sha256: ContentDigest
    #: ``None`` when the artefact's layout reserves no software-identity slot.
    software_identity_grade: AeatSoftwareIdentityGrade | None
    evidence_status: ModeloExportEvidenceStatus
    completeness: ModeloExportCompleteness
    #: Present exactly when the artefact is the fichero-BOE.
    fichero_boe: ModeloFicheroBoePublicReceipt | None = None
    handoff_required: bool = True

    @model_validator(mode="after")
    def _receipt_matches_artefact(self) -> Self:
        """Refuse a fichero-BOE result without its receipt, or a report result carrying one."""
        if (self.artefact is ModeloExportArtefact.FICHERO_BOE) != (self.fichero_boe is not None):
            raise ValueError("a fichero-BOE export result carries exactly its receipt")
        return self


__all__ = [
    "ModeloExportCompleteness",
    "ModeloExportEvidenceStatus",
    "ModeloExportPublicResultV2",
    "ModeloFicheroBoePublicReceipt",
    "ModeloIvaWalletDecisionPublicProvenance",
    "ModeloPriorDomiciliationPublicProvenance",
]
