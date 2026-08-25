"""Canonical annual-Orden calculation for Modelo 303 simplified-regime rows."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

from ...core import Period
from ...core.errors import CoreValidationError
from ...core.money import round_to_cents
from ...domain.calculations.registry.schema import (
    LegalParameter,
    RegistryCatalogues,
)
from ...domain.calculations.registry.m303_orden_projection_models import M303RegimenSimplificadoSnapshot
from ...domain.iva import (
    ActividadNoAgricolaSimplificado,
    ActividadOrdenAnual,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
    is_last_filing_period_of_year,
    validate_regimen_simplificado_rows,
)
from ...domain.modelos import (
    M303DANA2024EligibilityEvidence,
    M303DANA2024ReductionResult,
    M303RegimenSimplificadoActivityCalculationResult,
    M303RegimenSimplificadoCalculationResult,
    M303RegimenSimplificadoModuleCalculationResult,
)

_DANA_2024_PARAMETER_ID = "rdl-7-2024-art-11-2:iva-simplificado-reduccion-cuota-devengada-2024"
_DANA_2024_PARAMETER_LEGAL_REFS = (
    "real-decreto-ley-7-2024:art-11.2",
    "real-decreto-ley-7-2024:df-14",
    "real-decreto-ley-6-2024:anexo",
)
_DANA_2024_LEGAL_REFS = (
    *_DANA_2024_PARAMETER_LEGAL_REFS,
    "real-decreto-ley-6-2024:art-1",
    "correccion-errores-rdl-6-2024",
)
_DANA_2024_SOURCE_REFS = (
    "boe-rdl-7-2024-dana-authority",
    "boe-rdl-6-2024-dana-authority",
    "boe-correccion-errores-rdl-6-2024",
)
_HUNDRED = Decimal("100")


class M303RegimenSimplificadoCalculationError(CoreValidationError):
    """Raised when exact annual-Orden inputs cannot form a calculation result.

    Roots at :class:`~core.errors.CoreValidationError` like every other refusal
    in this package, so the class binds to the error registry and its refusal
    carries a code, a category and locale-resolved text. That base already
    carries :exc:`ValueError`, which the row validation below relies on to
    convert the domain refusal into this one.
    """


def calculate_m303_regimen_simplificado_result(
    *,
    period: Period,
    scope_decision: M303RegimenSimplificadoScopeDecision,
    rows: RegimenSimplificadoFilingRows,
    regimen_snapshot: M303RegimenSimplificadoSnapshot,
    dana_2024_eligibility: M303DANA2024EligibilityEvidence | None,
    catalogues: RegistryCatalogues,
) -> M303RegimenSimplificadoCalculationResult:
    """Calculate one immutable, source-pinned annual result from filing rows.

    The annual Orden defines every module coefficient and annual reduction.  The
    DANA relief is admitted solely by an evidenced eligibility decision and is
    applied to each eligible activity's 2024 annual cuota devengada once.
    """
    _validate_coordinate(
        period=period,
        scope_decision=scope_decision,
        rows=rows,
        regimen_snapshot=regimen_snapshot,
        dana_2024_eligibility=dana_2024_eligibility,
    )
    _validate_rows_against_annual_orden(rows=rows, regimen_snapshot=regimen_snapshot, scope_decision=scope_decision)
    dana_authority = _resolve_dana_2024_authority(catalogues) if dana_2024_eligibility is not None else None
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
) -> None:
    if rows.ejercicio != period.filing_year or regimen_snapshot.orden.ejercicio != period.filing_year:
        raise M303RegimenSimplificadoCalculationError("M303 simplified rows and annual Orden must use the filing year")
    if regimen_snapshot.scope_decision != scope_decision:
        raise M303RegimenSimplificadoCalculationError("M303 simplified scope must match the annual Orden snapshot")
    requires_dana_eligibility = (
        period.filing_year == 2024 and is_last_filing_period_of_year(period) and not scope_decision.is_not_claimed
    )
    if requires_dana_eligibility != (dana_2024_eligibility is not None):
        raise M303RegimenSimplificadoCalculationError(
            "M303 DANA eligibility evidence is required only for the 2024 annual simplified result",
        )


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
    difficult = round_to_cents(cuota_tras_dana * difficult_justification_pct / _HUNDRED)
    minimum = round_to_cents(cuota_tras_dana * minimum_pct / _HUNDRED)
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

    def __init__(self, *, rate: Decimal) -> None:
        self.rate = rate


def _resolve_dana_2024_authority(catalogues: RegistryCatalogues) -> _DANA2024Authority:
    parameter = catalogues.parameters.get(_DANA_2024_PARAMETER_ID)
    if parameter is None:
        raise M303RegimenSimplificadoCalculationError("DANA 2024 IVA simplified-regime authority is unavailable")
    _validate_dana_parameter_shape(parameter)
    _validate_dana_provenance(catalogues)
    return _DANA2024Authority(rate=_dana_rate(parameter.value))


def _validate_dana_parameter_shape(parameter: LegalParameter) -> None:
    if (
        parameter.unit != "fraction"
        or parameter.applies_to != "iva-regimen-simplificado"
        or tuple(parameter.legal_refs) != _DANA_2024_PARAMETER_LEGAL_REFS
    ):
        raise M303RegimenSimplificadoCalculationError(
            "DANA 2024 IVA simplified-regime authority is not the exact legal parameter",
        )


def _validate_dana_provenance(catalogues: RegistryCatalogues) -> None:
    if any(reference not in catalogues.legal for reference in _DANA_2024_LEGAL_REFS):
        raise M303RegimenSimplificadoCalculationError("DANA 2024 legal provenance is incomplete")
    if any(reference not in catalogues.sources for reference in _DANA_2024_SOURCE_REFS):
        raise M303RegimenSimplificadoCalculationError("DANA 2024 source provenance is incomplete")


def _dana_rate(value: str) -> Decimal:
    try:
        rate = Decimal(value)
    except InvalidOperation as exc:
        raise M303RegimenSimplificadoCalculationError("DANA 2024 reduction rate is not a decimal") from exc
    if not Decimal("0") < rate < Decimal("1"):
        raise M303RegimenSimplificadoCalculationError(
            "DANA 2024 reduction rate must be a fraction between zero and one",
        )
    return rate


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
            "DANA 2024 eligibility cannot be evaluated without its legal authority",
        )
    return M303DANA2024ReductionResult(
        eligible=eligibility.eligible,
        rate=authority.rate,
        amount=round_to_cents(cuota_devengada * authority.rate) if eligibility.eligible else Decimal("0"),
        evidence_reference=eligibility.evidence_reference,
        legal_refs=_DANA_2024_LEGAL_REFS,
        source_refs=_DANA_2024_SOURCE_REFS,
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
