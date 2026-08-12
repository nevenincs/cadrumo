"""Typed DP30304 projection from canonical exonerado-390 filing evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ....core import (
    STRICT_FROZEN_CONFIG,
    FilingProjectionRef,
    M303Exonerado390ActivityField,
    M303Exonerado390ActivityProjectionRef,
    M303Exonerado390OperacionesTercerosProjectionRef,
)
from ._errors import RegistryValidationError

if TYPE_CHECKING:
    from ...modelos import M303Exonerado390FilingEvidence

type _ExoneradoProjectionRef = M303Exonerado390ActivityProjectionRef | M303Exonerado390OperacionesTercerosProjectionRef


class M303Exonerado390FieldProjection(BaseModel):
    """One exact typed reference and its canonical projected value."""

    model_config = STRICT_FROZEN_CONFIG

    projection_ref: FilingProjectionRef
    value: str | None


class M303Exonerado390RecordProjection(BaseModel):
    """The complete exonerado-390 activity and Modelo 347 population."""

    model_config = STRICT_FROZEN_CONFIG

    fields: tuple[M303Exonerado390FieldProjection, ...] = Field(min_length=13, max_length=13)


def project_m303_exonerado_390_activity_rows(
    *,
    projection_refs: tuple[_ExoneradoProjectionRef, ...],
    evidence: M303Exonerado390FilingEvidence,
) -> M303Exonerado390RecordProjection | None:
    """Project ordered evidence rows through exact authored references."""
    refs = _validate_projection_refs(projection_refs)
    if not evidence.applicable:
        return None
    if tuple(row.slot for row in evidence.activity_rows) != (1, 2, 3, 4, 5, 6):
        raise RegistryValidationError("applicable exonerado-390 projection requires exactly six ordered activity rows")
    if evidence.operaciones_terceros_declarables is None or evidence.operaciones_terceros_reference is None:
        raise RegistryValidationError("applicable exonerado-390 projection requires an evidenced Modelo 347 decision")
    rows_by_slot = {row.slot: row for row in evidence.activity_rows}
    projected: list[M303Exonerado390FieldProjection] = []
    for ref in projection_refs:
        if isinstance(ref, M303Exonerado390OperacionesTercerosProjectionRef):
            value = "X" if evidence.operaciones_terceros_declarables else None
        else:
            row = rows_by_slot[ref.slot]
            if ref.field is M303Exonerado390ActivityField.ACTIVITY_CODE:
                value = row.codigo_actividad
            elif ref.field is M303Exonerado390ActivityField.IAE_EPIGRAFE:
                value = row.epigrafe_iae
            else:
                raise RegistryValidationError(f"unsupported exonerado-390 activity field {ref.field!r}")
        projected.append(M303Exonerado390FieldProjection(projection_ref=ref, value=value))
    projected_refs = tuple(field.projection_ref for field in projected)
    if len(projected_refs) != len(refs) or any(ref not in refs for ref in projected_refs):
        raise RegistryValidationError("DP30304 projection reference population changed during projection")
    return M303Exonerado390RecordProjection(fields=tuple(projected))


def _validate_projection_refs(refs: tuple[_ExoneradoProjectionRef, ...]) -> tuple[FilingProjectionRef, ...]:
    if any(refs.count(ref) > 1 for ref in refs):
        raise RegistryValidationError("DP30304 contains duplicate exonerado-390 projection references")
    expected: tuple[FilingProjectionRef, ...] = (
        *(
            M303Exonerado390ActivityProjectionRef(
                projection_kind="m303_exonerado_390_activity",
                slot=slot,
                field=field,
            )
            for slot in range(1, 7)
            for field in M303Exonerado390ActivityField
        ),
        M303Exonerado390OperacionesTercerosProjectionRef(
            projection_kind="m303_exonerado_390_operaciones_terceros",
        ),
    )
    if len(refs) != len(expected) or any(ref not in expected for ref in refs):
        raise RegistryValidationError("DP30304 requires six activity-code/IAE pairs and one Modelo 347 marker")
    return refs


__all__ = [
    "M303Exonerado390FieldProjection",
    "M303Exonerado390RecordProjection",
    "project_m303_exonerado_390_activity_rows",
]
