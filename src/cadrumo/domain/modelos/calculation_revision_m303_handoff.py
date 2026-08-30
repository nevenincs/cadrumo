"""Typed Modelo 303 annual handoff and filing-instance evidence."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import Final, Literal, Self

from pydantic import BaseModel, field_serializer, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.casilla_id import CasillaId
from ...core.filing_year import FilingYear
from ...core.hashing import content_hash_hex
from ...core.identity import BucketId, CalculationRevisionId, ContentDigest, WorkUnitId
from ..calculations.registry.ids import RevisionId
from ..calculations.registry.m303_orden_projection_models import M303RegimenSimplificadoSnapshot
from ..filing_evidence import FilingEvidenceReference
from ..identifiers import canonical_decimal_string as _canonical_decimal
from ..iva.refund_eligibility import is_last_filing_period_of_year
from ..iva.regimen_simplificado_rows import ActividadNoAgricolaSimplificado, M303RegimenSimplificadoScopeDecision, RegimenSimplificadoActivity, RegimenSimplificadoFilingRows
from .calculation_revision_m303_evidence import (
    M303DANA2024EligibilityEvidence,
    M303Exonerado390FilingEvidence,
    M303InsolvencyFilingFact,
    M303RegimenSimplificadoActivityCalculationResult,
    M303RegimenSimplificadoCalculationResult,
)
from .errors import ModeloValidationError

# The 2022 Modelo 390 record design declares these ten annual simplified-regime
# endpoints in this semantic order.  Keep the source-declared 51, 53, 52 order
# on the sibling selector; this target order follows the official 74--83 page.
M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS: Final[tuple[CasillaId, ...]] = (
    "iva.anual.regimen-simplificado.cuota-resultante-no-agricola",
    "iva.anual.regimen-simplificado.cuota-resultante-agricola",
    "iva.anual.regimen-simplificado.aic-bienes-cuota-devengada",
    "iva.anual.regimen-simplificado.inversion-sujeto-pasivo",
    "iva.anual.regimen-simplificado.entrega-activos-fijos",
    "iva.anual.reconciliacion.devengada-simplificado-303",
    "iva.anual.regimen-simplificado.iva-soportado-activos-fijos",
    "iva.anual.regimen-simplificado.regularizacion-bienes-inversion",
    "iva.anual.regimen-simplificado.suma-deducciones",
    "iva.anual.regimen-simplificado.resultado",
)
"""Canonical Modelo 390 casilla endpoints for the immutable 303 4T handoff."""


class M303RegimenSimplificadoAnnualSummaryHandoff(BaseModel):
    """One frozen, source-identified Modelo 303 4T -> Modelo 390 0A handoff.

    The handoff is calculated before its enclosing target revision has an id.
    Its digest and unsigned identity payload therefore deliberately exclude
    :attr:`target_calculation_revision_id`; persistence derives the target
    revision id from the unsigned payload and then stamps that id on this
    immutable envelope.  No relation, observation replay, or manual binding
    override can substitute for this exact source calculation contract.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_bucket_id: BucketId
    source_modelo: Literal["303"] = "303"
    source_work_unit_id: WorkUnitId
    source_calculation_revision_id: CalculationRevisionId
    source_registry_revision_id: RevisionId
    source_filing_year: FilingYear
    source_period: Period
    source_result_digest: ContentDigest
    # An exact empty tuple is meaningful when the immutable, filed 303 evidence
    # positively proves that the simplified-regime activity cohort is empty.
    # It must remain distinguishable from a missing filing-instance envelope,
    # which the application assembler refuses before it reaches this carrier.
    source_evidence_references: tuple[FilingEvidenceReference, ...] = ()
    target_bucket_id: BucketId
    target_modelo: Literal["390"] = "390"
    target_work_unit_id: WorkUnitId
    target_registry_revision_id: RevisionId
    target_filing_year: FilingYear
    target_period: Period
    values: Mapping[CasillaId, Decimal]
    target_calculation_revision_id: CalculationRevisionId | None = None
    digest: ContentDigest

    @classmethod
    def assembled(
        cls,
        *,
        source_bucket_id: BucketId,
        source_work_unit_id: WorkUnitId,
        source_calculation_revision_id: CalculationRevisionId,
        source_registry_revision_id: RevisionId,
        source_filing_year: int,
        source_result_digest: ContentDigest,
        source_evidence_references: tuple[FilingEvidenceReference, ...],
        target_bucket_id: BucketId,
        target_work_unit_id: WorkUnitId,
        target_registry_revision_id: RevisionId,
        target_filing_year: int,
        values: Mapping[CasillaId, Decimal],
    ) -> Self:
        """Build an unsigned handoff with its content digest.

        This is the only pre-persistence constructor.  It fixes the source to
        the annual fourth quarter and the target to the annual Modelo 390
        period, so application callers cannot accidentally form a quarterly or
        cross-year carrier and then rely on a later projection to repair it.
        """
        source_period = Period.from_year_and_code(source_filing_year, "4T")
        target_period = Period.from_year_and_code(target_filing_year, "0A")
        unsigned = cls.model_construct(
            source_bucket_id=source_bucket_id,
            source_work_unit_id=source_work_unit_id,
            source_calculation_revision_id=source_calculation_revision_id,
            source_registry_revision_id=source_registry_revision_id,
            source_filing_year=source_filing_year,
            source_period=source_period,
            source_result_digest=source_result_digest,
            source_evidence_references=source_evidence_references,
            target_bucket_id=target_bucket_id,
            target_work_unit_id=target_work_unit_id,
            target_registry_revision_id=target_registry_revision_id,
            target_filing_year=target_filing_year,
            target_period=target_period,
            values=values,
            target_calculation_revision_id=None,
            digest="",
        )
        return cls(
            source_bucket_id=source_bucket_id,
            source_work_unit_id=source_work_unit_id,
            source_calculation_revision_id=source_calculation_revision_id,
            source_registry_revision_id=source_registry_revision_id,
            source_filing_year=source_filing_year,
            source_period=source_period,
            source_result_digest=source_result_digest,
            source_evidence_references=source_evidence_references,
            target_bucket_id=target_bucket_id,
            target_work_unit_id=target_work_unit_id,
            target_registry_revision_id=target_registry_revision_id,
            target_filing_year=target_filing_year,
            target_period=target_period,
            values=values,
            digest=_m303_regimen_simplificado_annual_summary_handoff_digest(unsigned),
        )

    def stamped_for_target_calculation_revision(
        self,
        target_calculation_revision_id: CalculationRevisionId,
    ) -> Self:
        """Return this unsigned carrier stamped for its containing revision."""
        return type(self).model_validate(
            {
                **self.model_dump(mode="python"),
                "target_calculation_revision_id": target_calculation_revision_id,
            },
        )

    def unsigned_identity_payload(self) -> dict[str, object]:
        """Return the canonical, target-id-free payload used in revision identity."""
        return _m303_regimen_simplificado_annual_summary_handoff_payload(self)

    @field_validator("values")
    @classmethod
    def _freeze_exact_ten_values(cls, value: Mapping[CasillaId, Decimal]) -> Mapping[CasillaId, Decimal]:
        values = dict(value)
        expected = set(M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS)
        actual = set(values)
        if actual != expected:
            raise ModeloValidationError(
                "M303 simplified annual-summary handoff must carry exactly the ten Modelo 390 boxes "
                f"74-83; missing={sorted(expected - actual)!r} extra={sorted(actual - expected)!r}",
            )
        return MappingProxyType(
            {casilla_id: values[casilla_id] for casilla_id in M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS},
        )

    @field_serializer("values")
    def _serialize_values(self, value: Mapping[CasillaId, Decimal]) -> dict[CasillaId, Decimal]:
        """Emit the immutable mapping as an ordinary canonical JSON object."""
        return dict(value)

    @model_validator(mode="after")
    def _validate_immutable_coordinate_and_digest(self) -> M303RegimenSimplificadoAnnualSummaryHandoff:
        if self.source_bucket_id != self.target_bucket_id:
            raise ModeloValidationError("M303 simplified annual-summary handoff source and target bucket must agree")
        if self.source_filing_year != self.target_filing_year:
            raise ModeloValidationError(
                "M303 simplified annual-summary handoff source and target filing year must agree"
            )
        if self.source_period != Period.from_year_and_code(self.source_filing_year, "4T"):
            raise ModeloValidationError("M303 simplified annual-summary handoff source period must be 4T")
        if self.target_period != Period.from_year_and_code(self.target_filing_year, "0A"):
            raise ModeloValidationError("M303 simplified annual-summary handoff target period must be 0A")
        expected_digest = _m303_regimen_simplificado_annual_summary_handoff_digest(self)
        if self.digest != expected_digest:
            raise ModeloValidationError(
                "M303 simplified annual-summary handoff digest does not match its immutable unsigned payload",
            )
        return self


