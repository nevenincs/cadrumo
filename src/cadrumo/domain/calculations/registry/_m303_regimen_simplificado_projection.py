"""Typed DP30302 projection from canonical regimen-simplificado rows."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ....core import (
    STRICT_FROZEN_CONFIG,
    FilingProjectionRef,
    M303RegimenSimplificadoActivityField,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoCohort,
    M303RegimenSimplificadoFactProjectionRef,
    M303RegimenSimplificadoModuleProjectionRef,
    M303RegimenSimplificadoModuleValue,
)
from ...iva import (
    ActividadAgricolaSimplificado,
    ActividadNoAgricolaSimplificado,
    ActividadOrdenAnual,
    AutoridadAgricolaOrdenAnualNoResuelta,
    RegimenSimplificadoActivity,
    RegimenSimplificadoFilingRows,
    validate_regimen_simplificado_rows,
)
from ._errors import RegistryValidationError

if TYPE_CHECKING:
    from ...modelos import M303RegimenSimplificadoCalculationResult

type _RegimenSimplificadoProjectionRef = (
    M303RegimenSimplificadoActivityProjectionRef
    | M303RegimenSimplificadoFactProjectionRef
    | M303RegimenSimplificadoModuleProjectionRef
)


class M303RegimenSimplificadoFieldProjection(BaseModel):
    """One exact typed projection reference and its canonical value."""

    model_config = STRICT_FROZEN_CONFIG

    projection_ref: FilingProjectionRef
    value: str | Decimal | None


class M303RegimenSimplificadoRecordProjection(BaseModel):
    """All typed simplified-regime fields for one DP30302 occurrence."""

    model_config = STRICT_FROZEN_CONFIG

    record: int = Field(ge=1, le=3)
    fields: tuple[M303RegimenSimplificadoFieldProjection, ...] = Field(min_length=1)


def project_m303_regimen_simplificado_rows(
    *,
    projection_refs: tuple[_RegimenSimplificadoProjectionRef, ...],
    rows: RegimenSimplificadoFilingRows,
    orden: tuple[ActividadOrdenAnual, ...],
    agricultural_authority: AutoridadAgricolaOrdenAnualNoResuelta,
    applicable: bool,
    calculation_result: M303RegimenSimplificadoCalculationResult | None,
    censo_iae_epigraphs: frozenset[str],
) -> tuple[M303RegimenSimplificadoRecordProjection, ...]:
    """Select exact authored fields from immutable evidence and calculated results."""
    validate_regimen_simplificado_rows(
        rows,
        orden=orden,
        agricultural_authority=agricultural_authority,
        applicable=applicable,
        censo_iae_epigraphs=censo_iae_epigraphs,
    )
    _validate_refs(projection_refs)
    if not applicable:
        return ()
    agricultural = tuple(activity for activity in rows.activities if activity.kind == "agricola")
    non_agricultural = tuple(activity for activity in rows.activities if activity.kind == "no_agricola")
    record_count = max((len(agricultural) + 1) // 2, (len(non_agricultural) + 1) // 2)
    by_annual_id = {item.orden_id: item for item in orden}
    return tuple(
        M303RegimenSimplificadoRecordProjection(
            record=record_index + 1,
            fields=tuple(
                M303RegimenSimplificadoFieldProjection(
                    projection_ref=ref,
                    value=_project_ref(
                        ref,
                        agricultural=agricultural[record_index * 2 : record_index * 2 + 2],
                        non_agricultural=non_agricultural[record_index * 2 : record_index * 2 + 2],
                        by_annual_id=by_annual_id,
                        calculation_result=calculation_result,
                    ),
                )
                for ref in projection_refs
            ),
        )
        for record_index in range(record_count)
    )


def _validate_refs(refs: tuple[_RegimenSimplificadoProjectionRef, ...]) -> None:
    if not refs:
        raise RegistryValidationError("DP30302 requires typed regimen-simplificado projection references")
    if len(set(refs)) != len(refs):
        raise RegistryValidationError("DP30302 contains duplicate regimen-simplificado projection references")


def _project_ref(
    ref: _RegimenSimplificadoProjectionRef,
    *,
    agricultural: tuple[ActividadAgricolaSimplificado, ...],
    non_agricultural: tuple[ActividadNoAgricolaSimplificado, ...],
    by_annual_id: dict[str, ActividadOrdenAnual],
    calculation_result: M303RegimenSimplificadoCalculationResult | None,
) -> str | Decimal | None:
    row = _select_row(ref, agricultural=agricultural, non_agricultural=non_agricultural)
    if row is None:
        return None
    if isinstance(ref, M303RegimenSimplificadoActivityProjectionRef):
        return _project_activity_ref(ref, row)
    annual = by_annual_id[row.orden_id]
    if isinstance(ref, M303RegimenSimplificadoFactProjectionRef):
        return _project_fact_ref(ref, row, annual)
    return _project_module_ref(ref, row, calculation_result)


def _select_row(
    ref: _RegimenSimplificadoProjectionRef,
    *,
    agricultural: tuple[ActividadAgricolaSimplificado, ...],
    non_agricultural: tuple[ActividadNoAgricolaSimplificado, ...],
) -> RegimenSimplificadoActivity | None:
    candidates = agricultural if ref.cohort is M303RegimenSimplificadoCohort.AGRICOLA else non_agricultural
    return candidates[ref.slot - 1] if ref.slot <= len(candidates) else None


def _project_activity_ref(
    ref: M303RegimenSimplificadoActivityProjectionRef,
    row: RegimenSimplificadoActivity,
) -> str | None:
    if ref.field is M303RegimenSimplificadoActivityField.ACTIVITY_CODE:
        if not isinstance(row, ActividadAgricolaSimplificado):
            raise RegistryValidationError("agricultural activity-code reference resolved a non-agricultural row")
        return row.activity_code
    if ref.field is M303RegimenSimplificadoActivityField.IAE_EPIGRAFE:
        if not isinstance(row, ActividadNoAgricolaSimplificado):
            raise RegistryValidationError("IAE-epigraph reference resolved an agricultural row")
        return row.iae_epigrafe
    if ref.field is M303RegimenSimplificadoActivityField.AUXILIARY_ACTIVITY_INDICATOR:
        if not isinstance(row, ActividadNoAgricolaSimplificado):
            raise RegistryValidationError("auxiliary activity indicator reference resolved an agricultural row")
        return row.auxiliary_activity_indicator
    raise RegistryValidationError(f"unsupported regimen-simplificado activity field {ref.field!r}")


def _project_fact_ref(
    ref: M303RegimenSimplificadoFactProjectionRef,
    row: RegimenSimplificadoActivity,
    annual: ActividadOrdenAnual,
) -> str | Decimal | None:
    if ref.fact_identity not in annual.applicable_fact_identities:
        return None
    facts = {fact.identity: fact.value for fact in row.facts}
    try:
        return facts[ref.fact_identity]
    except KeyError as exc:
        raise RegistryValidationError(
            f"activity {row.activity_id!r} is missing applicable DP30302 fact {ref.fact_identity!r}",
        ) from exc


def _project_module_ref(
    ref: M303RegimenSimplificadoModuleProjectionRef,
    row: RegimenSimplificadoActivity,
    calculation_result: M303RegimenSimplificadoCalculationResult | None,
) -> Decimal | None:
    if not isinstance(row, ActividadNoAgricolaSimplificado):
        raise RegistryValidationError("annual-Orden module reference resolved an agricultural row")
    if ref.module_order > len(row.modulos):
        return None
    entry = row.modulos[ref.module_order - 1]
    if ref.value is M303RegimenSimplificadoModuleValue.DECLARED_QUANTITY:
        return entry.declared_quantity
    if ref.value is M303RegimenSimplificadoModuleValue.CUOTA_DEVENGADA:
        if calculation_result is None:
            raise RegistryValidationError(
                "calculated module cuota projection requires the immutable calculation result"
            )
        return _select_calculated_module_cuota(
            row=row,
            module_order=ref.module_order,
            calculation_result=calculation_result,
        )
    raise RegistryValidationError(f"unsupported regimen-simplificado module value {ref.value!r}")


def _select_calculated_module_cuota(
    *,
    row: ActividadNoAgricolaSimplificado,
    module_order: int,
    calculation_result: M303RegimenSimplificadoCalculationResult,
) -> Decimal:
    """Select one matching computed module cuota with no alternate result source."""
    matching_activities = tuple(item for item in calculation_result.activities if item.activity_id == row.activity_id)
    if len(matching_activities) != 1:
        raise RegistryValidationError(
            f"activity {row.activity_id!r} must have exactly one simplified-regime calculation result",
        )
    activity_result = matching_activities[0]
    if activity_result.orden_id != row.orden_id:
        raise RegistryValidationError(
            f"activity {row.activity_id!r} calculated result disagrees with its annual Orden identity",
        )
    if module_order > len(activity_result.module_results):
        raise RegistryValidationError(
            f"activity {row.activity_id!r} calculated result is missing module ordinal {module_order}",
        )
    module_result = activity_result.module_results[module_order - 1]
    expected_module = row.modulos[module_order - 1]
    if module_result.module_identity != expected_module.module_identity:
        raise RegistryValidationError(
            f"activity {row.activity_id!r} calculated module identity disagrees at ordinal {module_order}",
        )
    if module_result.declared_quantity != expected_module.declared_quantity:
        raise RegistryValidationError(
            f"activity {row.activity_id!r} calculated module quantity disagrees at ordinal {module_order}",
        )
    return module_result.cuota_devengada


__all__ = [
    "M303RegimenSimplificadoFieldProjection",
    "M303RegimenSimplificadoRecordProjection",
    "project_m303_regimen_simplificado_rows",
]
