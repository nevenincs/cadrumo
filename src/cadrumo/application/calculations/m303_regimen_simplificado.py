"""Canonical annual-Orden calculation for Modelo 303 simplified-regime rows."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import cast

from ...core.decimal.constants import HUNDRED
from ...core.errors.hierarchy import CoreValidationError
from ...core.money.rounding import round_to_cents
from ...core.period import Period
from ...domain.calculations.registry.authority import ValidatedRegistryAuthority
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
from ...domain.calculations.registry.m303_orden_projection_models import M303RegimenSimplificadoSnapshot
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.iva.refund_eligibility import is_last_filing_period_of_year
from ...domain.iva.regimen_simplificado_rows import (
    ActividadNoAgricolaSimplificado,
    ActividadOrdenAnual,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
    validate_regimen_simplificado_rows,
)
from ...domain.modelos.calculation_revision_m303_evidence import (
    M303DANA2024EligibilityEvidence,
    M303DANA2024ReductionResult,
    M303RegimenSimplificadoActivityCalculationResult,
    M303RegimenSimplificadoCalculationResult,
    M303RegimenSimplificadoModuleCalculationResult,
)

_DANA_2024_REDUCTION_FACT_ID = "rdl-7-2024-art-11-2:iva-simplificado-reduccion-cuota-devengada"


class M303RegimenSimplificadoCalculationError(CoreValidationError):
    """Raised when exact annual-Orden inputs cannot form a calculation result."""


def calculate_m303_regimen_simplificado_result(
    *,
    period: Period,
    scope_decision: M303RegimenSimplificadoScopeDecision,
    rows: RegimenSimplificadoFilingRows,
    regimen_snapshot: M303RegimenSimplificadoSnapshot,
    dana_2024_eligibility: M303DANA2024EligibilityEvidence | None,
    authority: ValidatedRegistryAuthority | None = None,
) -> M303RegimenSimplificadoCalculationResult:
    """Calculate one immutable, source-pinned annual result from filing rows."""
    _validate_coordinate(
        period=period,
        scope_decision=scope_decision,
        rows=rows,
        regimen_snapshot=regimen_snapshot,
        dana_2024_eligibility=dana_2024_eligibility,
        authority=authority,
    )
    _validate_rows_against_annual_orden(rows=rows, regimen_snapshot=regimen_snapshot, scope_decision=scope_decision)
    dana_authority = None
    if dana_2024_eligibility is not None:
        if authority is None:
            raise M303RegimenSimplificadoCalculationError(
                "DANA eligibility requires a validated registry authority",
            )
        dana_authority = _resolve_dana_2024_authority(authority=authority, effective_date=period.end_date)
    annual_by_id = {activity.orden_id: activity for activity in regimen_snapshot.orden.activities}
    activities = tuple(
        _calculate_no_agricultural_activity(
            row=row,
            annual=annual_by_id[row.orden_id],
            difficult_justification_pct=regimen_snapshot.orden.difficult_justification.percentage,
            difficult_justification_legal_refs=regimen_snapshot.orden.difficult_justification.legal_refs,
            difficult_justification_source_refs=regimen_snapshot.orden.difficult_justification.source_refs,
            dana_eligibility=dana_2024_eligibility,
            dana_authority=dana_authority,
        )
        for row in rows.activities
        if isinstance(row, ActividadNoAgricolaSimplificado)
    )
    orden = regimen_snapshot.orden
    record_design = regimen_snapshot.record_design
    if record_design.record_design_epoch is None:
        raise M303RegimenSimplificadoCalculationError("M303 simplified record design must retain its epoch")
    return M303RegimenSimplificadoCalculationResult.calculated(
        ejercicio=orden.ejercicio,
        registry_revision_id=orden.registry_revision_id,
        period=period,
        orden_source_ref=orden.source_ref,
        orden_source_content_digest=orden.source_content_digest,
        record_design_source_ref=record_design.id,
        record_design_content_digest=record_design.sha256,
        record_design_epoch=record_design.record_design_epoch,
        activities=activities,
    )


def _validate_coordinate(
    *,
    period: Period,
    scope_decision: M303RegimenSimplificadoScopeDecision,
    rows: RegimenSimplificadoFilingRows,
    regimen_snapshot: M303RegimenSimplificadoSnapshot,
    dana_2024_eligibility: M303DANA2024EligibilityEvidence | None,
    authority: ValidatedRegistryAuthority | None,
) -> None:
    if rows.ejercicio != period.filing_year or regimen_snapshot.orden.ejercicio != period.filing_year:
        raise M303RegimenSimplificadoCalculationError("M303 simplified rows and annual Orden must use the filing year")
    if regimen_snapshot.scope_decision != scope_decision:
        raise M303RegimenSimplificadoCalculationError("M303 simplified scope must match the annual Orden snapshot")
    requires_dana_eligibility = (
        _dana_reduction_is_available(authority=authority, effective_date=period.end_date)
        and is_last_filing_period_of_year(period)
        and not scope_decision.is_not_claimed
    )
    if requires_dana_eligibility != (dana_2024_eligibility is not None):
        raise M303RegimenSimplificadoCalculationError(
            "M303 DANA eligibility evidence is required only when the selected registry reduction applies to the annual simplified result",
        )


def _dana_reduction_is_available(
    *,
    authority: ValidatedRegistryAuthority | None,
    effective_date: date,
) -> bool:
    """Return whether the selected authority publishes the DANA reduction now.

    The applicability window belongs to the governed scalar fact.  This
    coordinate check therefore asks the same authority used to resolve the
    reduction instead of encoding a filing year in the calculation module.
    """
    if authority is None:
        from ...domain.calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    try:
        authority.resolve_governed_fact(
            ScalarFactQuery(
                fact_id=_DANA_2024_REDUCTION_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        )
    except RegistryValidationError:
        return False
    return True


def _validate_rows_against_annual_orden(
    *,
    rows: RegimenSimplificadoFilingRows,
    regimen_snapshot: M303RegimenSimplificadoSnapshot,
    scope_decision: M303RegimenSimplificadoScopeDecision,
) -> None:
    try:
        validate_regimen_simplificado_rows(
            rows,
            orden=regimen_snapshot.orden.activities,
            agricultural_authority=regimen_snapshot.orden.agricultural_authority,
            applicable=not scope_decision.is_not_claimed,
            censo_iae_epigraphs=frozenset(
                row.iae_epigrafe for row in rows.activities if isinstance(row, ActividadNoAgricolaSimplificado)
            ),
        )
    except ValueError as exc:
        raise M303RegimenSimplificadoCalculationError(str(exc)) from exc


def _calculate_no_agricultural_activity(
    *,
    row: ActividadNoAgricolaSimplificado,
    annual: ActividadOrdenAnual,
    difficult_justification_pct: Decimal,
    difficult_justification_legal_refs: tuple[str, ...],
    difficult_justification_source_refs: tuple[str, ...],
    dana_eligibility: M303DANA2024EligibilityEvidence | None,
    dana_authority: _DANA2024Authority | None,
) -> M303RegimenSimplificadoActivityCalculationResult:
    if annual.kind != "no_agricola":
        raise M303RegimenSimplificadoCalculationError(
            "M303 simplified calculation requires a non-agricultural annual Orden row",
        )
    modules = _calculate_activity_modules(row=row, annual=annual)
    cuota_devengada = _sum_module_cuotas(modules)
    dana_reduction = _calculate_dana_2024_reduction(
        cuota_devengada=cuota_devengada,
        eligibility=dana_eligibility,
        authority=dana_authority,
    )
    cuota_tras_dana = _cuota_after_dana(cuota_devengada, dana_reduction)
    difficult, minimum = _calculate_activity_adjustments(
        cuota_tras_dana=cuota_tras_dana,
        difficult_justification_pct=difficult_justification_pct,
        minimum_pct=annual.cuota_minima_pct,
    )
    activity_legal_refs, activity_source_refs = _activity_provenance(
        annual=annual,
        modules=modules,
        difficult_justification_legal_refs=difficult_justification_legal_refs,
        difficult_justification_source_refs=difficult_justification_source_refs,
        dana_reduction=dana_reduction,
    )
    return M303RegimenSimplificadoActivityCalculationResult(
        activity_id=row.activity_id,
        orden_id=row.orden_id,
        module_results=modules,
        evidence_references=(
            row.evidence_reference,
            *(item.evidence_reference for item in row.modulos),
            *(item.evidence_reference for item in row.facts),
        ),
        cuota_devengada_operaciones_corrientes=cuota_devengada,
        cuota_devengada_tras_dana_2024=cuota_tras_dana,
        deduccion_dificil_justificacion=difficult,
        cuota_minima=minimum,
        dana_2024_reduction=dana_reduction,
        cuota_resultante=max(cuota_tras_dana - difficult, minimum),
        legal_refs=activity_legal_refs,
        source_refs=activity_source_refs,
    )


def _calculate_activity_modules(
    *,
    row: ActividadNoAgricolaSimplificado,
    annual: ActividadOrdenAnual,
) -> tuple[M303RegimenSimplificadoModuleCalculationResult, ...]:
    return tuple(
        M303RegimenSimplificadoModuleCalculationResult(
            module_identity=declared.module_identity,
            declared_quantity=declared.declared_quantity,
            coefficient=published.coefficient,
            cuota_devengada=round_to_cents(declared.declared_quantity * published.coefficient),
            evidence_reference=declared.evidence_reference,
            legal_refs=published.legal_refs,
            source_refs=published.source_refs,
        )
        for declared, published in zip(row.modulos, annual.modulos, strict=True)
    )


def _sum_module_cuotas(modules: tuple[M303RegimenSimplificadoModuleCalculationResult, ...]) -> Decimal:
    return round_to_cents(sum((item.cuota_devengada for item in modules), start=Decimal("0")))


def _cuota_after_dana(
    cuota_devengada: Decimal,
    dana_reduction: M303DANA2024ReductionResult | None,
) -> Decimal:
    reduction = dana_reduction.amount if dana_reduction is not None else Decimal("0")
    return cuota_devengada - reduction


def _calculate_activity_adjustments(
    *,
    cuota_tras_dana: Decimal,
    difficult_justification_pct: Decimal,
    minimum_pct: Decimal,
) -> tuple[Decimal, Decimal]:
    difficult = round_to_cents(cuota_tras_dana * difficult_justification_pct / HUNDRED)
    minimum = round_to_cents(cuota_tras_dana * minimum_pct / HUNDRED)
    return difficult, minimum


def _activity_provenance(
    *,
    annual: ActividadOrdenAnual,
    modules: tuple[M303RegimenSimplificadoModuleCalculationResult, ...],
    difficult_justification_legal_refs: tuple[str, ...],
    difficult_justification_source_refs: tuple[str, ...],
    dana_reduction: M303DANA2024ReductionResult | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    reduction_legal_refs = dana_reduction.legal_refs if dana_reduction is not None else ()
    reduction_source_refs = dana_reduction.source_refs if dana_reduction is not None else ()
    legal_refs = _ordered_unique(
        (
            annual.legal_refs,
            *(item.legal_refs for item in modules),
            difficult_justification_legal_refs,
            reduction_legal_refs,
        ),
    )
    source_refs = _ordered_unique(
        (
            annual.source_refs,
            *(item.source_refs for item in modules),
            difficult_justification_source_refs,
            reduction_source_refs,
        ),
    )
    return legal_refs, source_refs


class _DANA2024Authority:
    """Resolved DANA parameter with all legal/source provenance retained."""

    def __init__(self, *, rate: Decimal, legal_refs: tuple[str, ...], source_refs: tuple[str, ...]) -> None:
        self.rate = rate
        self.legal_refs = legal_refs
        self.source_refs = source_refs


def _resolve_dana_2024_authority(*, authority: ValidatedRegistryAuthority, effective_date: date) -> _DANA2024Authority:
    try:
        resolved = authority.resolve_governed_fact(
            ScalarFactQuery(
                fact_id=_DANA_2024_REDUCTION_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        )
    except RegistryValidationError as exc:
        raise M303RegimenSimplificadoCalculationError(
            "DANA IVA simplified-regime authority is unavailable",
        ) from exc
    scalar = cast("ResolvedScalarFact", resolved)
    if scalar.payload.unit != "fraction" or not isinstance(scalar.payload.value, Decimal):
        raise M303RegimenSimplificadoCalculationError(
            "DANA IVA simplified-regime authority is not the exact fraction",
        )
    rate = scalar.payload.value
    if not Decimal("0") < rate < Decimal("1"):
        raise M303RegimenSimplificadoCalculationError(
            "DANA reduction rate must be a fraction between zero and one",
        )
    return _DANA2024Authority(
        rate=rate,
        legal_refs=tuple(scalar.legal_refs),
        source_refs=tuple(scalar.source_refs),
    )


def _calculate_dana_2024_reduction(
    *,
    cuota_devengada: Decimal,
    eligibility: M303DANA2024EligibilityEvidence | None,
    authority: _DANA2024Authority | None,
) -> M303DANA2024ReductionResult | None:
    if eligibility is None:
        return None
    if authority is None:
        raise M303RegimenSimplificadoCalculationError(
            "DANA eligibility cannot be evaluated without its legal authority",
        )
    return M303DANA2024ReductionResult(
        eligible=eligibility.eligible,
        rate=authority.rate,
        amount=round_to_cents(cuota_devengada * authority.rate) if eligibility.eligible else Decimal("0"),
        evidence_reference=eligibility.evidence_reference,
        legal_refs=authority.legal_refs,
        source_refs=authority.source_refs,
    )


def _ordered_unique(groups: Iterable[Iterable[str]]) -> tuple[str, ...]:
    seen: set[str] = set()
    values: list[str] = []
    for group in groups:
        for item in group:
            if item not in seen:
                seen.add(item)
                values.append(item)
    return tuple(values)


__all__ = ["M303RegimenSimplificadoCalculationError", "calculate_m303_regimen_simplificado_result"]
