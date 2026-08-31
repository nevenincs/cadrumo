"""Typed Modelo 303 filing evidence calculation payloads."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from ...core.record_design_epoch import RECORD_DESIGN_EPOCH_PATTERN
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.casilla_id import CasillaId
from ...core.filing_year import FilingYear
from ...core.hashing import content_hash_hex
from ...core.identity import ContentDigest
from ...core.unit_proportion import UnitProportion
from ..calculations.registry.ids import LegalRefId, RevisionId, SourceRefId
from ..filing_evidence import FilingEvidenceReference
from .errors import ModeloValidationError


class M303InsolvencyFilingSubtype(StrEnum):
    """Official Modelo 303 insolvency declaration subtype."""

    PRE_ORDER = "pre_order"
    POST_ORDER = "post_order"


class M303InsolvencyFilingFact(BaseModel):
    """Atomic judicial-order evidence for one Modelo 303 filing instance."""

    model_config = STRICT_FROZEN_CONFIG

    judicial_order_date: date
    subtype: M303InsolvencyFilingSubtype


class M303Exonerado390EndpointEvidence(BaseModel):
    """One evidenced annual-summary endpoint selected for the filing revision."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    value: Decimal
    evidence_reference: FilingEvidenceReference


_M303Exonerado390CodigoActividad = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=3, to_upper=True),
]
_M303Exonerado390EpigrafeIae = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4, to_upper=True),
]


# The AEAT DP30304 record design carries six (Clave, Epigrafe IAE) pairs - the
# Principal pair plus Otras 1a through 5a - but marks none of them Obligatorio.
# Six is the record's capacity, bounded by the slot field, not a population
# requirement: a filer carrying one activity states one row. Requiring six would
# force five fabricated activities, because both row fields reject blanks.


class M303Exonerado390ActivityRowEvidence(BaseModel):
    """One ordered evidenced activity row for the exonerado-390 population."""

    model_config = STRICT_FROZEN_CONFIG

    slot: int = Field(ge=1, le=6)
    codigo_actividad: _M303Exonerado390CodigoActividad
    epigrafe_iae: _M303Exonerado390EpigrafeIae
    evidence_reference: FilingEvidenceReference


class M303Exonerado390FilingEvidence(BaseModel):
    """Resolved A28 applicability and its complete evidenced annual population."""

    model_config = STRICT_FROZEN_CONFIG

    applicable: bool
    applicability_reference: FilingEvidenceReference
    endpoints: tuple[M303Exonerado390EndpointEvidence, ...]
    activity_rows: tuple[M303Exonerado390ActivityRowEvidence, ...]
    operaciones_terceros_declarables: bool | None
    operaciones_terceros_reference: FilingEvidenceReference | None

    @model_validator(mode="after")
    def _applicability_matches_endpoint_population(self) -> M303Exonerado390FilingEvidence:
        _validate_m303_exonerado_endpoint_ids(self.endpoints)
        if self.applicable:
            _validate_applicable_m303_exonerado_evidence(self)
        else:
            _validate_non_applicable_m303_exonerado_evidence(self)
        return self


def _validate_m303_exonerado_endpoint_ids(
    endpoints: tuple[M303Exonerado390EndpointEvidence, ...],
) -> None:
    endpoint_ids = tuple(endpoint.casilla_id for endpoint in endpoints)
    if len(set(endpoint_ids)) != len(endpoint_ids):
        raise ModeloValidationError("M303 exonerado-390 evidence contains duplicate endpoint casillas")


def _validate_applicable_m303_exonerado_evidence(evidence: M303Exonerado390FilingEvidence) -> None:
    if not evidence.endpoints:
        raise ModeloValidationError("applicable M303 exonerado-390 evidence requires endpoint facts")
    if not evidence.activity_rows:
        raise ModeloValidationError("applicable M303 exonerado-390 evidence requires activity rows")
    row_slots = tuple(row.slot for row in evidence.activity_rows)
    if row_slots != tuple(range(1, len(row_slots) + 1)):
        raise ModeloValidationError(
            "M303 exonerado-390 activity rows must use contiguous ordered slots 1-6",
        )
    if evidence.operaciones_terceros_declarables is None or evidence.operaciones_terceros_reference is None:
        raise ModeloValidationError("applicable M303 exonerado-390 evidence requires the Modelo 347 decision")


def _validate_non_applicable_m303_exonerado_evidence(evidence: M303Exonerado390FilingEvidence) -> None:
    if evidence.endpoints or evidence.activity_rows:
        raise ModeloValidationError("non-applicable M303 exonerado-390 evidence must not carry annual facts")
    if evidence.operaciones_terceros_declarables is not None or evidence.operaciones_terceros_reference is not None:
        raise ModeloValidationError(
            "non-applicable M303 exonerado-390 evidence must not carry a Modelo 347 decision",
        )


class M303DANA2024EligibilityEvidence(BaseModel):
    """Attested DANA eligibility without transcribing the mutable municipal anexo."""

    model_config = STRICT_FROZEN_CONFIG

    eligible: bool
    evidence_reference: FilingEvidenceReference


class M303RegimenSimplificadoModuleCalculationResult(BaseModel):
    """One annual-Orden module calculation and its input/source evidence."""

    model_config = STRICT_FROZEN_CONFIG

    module_identity: str
    declared_quantity: Decimal = Field(ge=Decimal("0"))
    coefficient: Decimal = Field(gt=Decimal("0"))
    cuota_devengada: Decimal = Field(ge=Decimal("0"))
    evidence_reference: FilingEvidenceReference
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


