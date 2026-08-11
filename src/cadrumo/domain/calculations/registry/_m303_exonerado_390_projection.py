"""Exact DP30304 projection from canonical exonerado-390 filing evidence."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG
from ._errors import RegistryValidationError
from ._record_design_schema import RecordDesignField, RecordDesignSheet

if TYPE_CHECKING:
    from ...modelos import M303Exonerado390FilingEvidence

_CASILLA_TAG = re.compile(r"\[\s*\d{1,3}\s*\]")
_ACTIVITY_CODE = "código de actividad"
_IAE_EPIGRAPH = "epígrafe iae"
_THIRD_PARTY_DECLARATION = "declaración anual de operaciones"


class M303Exonerado390FieldProjection(BaseModel):
    """One exact official DP30304 anchor and its canonical projected value."""

    model_config = STRICT_FROZEN_CONFIG

    ordinal: int = Field(gt=0)
    offset: int = Field(gt=0)
    length: int = Field(gt=0)
    type_code: str = Field(min_length=1)
    description: str = Field(min_length=1)
    value: str | None


class M303Exonerado390RecordProjection(BaseModel):
    """The complete nonnumbered exonerado-390 field population for DP30304."""

    model_config = STRICT_FROZEN_CONFIG

    fields: tuple[M303Exonerado390FieldProjection, ...] = Field(min_length=13, max_length=13)


def project_m303_exonerado_390_activity_rows(
    sheet: RecordDesignSheet,
    *,
    evidence: M303Exonerado390FilingEvidence,
) -> M303Exonerado390RecordProjection | None:
    """Project the ordered evidence rows and Modelo 347 decision to DP30304."""
    if sheet.name != "DP30304":
        raise RegistryValidationError("exonerado-390 projection requires the DP30304 source sheet")
    activity_fields, marker = _projection_fields(sheet)
    if not evidence.applicable:
        return None
    rows_by_slot = {row.slot: row for row in evidence.activity_rows}
    projected: list[M303Exonerado390FieldProjection] = []
    for slot in range(1, 7):
        row = rows_by_slot.get(slot)
        code_field, epigraph_field = activity_fields[(slot - 1) * 2 : slot * 2]
        projected.append(_field_value(code_field, None if row is None else row.codigo_actividad))
        projected.append(_field_value(epigraph_field, None if row is None else row.epigrafe_iae))
    marker_value = "X" if evidence.operaciones_terceros_declarables else None
    projected.append(_field_value(marker, marker_value))
    return M303Exonerado390RecordProjection(fields=tuple(projected))


def _projection_fields(sheet: RecordDesignSheet) -> tuple[tuple[RecordDesignField, ...], RecordDesignField]:
    unnumbered = tuple(
        field
        for field in sheet.fields
        if "exonerados de la declaración-resumen anual" in field.description.casefold()
        and _CASILLA_TAG.search(field.description) is None
    )
    activity_fields = tuple(
        field
        for field in unnumbered
        if _ACTIVITY_CODE in field.description.casefold() or _IAE_EPIGRAPH in field.description.casefold()
    )
    marker_fields = tuple(field for field in unnumbered if _THIRD_PARTY_DECLARATION in field.description.casefold())
    if len(activity_fields) != 12 or len(marker_fields) != 1:
        raise RegistryValidationError(
            "DP30304 must contain six activity-code/IAE pairs and one Modelo 347 marker",
        )
    for pair_index in range(6):
        code_field, epigraph_field = activity_fields[pair_index * 2 : pair_index * 2 + 2]
        if _ACTIVITY_CODE not in code_field.description.casefold() or code_field.length != 3:
            raise RegistryValidationError(f"DP30304 activity slot {pair_index + 1} has no exact code anchor")
        if _IAE_EPIGRAPH not in epigraph_field.description.casefold() or epigraph_field.length != 4:
            raise RegistryValidationError(f"DP30304 activity slot {pair_index + 1} has no exact IAE anchor")
    marker = marker_fields[0]
    if marker.length != 1:
        raise RegistryValidationError("DP30304 Modelo 347 marker must occupy exactly one character")
    return activity_fields, marker


def _field_value(field: RecordDesignField, value: str | None) -> M303Exonerado390FieldProjection:
    if value is not None and len(value) > field.length:
        raise RegistryValidationError(
            f"DP30304 field {field.ordinal} rejects value wider than its {field.length}-character anchor",
        )
    return M303Exonerado390FieldProjection(
        ordinal=field.ordinal,
        offset=field.offset,
        length=field.length,
        type_code=field.type_code,
        description=field.description,
        value=value,
    )


__all__ = [
    "M303Exonerado390FieldProjection",
    "M303Exonerado390RecordProjection",
    "project_m303_exonerado_390_activity_rows",
]
