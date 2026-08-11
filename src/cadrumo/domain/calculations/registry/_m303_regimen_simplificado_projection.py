"""Exact DP30302 projection from canonical regimen-simplificado activity rows."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG
from ...iva import (
    ActividadAgricolaSimplificado,
    ActividadNoAgricolaSimplificado,
    ActividadOrdenAnual,
    RegimenSimplificadoActivity,
    RegimenSimplificadoFilingRows,
    validate_regimen_simplificado_rows,
)
from ._errors import RegistryValidationError
from ._record_design_schema import RecordDesignField, RecordDesignSheet

_SUPPORTED_EPOCHS = frozenset({"2023", "2024-early", "2024-late", "2025", "2026"})
_NUMERIC_CASILLA = re.compile(r"\[\s*\d{1,3}\s*\]")
_ACTIVITY = re.compile(r" - Actividad ([12]) - ")
_MODULE = re.compile(r"^Módulo ([1-7]) - (Nº Unidades|Importe)$")


class M303RegimenSimplificadoFieldProjection(BaseModel):
    """One exact official source anchor and its canonical projected value."""

    model_config = STRICT_FROZEN_CONFIG

    ordinal: int = Field(gt=0)
    offset: int = Field(gt=0)
    length: int = Field(gt=0)
    type_code: str = Field(min_length=1)
    description: str = Field(min_length=1)
    value: str | Decimal | None


class M303RegimenSimplificadoRecordProjection(BaseModel):
    """All nonnumbered simplified-regime fields for one DP30302 record."""

    model_config = STRICT_FROZEN_CONFIG

    record: int = Field(ge=1, le=3)
    design_epoch: str
    fields: tuple[M303RegimenSimplificadoFieldProjection, ...] = Field(min_length=1)


def project_m303_regimen_simplificado_rows(
    sheet: RecordDesignSheet,
    *,
    design_epoch: str,
    expected_design_epoch: str,
    rows: RegimenSimplificadoFilingRows,
    orden: tuple[ActividadOrdenAnual, ...],
    applicable: bool,
    censo_iae_epigraphs: frozenset[str],
) -> tuple[M303RegimenSimplificadoRecordProjection, ...]:
    """Project canonical rows to every nonnumbered RS field in the exact source epoch."""
    if sheet.name != "DP30302":
        raise RegistryValidationError("regimen simplificado projection requires the DP30302 source sheet")
    if design_epoch != expected_design_epoch or design_epoch not in _SUPPORTED_EPOCHS:
        raise RegistryValidationError("regimen simplificado projection refuses a wrong or unknown design epoch")
    validate_regimen_simplificado_rows(
        rows,
        orden=orden,
        applicable=applicable,
        censo_iae_epigraphs=censo_iae_epigraphs,
    )
    source_fields = m303_regimen_simplificado_nonnumbered_fields(sheet)
    if not applicable:
        return ()
    by_annual_id = {item.orden_id: item for item in orden}
    agricultural = tuple(activity for activity in rows.activities if activity.kind == "agricola")
    non_agricultural = tuple(activity for activity in rows.activities if activity.kind == "no_agricola")
    record_count = max((len(agricultural) + 1) // 2, (len(non_agricultural) + 1) // 2)
    return tuple(
        M303RegimenSimplificadoRecordProjection(
            record=record_index + 1,
            design_epoch=design_epoch,
            fields=tuple(
                _project_field(
                    field,
                    agricultural=agricultural[record_index * 2 : record_index * 2 + 2],
                    non_agricultural=non_agricultural[record_index * 2 : record_index * 2 + 2],
                    by_annual_id=by_annual_id,
                )
                for field in source_fields
            ),
        )
        for record_index in range(record_count)
    )


def m303_regimen_simplificado_nonnumbered_fields(sheet: RecordDesignSheet) -> tuple[RecordDesignField, ...]:
    fields = tuple(
        field
        for field in sheet.fields
        if " - RS - " in field.description and _NUMERIC_CASILLA.search(field.description) is None
    )
    if not fields:
        raise RegistryValidationError("DP30302 contains no nonnumbered regimen-simplificado fields")
    if any(_ACTIVITY.search(field.description) is None for field in fields):
        raise RegistryValidationError("a nonnumbered DP30302 RS field lacks an explicit activity anchor")
    return fields


def _project_field(
    field: RecordDesignField,
    *,
    agricultural: tuple[ActividadAgricolaSimplificado, ...],
    non_agricultural: tuple[ActividadNoAgricolaSimplificado, ...],
    by_annual_id: dict[str, ActividadOrdenAnual],
) -> M303RegimenSimplificadoFieldProjection:
    match = _ACTIVITY.search(field.description)
    if match is None:  # guarded by _nonnumbered_rs_fields
        raise RegistryValidationError(f"DP30302 field {field.ordinal} has no activity anchor")
    slot = int(match.group(1)) - 1
    is_agricultural = " - (A) Actividades agrícolas, ganaderas y forestales - " in field.description
    candidates: tuple[RegimenSimplificadoActivity, ...] = agricultural if is_agricultural else non_agricultural
    row = candidates[slot] if slot < len(candidates) else None
    value = None if row is None else _row_value(field, row=row, by_annual_id=by_annual_id)
    return M303RegimenSimplificadoFieldProjection(
        ordinal=field.ordinal,
        offset=field.offset,
        length=field.length,
        type_code=field.type_code,
        description=field.description,
        value=value,
    )


def _row_value(
    field: RecordDesignField,
    *,
    row: RegimenSimplificadoActivity,
    by_annual_id: dict[str, ActividadOrdenAnual],
) -> str | Decimal | None:
    suffix = _ACTIVITY.split(field.description, maxsplit=1)[-1].strip()
    if isinstance(row, ActividadAgricolaSimplificado) and suffix == "Código":
        return row.activity_code
    if isinstance(row, ActividadNoAgricolaSimplificado) and suffix == "Epigrafe IAE":
        return row.iae_epigrafe
    module_match = _MODULE.fullmatch(suffix)
    if isinstance(row, ActividadNoAgricolaSimplificado) and module_match is not None:
        module_order = int(module_match.group(1))
        annual = by_annual_id[row.orden_id]
        if module_order > len(annual.modulos):
            return None
        module_identity = annual.modulos[module_order - 1].identity
        entry = next(module for module in row.modulos if module.module_identity == module_identity)
        return entry.declared_quantity if module_match.group(2) == "Nº Unidades" else entry.off_form_result
    fact_identity = _fact_identity(suffix)
    annual = by_annual_id[row.orden_id]
    if fact_identity not in annual.applicable_fact_identities:
        return None
    facts = {fact.identity: fact.value for fact in row.facts}
    try:
        return facts[fact_identity]
    except KeyError as exc:
        raise RegistryValidationError(
            f"activity {row.activity_id!r} is missing applicable DP30302 fact {fact_identity!r}",
        ) from exc


def _fact_identity(description_suffix: str) -> str:
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", description_suffix.casefold().replace("º", "o"))
        if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    if not normalized:
        raise RegistryValidationError("a DP30302 fact description cannot normalize to an empty identity")
    return normalized


__all__ = [
    "M303RegimenSimplificadoFieldProjection",
    "M303RegimenSimplificadoRecordProjection",
    "m303_regimen_simplificado_nonnumbered_fields",
    "project_m303_regimen_simplificado_rows",
]