def _m303_regimen_simplificado_annual_summary_handoff_payload(
    handoff: M303RegimenSimplificadoAnnualSummaryHandoff,
) -> dict[str, object]:
    """Canonical target-id-free payload for the annual Modelo 390 handoff."""
    return {
        "source": {
            "bucket_id": handoff.source_bucket_id,
            "modelo": handoff.source_modelo,
            "work_unit_id": handoff.source_work_unit_id,
            "calculation_revision_id": handoff.source_calculation_revision_id,
            "registry_revision_id": handoff.source_registry_revision_id,
            "filing_year": handoff.source_filing_year,
            "period": handoff.source_period.registry_token,
            "result_digest": handoff.source_result_digest,
            "evidence_references": tuple(item.model_dump(mode="json") for item in handoff.source_evidence_references),
        },
        "target": {
            "bucket_id": handoff.target_bucket_id,
            "modelo": handoff.target_modelo,
            "work_unit_id": handoff.target_work_unit_id,
            "registry_revision_id": handoff.target_registry_revision_id,
            "filing_year": handoff.target_filing_year,
            "period": handoff.target_period.registry_token,
        },
        "values": tuple(
            {
                "casilla_id": casilla_id,
                "value": _canonical_decimal(handoff.values[casilla_id]),
            }
            for casilla_id in M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS
        ),
    }


