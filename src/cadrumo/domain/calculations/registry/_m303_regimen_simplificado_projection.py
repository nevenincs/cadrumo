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
    M303RegimenSimplificadoFact,
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
from .errors import RegistryValidationError

if TYPE_CHECKING:
    from ...modelos import M303RegimenSimplificadoCalculationResult

type _RegimenSimplificadoProjectionRef = (
    M303RegimenSimplificadoActivityProjectionRef
    | M303RegimenSimplificadoFactProjectionRef
    | M303RegimenSimplificadoModuleProjectionRef
)

_CALCULATED_FACTS = frozenset(
    {
        M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
        M303RegimenSimplificadoFact.CUOTA_MINIMA,
        M303RegimenSimplificadoFact.REDUCCION_DANA,
        M303RegimenSimplificadoFact.REDUCCIONES,
        M303RegimenSimplificadoFact.RESULTADO_CUARTO_TRIMESTRE,
    },
)

_MESA_FACTS = frozenset(
    {
        M303RegimenSimplificadoFact.MESAS_CAPACIDAD,
        M303RegimenSimplificadoFact.MESAS_DIAS_CUARTO_TRIMESTRE,
        M303RegimenSimplificadoFact.MESAS_NUMERO,
    },
)
_MESA_SUB_INDICES = frozenset({1, 2, 3, 4})
_REPEATING_FACT_SUB_INDICES = frozenset({1, 2, 3, 4})
_EARLY_DP30302_EPOCHS = frozenset({"2023", "2024-hasta-08-y-2t", "2024-desde-09-y-3t"})
_LATE_DP30302_EPOCHS = frozenset({"2025", "2026-y-siguientes"})
_HORNO_DIAS = M303RegimenSimplificadoFact.SUPERFICIE_HORNO_DIAS_CUARTO_TRIMESTRE
_HORNO_SUPERFICIE = M303RegimenSimplificadoFact.SUPERFICIE_HORNO_CUARTO_TRIMESTRE


def _validate_m303_regimen_simplificado_revision_epoch(revision_id: str) -> bool:
    if revision_id not in _EARLY_DP30302_EPOCHS | _LATE_DP30302_EPOCHS:
        raise RegistryValidationError(f"unknown DP30302 simplified-regime revision {revision_id!r}")
    return revision_id in _EARLY_DP30302_EPOCHS


def _validate_mesa_fact_epoch(ref: M303RegimenSimplificadoFactProjectionRef) -> None:
    if ref.fact in _MESA_FACTS and ref.sub_index not in _MESA_SUB_INDICES:
        raise RegistryValidationError("Mesa DP30302 facts require sub_index 1..4")


def _validate_horno_days_fact_epoch(
    ref: M303RegimenSimplificadoFactProjectionRef,
    *,
    revision_id: str,
    early_epoch: bool,
) -> None:
    if ref.fact is not _HORNO_DIAS:
        return
    expected = {None} if early_epoch else _REPEATING_FACT_SUB_INDICES
    if ref.sub_index not in expected:
        raise RegistryValidationError(f"horno-days fact is not admitted by revision {revision_id!r}")


def _validate_horno_surface_fact_epoch(
    ref: M303RegimenSimplificadoFactProjectionRef,
    *,
    revision_id: str,
    early_epoch: bool,
) -> None:
    if ref.fact is _HORNO_SUPERFICIE and (early_epoch or ref.sub_index not in _REPEATING_FACT_SUB_INDICES):
        raise RegistryValidationError(f"horno-surface fact is not admitted by revision {revision_id!r}")


def validate_m303_regimen_simplificado_endpoint_epoch(
    refs: tuple[_RegimenSimplificadoProjectionRef, ...], *, revision_id: str
) -> None:
    """Refuse simplified fact multiplicity that the selected record-design epoch never admits."""
    early_epoch = _validate_m303_regimen_simplificado_revision_epoch(revision_id)
    for ref in refs:
        if not isinstance(ref, M303RegimenSimplificadoFactProjectionRef):
            continue
        _validate_mesa_fact_epoch(ref)
        _validate_horno_days_fact_epoch(ref, revision_id=revision_id, early_epoch=early_epoch)
        _validate_horno_surface_fact_epoch(ref, revision_id=revision_id, early_epoch=early_epoch)


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
    if calculation_result is None:
        raise RegistryValidationError(
            "applicable simplified-regime projection requires the immutable calculation result",
        )
    agricultural = tuple(activity for activity in rows.activities if activity.kind == "agricola")
    non_agricultural = tuple(activity for activity in rows.activities if activity.kind == "no_agricola")
    record_count = max((len(agricultural) + 1) // 2, (len(non_agricultural) + 1) // 2)
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
    calculation_result: M303RegimenSimplificadoCalculationResult | None,
) -> str | Decimal | None:
    row = _select_row(ref, agricultural=agricultural, non_agricultural=non_agricultural)
    if row is None:
        return None
    if isinstance(ref, M303RegimenSimplificadoActivityProjectionRef):
        return _project_activity_ref(ref, row)
    if isinstance(ref, M303RegimenSimplificadoFactProjectionRef):
        return _project_fact_ref(ref, row, calculation_result)
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
    calculation_result: M303RegimenSimplificadoCalculationResult | None,
) -> str | Decimal | None:
    """Select one declared fact; source order and occurrence never participate."""
    if ref.fact in _CALCULATED_FACTS:
        return _project_calculated_fact_ref(ref, row, calculation_result)
    matches = tuple(fact for fact in row.facts if fact.fact is ref.fact and fact.sub_index == ref.sub_index)
    if len(matches) > 1:
        raise RegistryValidationError(
            f"activity {row.activity_id!r} contains duplicate DP30302 fact {ref.fact.value!r}",
        )
    return matches[0].value if matches else None


def _project_calculated_fact_ref(
    ref: M303RegimenSimplificadoFactProjectionRef,
    row: RegimenSimplificadoActivity,
    calculation_result: M303RegimenSimplificadoCalculationResult | None,
) -> str | Decimal | None:
    """Select a calculated value only from the exact immutable activity result."""
    if not isinstance(row, ActividadNoAgricolaSimplificado):
        raise RegistryValidationError("calculated simplified-regime fact resolved an agricultural row")
    if calculation_result is None:
        raise RegistryValidationError("calculated simplified-regime fact requires the immutable calculation result")
    matching = tuple(item for item in calculation_result.activities if item.activity_id == row.activity_id)
    if len(matching) != 1:
        raise RegistryValidationError(
            f"activity {row.activity_id!r} must have exactly one simplified-regime calculation result",
        )
    result = matching[0]
    if result.orden_id != row.orden_id:
        raise RegistryValidationError(
            f"activity {row.activity_id!r} calculated result disagrees with its annual Orden identity",
        )
    values: dict[M303RegimenSimplificadoFact, str | Decimal | None] = {
        M303RegimenSimplificadoFact.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES: (
            result.cuota_devengada_operaciones_corrientes
        ),
        M303RegimenSimplificadoFact.CUOTA_MINIMA: result.cuota_minima,
        M303RegimenSimplificadoFact.REDUCCION_DANA: (
            result.dana_2024_reduction.amount if result.dana_2024_reduction is not None else None
        ),
        M303RegimenSimplificadoFact.REDUCCIONES: result.deduccion_dificil_justificacion,
        M303RegimenSimplificadoFact.RESULTADO_CUARTO_TRIMESTRE: result.cuota_resultante,
    }
    return values[ref.fact]


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
    "validate_m303_regimen_simplificado_endpoint_epoch",
]