class M303DANA2024ReductionResult(BaseModel):
    """The annually-applied DANA reduction for one evidenced activity."""

    model_config = STRICT_FROZEN_CONFIG

    eligible: bool
    rate: UnitProportion
    amount: Decimal = Field(ge=Decimal("0"))
    evidence_reference: FilingEvidenceReference
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _ineligible_reduction_is_zero(self) -> M303DANA2024ReductionResult:
        if not self.eligible and self.amount != Decimal("0"):
            raise ModeloValidationError("an ineligible DANA reduction must be zero")
        return self


class M303RegimenSimplificadoActivityCalculationResult(BaseModel):
    """One immutable no-agricultural activity result for an annual Orden row."""

    model_config = STRICT_FROZEN_CONFIG

    activity_id: str
    orden_id: str
    module_results: tuple[M303RegimenSimplificadoModuleCalculationResult, ...] = Field(min_length=1, max_length=7)
    evidence_references: tuple[FilingEvidenceReference, ...] = Field(min_length=1)
    cuota_devengada_operaciones_corrientes: Decimal = Field(ge=Decimal("0"))
    cuota_devengada_tras_dana_2024: Decimal = Field(ge=Decimal("0"))
    deduccion_dificil_justificacion: Decimal = Field(ge=Decimal("0"))
    cuota_minima: Decimal = Field(ge=Decimal("0"))
    dana_2024_reduction: M303DANA2024ReductionResult | None
    cuota_resultante: Decimal = Field(ge=Decimal("0"))
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _amounts_form_one_closed_activity_result(self) -> M303RegimenSimplificadoActivityCalculationResult:
        module_ids = tuple(item.module_identity for item in self.module_results)
        if len(set(module_ids)) != len(module_ids):
            raise ModeloValidationError("M303 simplified calculation result contains duplicate modules")
        reduction = self.dana_2024_reduction.amount if self.dana_2024_reduction is not None else Decimal("0")
        if self.cuota_devengada_tras_dana_2024 != self.cuota_devengada_operaciones_corrientes - reduction:
            raise ModeloValidationError("M303 simplified activity result has an incoherent DANA annual cuota")
        if self.cuota_resultante != max(
            self.cuota_devengada_tras_dana_2024 - self.deduccion_dificil_justificacion,
            self.cuota_minima,
        ):
            raise ModeloValidationError("M303 simplified activity result has an incoherent annual cuota")
        return self


class M303RegimenSimplificadoCalculationResult(BaseModel):
    """Content-addressed annual-Orden result retained beside immutable filing rows."""

    model_config = STRICT_FROZEN_CONFIG

    ejercicio: FilingYear
    registry_revision_id: RevisionId
    period: Period
    orden_source_ref: SourceRefId
    orden_source_content_digest: ContentDigest
    record_design_source_ref: SourceRefId
    record_design_content_digest: ContentDigest
    #: Shape-constrained at the ARTEFACT boundary, not only where it is declared.
    #: A build-time check on the registry proves the tag is well formed where it is
    #: authored; it says nothing about a value arriving here by any other route, and
    #: this field is stamped into filing evidence. ``min_length=1`` accepted strings
    #: the registry would have refused, so the two boundaries disagreed about what an
    #: epoch is -- with the weaker one downstream.
    record_design_epoch: str = Field(min_length=1, pattern=RECORD_DESIGN_EPOCH_PATTERN)
    activities: tuple[M303RegimenSimplificadoActivityCalculationResult, ...]
    digest: ContentDigest

    @classmethod
    def calculated(
        cls,
        *,
        ejercicio: int,
        registry_revision_id: RevisionId,
        period: Period,
        orden_source_ref: SourceRefId,
        orden_source_content_digest: str,
        record_design_source_ref: SourceRefId,
        record_design_content_digest: str,
        record_design_epoch: str,
        activities: tuple[M303RegimenSimplificadoActivityCalculationResult, ...],
    ) -> Self:
        """Build a result with the deterministic digest of its typed payload."""
        unsigned = cls.model_construct(
            ejercicio=ejercicio,
            registry_revision_id=registry_revision_id,
            period=period,
            orden_source_ref=orden_source_ref,
            orden_source_content_digest=orden_source_content_digest,
            record_design_source_ref=record_design_source_ref,
            record_design_content_digest=record_design_content_digest,
            record_design_epoch=record_design_epoch,
            activities=activities,
            digest="",
        )
        return cls(
            ejercicio=ejercicio,
            registry_revision_id=registry_revision_id,
            period=period,
            orden_source_ref=orden_source_ref,
            orden_source_content_digest=orden_source_content_digest,
            record_design_source_ref=record_design_source_ref,
            record_design_content_digest=record_design_content_digest,
            record_design_epoch=record_design_epoch,
            activities=activities,
            digest=_m303_regimen_simplificado_result_digest(unsigned),
        )

    @model_validator(mode="after")
    def _is_content_addressed_and_period_scoped(self) -> M303RegimenSimplificadoCalculationResult:
        if self.period.filing_year != self.ejercicio:
            raise ModeloValidationError("M303 simplified calculation result period must use its annual Orden year")
        activity_ids = tuple(item.activity_id for item in self.activities)
        if len(set(activity_ids)) != len(activity_ids):
            raise ModeloValidationError("M303 simplified calculation result contains duplicate activities")
        expected_digest = _m303_regimen_simplificado_result_digest(self)
        if self.digest != expected_digest:
            raise ModeloValidationError(
                "M303 simplified calculation result digest does not match its immutable payload",
            )
        return self


def _m303_regimen_simplificado_result_digest(result: M303RegimenSimplificadoCalculationResult) -> str:
    """Return the clock-free content identity for one result payload."""
    return content_hash_hex(result.model_dump(mode="json", exclude={"digest"}))