def _m303_regimen_simplificado_annual_summary_handoff_digest(
    handoff: M303RegimenSimplificadoAnnualSummaryHandoff,
) -> str:
    """Return the digest of a handoff without its post-derivation target id."""
    return content_hash_hex(_m303_regimen_simplificado_annual_summary_handoff_payload(handoff))


class M303RegimenSimplificadoFilingEvidence(BaseModel):
    """Taxpayer rows bound to the exact S59 Orden and record-design snapshot."""

    model_config = STRICT_FROZEN_CONFIG

    scope_decision: M303RegimenSimplificadoScopeDecision
    rows: RegimenSimplificadoFilingRows
    regimen_snapshot: M303RegimenSimplificadoSnapshot
    dana_2024_eligibility: M303DANA2024EligibilityEvidence | None
    calculation_result: M303RegimenSimplificadoCalculationResult

    @model_validator(mode="after")
    def _rows_match_scope_and_snapshot(self) -> M303RegimenSimplificadoFilingEvidence:
        if self.scope_decision != self.regimen_snapshot.scope_decision:
            raise ModeloValidationError("M303 simplified-regime evidence scope disagrees with its S59 snapshot")
        if self.rows.ejercicio != self.regimen_snapshot.orden.ejercicio:
            raise ModeloValidationError("M303 simplified-regime evidence year disagrees with its S59 snapshot")
        _validate_m303_regimen_simplificado_result_coordinate(self)
        if self.scope_decision.is_not_claimed:
            if self.rows.activities:
                raise ModeloValidationError("general M303 scope must not carry simplified-regime activity evidence")
        elif not self.rows.activities:
            raise ModeloValidationError("simplified or mixed M303 scope requires activity evidence")
        return self


def _validate_m303_regimen_simplificado_result_coordinate(
    evidence: M303RegimenSimplificadoFilingEvidence,
) -> None:
    """Require the retained result to name exactly these rows and S59 coordinate."""
    _validate_m303_result_snapshot_coordinate(evidence)
    _validate_m303_result_activity_order(evidence)
    _validate_m303_result_activity_evidence(evidence)


def _validate_m303_result_snapshot_coordinate(evidence: M303RegimenSimplificadoFilingEvidence) -> None:
    result = evidence.calculation_result
    orden = evidence.regimen_snapshot.orden
    record_design = evidence.regimen_snapshot.record_design
    if (
        result.ejercicio,
        result.registry_revision_id,
        result.orden_source_ref,
        result.orden_source_content_digest,
        result.record_design_source_ref,
        result.record_design_content_digest,
        result.record_design_epoch,
    ) != (
        orden.ejercicio,
        orden.registry_revision_id,
        orden.source_ref,
        orden.source_content_digest,
        record_design.id,
        record_design.sha256,
        record_design.record_design_epoch,
    ):
        raise ModeloValidationError("M303 simplified calculation result disagrees with its S59 coordinate")


