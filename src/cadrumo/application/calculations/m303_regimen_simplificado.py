"""Canonical annual-Orden calculation for Modelo 303 simplified-regime rows."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from ...core.decimal.constants import HUNDRED
from ...core.errors.hierarchy import CoreValidationError
from ...core.money.rounding import round_to_cents
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
from ...domain.calculations.registry.m303_orden_projection_models import M303RegimenSimplificadoSnapshot
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.calculations.registry.schema_references import TemporalProjectionDirection
from ...domain.iva.errors import IvaValidationError
from ...domain.iva.refund_eligibility import is_last_filing_period_of_year
from ...domain.iva.regimen_simplificado_rows import (
    ActividadNoAgricolaSimplificado,
    ActividadOrdenAnual,
    M303RegimenSimplificadoScopeDecision,
    ReduccionLorcaOrdenAnual,
    RegimenSimplificadoFilingRows,
    validate_regimen_simplificado_rows,
)
from ...domain.modelos.calculation_revision_m303_evidence import (
    M303DANAEligibilityEvidence,
    M303DANAReductionResult,
    M303RegimenSimplificadoActivityCalculationResult,
    M303RegimenSimplificadoCalculationResult,
    M303RegimenSimplificadoModuleCalculationResult,
)

_DANA_REDUCTION_FACT_ID = "rdl-7-2024-art-11-2:iva-simplificado-reduccion-cuota-devengada"


class M303RegimenSimplificadoCalculationError(CoreValidationError):
    """Raised when exact annual-Orden inputs cannot form a calculation result."""


def calculate_m303_regimen_simplificado_result(
    *,
    period: Period,
    scope_decision: M303RegimenSimplificadoScopeDecision,
    rows: RegimenSimplificadoFilingRows,
    regimen_snapshot: M303RegimenSimplificadoSnapshot,
    dana_eligibility: M303DANAEligibilityEvidence | None,
    operation: PinnedAuthorityOperation,
) -> M303RegimenSimplificadoCalculationResult:
    """Calculate one immutable, source-pinned annual result from filing rows."""
    _validate_coordinate(
        period=period,
        scope_decision=scope_decision,
        rows=rows,
        regimen_snapshot=regimen_snapshot,
        dana_eligibility=dana_eligibility,
        operation=operation,
    )
    _validate_rows_against_annual_orden(rows=rows, regimen_snapshot=regimen_snapshot, scope_decision=scope_decision)
    dana_authority = None
    if dana_eligibility is not None:
        dana_authority = _resolve_dana_authority(
            operation=operation,
            effective_date=period.end_date,
        )
    annual_by_id = {activity.orden_id: activity for activity in regimen_snapshot.orden.activities}
    activities = tuple(
        _calculate_no_agricultural_activity(
            row=row,
            annual=annual_by_id[row.orden_id],
            difficult_justification_pct=regimen_snapshot.orden.difficult_justification.percentage,
            difficult_justification_legal_refs=regimen_snapshot.orden.difficult_justification.legal_refs,
            difficult_justification_source_refs=regimen_snapshot.orden.difficult_justification.source_refs,
            dana_eligibility=dana_eligibility,
            dana_authority=dana_authority,
            lorca_authority=regimen_snapshot.orden.lorca_reduction,
        )
        for row in rows.activities
        if isinstance(row, ActividadNoAgricolaSimplificado)
    )
    orden = regimen_snapshot.orden
    record_design = regimen_snapshot.record_design
    if record_design.record_design_epoch is None:
        raise M303RegimenSimplificadoCalculationError("M303 simplified record design must retain its epoch")
    return M303RegimenSimplificadoCalculationResult.calculated(
        ejercicio=period.filing_year,
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
    dana_eligibility: M303DANAEligibilityEvidence | None,
    operation: PinnedAuthorityOperation,
) -> None:
    if rows.ejercicio != period.filing_year or regimen_snapshot.filing_year != period.filing_year:
        raise M303RegimenSimplificadoCalculationError("M303 simplified rows and annual Orden must use the filing year")
    if regimen_snapshot.scope_decision != scope_decision:
        raise M303RegimenSimplificadoCalculationError("M303 simplified scope must match the annual Orden snapshot")
    requires_dana_eligibility = (
        _dana_reduction_is_available(operation=operation, effective_date=period.end_date)
        and is_last_filing_period_of_year(period)
        and not scope_decision.is_not_claimed
    )
    if requires_dana_eligibility != (dana_eligibility is not None):
        raise M303RegimenSimplificadoCalculationError(
            "M303 DANA eligibility evidence is required only when the selected "
            "registry reduction applies to the annual simplified result",
        )


def _dana_reduction_is_available(
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date,
) -> bool:
    """Return whether the selected authority publishes the DANA reduction now.

    The applicability window belongs to the governed scalar fact.  This
    coordinate check therefore asks the same authority used to resolve the
    reduction instead of encoding a filing year in the calculation module.
    RDL 7/2024 art. 11.2 grants the reduction only for the year 2024, so a
    value carried past the authored window by temporal projection is not
    availability of the reduction.
    """
    try:
        resolved = operation.resolve_governed_fact(
            ScalarFactQuery(
                fact_id=_DANA_REDUCTION_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        )
    except RegistryValidationError:
        return False
    return resolved.projection_direction is TemporalProjectionDirection.AUTHORED


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
            orden_ejercicio=regimen_snapshot.orden.ejercicio,
            applicable=not scope_decision.is_not_claimed,
            censo_iae_epigraphs=frozenset(
                row.iae_epigrafe for row in rows.activities if isinstance(row, ActividadNoAgricolaSimplificado)
            ),
        )
    except (ValueError, IvaValidationError) as exc:
        raise M303RegimenSimplificadoCalculationError(str(exc)) from exc


def _calculate_no_agricultural_activity(
    *,
    row: ActividadNoAgricolaSimplificado,
    annual: ActividadOrdenAnual,
    difficult_justification_pct: Decimal,
    difficult_justification_legal_refs: tuple[str, ...],
    difficult_justification_source_refs: tuple[str, ...],
    dana_eligibility: M303DANAEligibilityEvidence | None,
    dana_authority: _DANAAuthority | None,
    lorca_authority: ReduccionLorcaOrdenAnual | None,
) -> M303RegimenSimplificadoActivityCalculationResult:
    if annual.kind != "no_agricola":
        raise M303RegimenSimplificadoCalculationError(
            "M303 simplified calculation requires a non-agricultural annual Orden row",
        )
    modules = _calculate_activity_modules(row=row, annual=annual)
    cuota_devengada = _sum_module_cuotas(modules)
    dana_reduction = _calculate_dana_reduction(
        cuota_devengada=cuota_devengada,
        eligibility=dana_eligibility,
        authority=dana_authority,
    )
    cuota_tras_dana = _cuota_after_dana(cuota_devengada, dana_reduction)
    lorca_amount = _calculate_lorca_reduction(
        row=row,
        authority=lorca_authority,
        cuota_devengada=cuota_devengada,
        dana_eligibility=dana_eligibility,
    )
    cuota_tras_reducciones = cuota_tras_dana - lorca_amount
    difficult, minimum = _calculate_activity_adjustments(
        cuota_tras_dana=cuota_tras_reducciones,
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
            *((row.lorca_eligibility.evidence_reference,) if row.lorca_eligibility is not None else ()),
        ),
        cuota_devengada_operaciones_corrientes=cuota_devengada,
        cuota_devengada_tras_dana=cuota_tras_dana,
        lorca_reduction_amount=lorca_amount,
        cuota_devengada_tras_reducciones=cuota_tras_reducciones,
        deduccion_dificil_justificacion=difficult,
        cuota_minima=minimum,
        dana_reduction=dana_reduction,
        cuota_resultante=max(cuota_tras_reducciones - difficult, minimum),
        legal_refs=tuple(
            dict.fromkeys((*activity_legal_refs, *(lorca_authority.legal_refs if lorca_authority is not None else ())))
        ),
        source_refs=tuple(
            dict.fromkeys(
                (*activity_source_refs, *(lorca_authority.source_refs if lorca_authority is not None else ()))
            )
        ),
    )


def _calculate_lorca_reduction(
    *,
    row: ActividadNoAgricolaSimplificado,
    authority: ReduccionLorcaOrdenAnual | None,
    cuota_devengada: Decimal,
    dana_eligibility: M303DANAEligibilityEvidence | None,
) -> Decimal:
    """Require evidenced activity eligibility before applying annual municipal relief."""
    eligibility = row.lorca_eligibility
    if authority is None:
        if eligibility is not None and eligibility.eligible:
            raise M303RegimenSimplificadoCalculationError("Lorca reduction is unavailable for this filing year")
        return Decimal("0")
    if eligibility is None:
        raise M303RegimenSimplificadoCalculationError(
            f"Activity {row.activity_id!r} requires Lorca eligibility evidence for {row.ejercicio}"
        )
    if not eligibility.eligible:
        return Decimal("0")
    if dana_eligibility is not None and dana_eligibility.eligible:
        raise M303RegimenSimplificadoCalculationError("Combined Lorca and DANA eligibility requires reviewed authority")
    if authority.ejercicio != row.ejercicio or authority.annex_scope != "ANEXO II":
        raise M303RegimenSimplificadoCalculationError("Lorca authority does not cover this activity year and annex")
    return round_to_cents(cuota_devengada * authority.percentage / HUNDRED)


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
    dana_reduction: M303DANAReductionResult | None,
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
    dana_reduction: M303DANAReductionResult | None,
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


class _DANAAuthority:
    """Resolved DANA parameter with all legal/source provenance retained."""

    def __init__(self, *, rate: Decimal, legal_refs: tuple[str, ...], source_refs: tuple[str, ...]) -> None:
        self.rate = rate
        self.legal_refs = legal_refs
        self.source_refs = source_refs


def _resolve_dana_authority(
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date,
) -> _DANAAuthority:
    try:
        resolved = operation.resolve_governed_fact(
            ScalarFactQuery(
                fact_id=_DANA_REDUCTION_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        )
    except RegistryValidationError as exc:
        raise M303RegimenSimplificadoCalculationError(
            "DANA IVA simplified-regime authority is unavailable",
        ) from exc
    if not isinstance(resolved, ResolvedScalarFact):
        raise M303RegimenSimplificadoCalculationError(
            "DANA IVA simplified-regime authority is not a scalar fact",
        )
    scalar = resolved
    if scalar.projection_direction is not TemporalProjectionDirection.AUTHORED:
        raise M303RegimenSimplificadoCalculationError(
            "DANA IVA simplified-regime reduction is not authored for the filing coordinate",
        )
    if scalar.payload.unit != "fraction" or not isinstance(scalar.payload.value, Decimal):
        raise M303RegimenSimplificadoCalculationError(
            "DANA IVA simplified-regime authority is not the exact fraction",
        )
    rate = scalar.payload.value
    if not Decimal("0") < rate < Decimal("1"):
        raise M303RegimenSimplificadoCalculationError(
            "DANA reduction rate must be a fraction between zero and one",
        )
    return _DANAAuthority(
        rate=rate,
        legal_refs=tuple(scalar.legal_refs),
        source_refs=tuple(scalar.source_refs),
    )


def _calculate_dana_reduction(
    *,
    cuota_devengada: Decimal,
    eligibility: M303DANAEligibilityEvidence | None,
    authority: _DANAAuthority | None,
) -> M303DANAReductionResult | None:
    if eligibility is None:
        return None
    if authority is None:
        raise M303RegimenSimplificadoCalculationError(
            "DANA eligibility cannot be evaluated without its legal authority",
        )
    return M303DANAReductionResult(
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
