"""Typed DP30302 projection from canonical regimen-simplificado rows."""

from __future__ import annotations

from decimal import Decimal

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
    censo_iae_epigraphs: frozenset[str],
) -> tuple[M303RegimenSimplificadoRecordProjection, ...]:
    """Project canonical rows through exact authored references without source-text inference."""
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
) -> str | Decimal | None:
    row = _select_row(ref, agricultural=agricultural, non_agricultural=non_agricultural)
    if row is None:
        return None
    if isinstance(ref, M303RegimenSimplificadoActivityProjectionRef):
        return _project_activity_ref(ref, row)
    annual = by_annual_id[row.orden_id]
    if isinstance(ref, M303RegimenSimplificadoFactProjectionRef):
        return _project_fact_ref(ref, row, annual)
    return _project_module_ref(ref, row)


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
) -> str:
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
) -> Decimal | None:
    if not isinstance(row, ActividadNoAgricolaSimplificado):
        raise RegistryValidationError("annual-Orden module reference resolved an agricultural row")
    if ref.module_order > len(row.modulos):
        return None
    entry = row.modulos[ref.module_order - 1]
    if ref.value is M303RegimenSimplificadoModuleValue.DECLARED_QUANTITY:
        return entry.declared_quantity
    if ref.value is M303RegimenSimplificadoModuleValue.OFF_FORM_RESULT:
        return entry.off_form_result
    raise RegistryValidationError(f"unsupported regimen-simplificado module value {ref.value!r}")


__all__ = [
    "M303RegimenSimplificadoFieldProjection",
    "M303RegimenSimplificadoRecordProjection",
    "project_m303_regimen_simplificado_rows",
]