def _validate_m303_result_activity_order(evidence: M303RegimenSimplificadoFilingEvidence) -> None:
    result = evidence.calculation_result
    row_activities = tuple(evidence.rows.activities)
    if tuple(item.activity_id for item in result.activities) != tuple(item.activity_id for item in row_activities):
        raise ModeloValidationError("M303 simplified calculation result must retain every filing activity in row order")
    if tuple(item.orden_id for item in result.activities) != tuple(item.orden_id for item in row_activities):
        raise ModeloValidationError("M303 simplified calculation result Orden identities disagree with filing rows")


def _validate_m303_result_activity_evidence(evidence: M303RegimenSimplificadoFilingEvidence) -> None:
    row_activities = tuple(evidence.rows.activities)
    for row, activity_result in zip(row_activities, evidence.calculation_result.activities, strict=True):
        _validate_m303_result_activity_row(activity_result, row)


def _validate_m303_result_activity_row(
    activity_result: M303RegimenSimplificadoActivityCalculationResult,
    row: RegimenSimplificadoActivity,
) -> None:
    if not isinstance(row, ActividadNoAgricolaSimplificado):
        raise ModeloValidationError("M303 simplified calculation result cannot resolve agricultural activity rows")
    expected_evidence = _m303_regimen_simplificado_activity_evidence_references(row)
    if activity_result.evidence_references != expected_evidence:
        raise ModeloValidationError(
            "M303 simplified calculation result evidence references disagree with filing rows",
        )
    if tuple(item.module_identity for item in activity_result.module_results) != tuple(
        item.module_identity for item in row.modulos
    ):
        raise ModeloValidationError("M303 simplified calculation result modules disagree with filing rows")
    if tuple(item.evidence_reference for item in activity_result.module_results) != tuple(
        item.evidence_reference for item in row.modulos
    ):
        raise ModeloValidationError("M303 simplified calculation result module evidence disagrees with filing rows")


def _m303_regimen_simplificado_activity_evidence_references(
    row: RegimenSimplificadoActivity,
) -> tuple[FilingEvidenceReference, ...]:
    """Return the ordered immutable evidence identity carried by one filing row."""
    if not isinstance(row, ActividadNoAgricolaSimplificado):
        return (row.evidence_reference, *(item.evidence_reference for item in row.facts))
    return (
        row.evidence_reference,
        *(item.evidence_reference for item in row.modulos),
        *(item.evidence_reference for item in row.facts),
    )


class M303FilingInstanceEvidence(BaseModel):
    """Complete operator-selected facts bound to one Modelo 303 revision."""

    model_config = STRICT_FROZEN_CONFIG

    period: Period
    joint_return_elected: bool
    annual_volume_nonzero: bool
    insolvency: M303InsolvencyFilingFact | None
    exonerado_390: M303Exonerado390FilingEvidence
    regimen_simplificado: M303RegimenSimplificadoFilingEvidence

    @model_validator(mode="after")
    def _all_evidence_uses_the_filing_year(self) -> M303FilingInstanceEvidence:
        if self.regimen_simplificado.rows.ejercicio != self.period.filing_year:
            raise ModeloValidationError("M303 filing evidence must use the work-period filing year")
        result = self.regimen_simplificado.calculation_result
        if result.period != self.period:
            raise ModeloValidationError("M303 simplified calculation result must use the filing period")
        eligibility = self.regimen_simplificado.dana_2024_eligibility
        requires_dana_eligibility = (
            self.period.filing_year == 2024
            and is_last_filing_period_of_year(self.period)
            and not self.regimen_simplificado.scope_decision.is_not_claimed
        )
        if requires_dana_eligibility != (eligibility is not None):
            raise ModeloValidationError(
                "M303 DANA eligibility evidence is valid only for the 2024 annual simplified result",
            )
        return self


class FilingInstanceEvidence(BaseModel):
    """Closed filing-instance evidence envelope persisted on a revision."""

    model_config = STRICT_FROZEN_CONFIG

    m303: M303FilingInstanceEvidence
