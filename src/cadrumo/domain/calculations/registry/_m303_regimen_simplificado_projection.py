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
    applicable: bool,
    censo_iae_epigraphs: frozenset[str],
) -> tuple[M303RegimenSimplificadoRecordProjection, ...]:
    """Project canonical rows through exact authored references without source-text inference."""
    validate_regimen_simplificado_rows(
        rows,
        orden=orden,
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
    identities = tuple(ref.model_dump_json() for ref in refs)
    if len(set(identities)) != len(identities):
        raise RegistryValidationError("DP30302 contains duplicate regimen-simplificado projection references")


def _project_ref(
    ref: _RegimenSimplificadoProjectionRef,
    *,
    agricultural: tuple[ActividadAgricolaSimplificado, ...],
    non_agricultural: tuple[ActividadNoAgricolaSimplificado, ...],
    by_annual_id: dict[str, ActividadOrdenAnual],
) -> str | Decimal | None:
    candidates: tuple[RegimenSimplificadoActivity, ...] = (
        agricultural if ref.cohort is M303RegimenSimplificadoCohort.AGRICOLA else non_agricultural
    )
    row = candidates[ref.slot - 1] if ref.slot <= len(candidates) else None
    if row is None:
        return None
    if isinstance(ref, M303RegimenSimplificadoActivityProjectionRef):
        if ref.field is M303RegimenSimplificadoActivityField.ACTIVITY_CODE:
            if not isinstance(row, ActividadAgricolaSimplificado):
                raise RegistryValidationError("agricultural activity-code reference resolved a non-agricultural row")
            return row.activity_code
        if not isinstance(row, ActividadNoAgricolaSimplificado):
            raise RegistryValidationError("IAE-epigraph reference resolved an agricultural row")
        return row.iae_epigrafe
    annual = by_annual_id[row.orden_id]
    if isinstance(ref, M303RegimenSimplificadoFactProjectionRef):
        if ref.fact_identity not in annual.applicable_fact_identities:
            return None
        facts = {fact.identity: fact.value for fact in row.facts}
        try:
            return facts[ref.fact_identity]
        except KeyError as exc:
            raise RegistryValidationError(
                f"activity {row.activity_id!r} is missing applicable DP30302 fact {ref.fact_identity!r}",
            ) from exc
    if not isinstance(row, ActividadNoAgricolaSimplificado):
        raise RegistryValidationError("annual-Orden module reference resolved an agricultural row")
    if ref.module_order > len(row.modulos):
        return None
    entry = row.modulos[ref.module_order - 1]
    return (
        entry.declared_quantity
        if ref.value is M303RegimenSimplificadoModuleValue.DECLARED_QUANTITY
        else entry.off_form_result
    )


__all__ = [
    "M303RegimenSimplificadoFieldProjection",
    "M303RegimenSimplificadoRecordProjection",
    "project_m303_regimen_simplificado_rows",
]
