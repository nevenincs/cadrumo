"""Exact DP30304 projection from immutable exonerado-390 filing evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG
from ._errors import RegistryValidationError
from ._record_design_schema import RecordDesignField, RecordDesignSheet

if TYPE_CHECKING:
    from ...modelos import M303Exonerado390FilingEvidence

_SUPPORTED_EPOCHS = frozenset({"2023", "2024-early", "2024-late", "2025", "2026"})
_EXPECTED_FIELD_SHAPE = (
    (6, 13, 3),
    (7, 16, 4),
    (8, 20, 3),
    (9, 23, 4),
    (10, 27, 3),
    (11, 30, 4),
    (12, 34, 3),
    (13, 37, 4),
    (14, 41, 3),
    (15, 44, 4),
    (16, 48, 3),
    (17, 51, 4),
    (18, 55, 1),
)
_EXONERADO_DESCRIPTION = "exonerados de la declaración-resumen anual"


class M303Exonerado390FieldProjection(BaseModel):
    """One exact DP30304 source field and its immutable evidence value."""

    model_config = STRICT_FROZEN_CONFIG

    ordinal: int = Field(gt=0)
    offset: int = Field(gt=0)
    length: int = Field(gt=0)
    type_code: str = Field(min_length=1)
    description: str = Field(min_length=1)
    value: str | None


class M303Exonerado390RecordProjection(BaseModel):
    """The intrinsically ordered six activity pairs and Modelo 347 marker."""

    model_config = STRICT_FROZEN_CONFIG

    design_epoch: str
    fields: tuple[M303Exonerado390FieldProjection, ...] = Field(min_length=13, max_length=13)


def project_m303_exonerado_390_activity_rows(
    sheet: RecordDesignSheet,
    *,
    design_epoch: str,
    expected_design_epoch: str,
    evidence: M303Exonerado390FilingEvidence,
) -> M303Exonerado390RecordProjection | None:
    """Project one complete applicable row owner in source-defined field order."""
    if sheet.name != "DP30304":
        raise RegistryValidationError("exonerado-390 projection requires the DP30304 source sheet")
    if design_epoch != expected_design_epoch or design_epoch not in _SUPPORTED_EPOCHS:
        raise RegistryValidationError("exonerado-390 projection refuses a wrong or unknown design epoch")
    if not evidence.applicable:
        return None
    if tuple(row.slot for row in evidence.activity_rows) != (1, 2, 3, 4, 5, 6):
        raise RegistryValidationError("applicable exonerado-390 projection requires exactly six ordered activity rows")
    if evidence.operaciones_terceros_declarables is None or evidence.operaciones_terceros_reference is None:
        raise RegistryValidationError("applicable exonerado-390 projection requires an evidenced Modelo 347 decision")
    fields = _exact_unnumbered_fields(sheet)
    values = (
        *(value for row in evidence.activity_rows for value in (row.codigo_actividad, row.epigrafe_iae)),
        "X" if evidence.operaciones_terceros_declarables else None,
    )
    return M303Exonerado390RecordProjection(
        design_epoch=design_epoch,
        fields=tuple(
            M303Exonerado390FieldProjection(
                ordinal=field.ordinal,
                offset=field.offset,
                length=field.length,
                type_code=field.type_code,
                description=field.description,
                value=value,
            )
            for field, value in zip(fields, values, strict=True)
        ),
    )


def _exact_unnumbered_fields(sheet: RecordDesignSheet) -> tuple[RecordDesignField, ...]:
    fields = tuple(
        field
        for field in sheet.fields
        if _EXONERADO_DESCRIPTION in field.description.casefold() and "[" not in field.description
    )
    shape = tuple((field.ordinal, field.offset, field.length) for field in fields)
    if shape != _EXPECTED_FIELD_SHAPE:
        raise RegistryValidationError(
            "DP30304 exonerado-390 unnumbered field geometry does not match the six-pair and Modelo 347 contract",
        )
    if any(field.type_code != "An" for field in fields):
        raise RegistryValidationError("DP30304 exonerado-390 fields must retain official alphanumeric type codes")
    return fields


__all__ = [
    "M303Exonerado390FieldProjection",
    "M303Exonerado390RecordProjection",
    "project_m303_exonerado_390_activity_rows",
]
