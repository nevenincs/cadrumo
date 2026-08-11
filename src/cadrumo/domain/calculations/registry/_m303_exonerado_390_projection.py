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
    rows_by_slot = {row.slot: row for row in evidence.activity_rows}
    projected: list[M303Exonerado390FieldProjection] = []
    for ref in projection_refs:
        if isinstance(ref, M303Exonerado390OperacionesTercerosProjectionRef):
            value = "X" if evidence.operaciones_terceros_declarables else None
        else:
            row = rows_by_slot.get(ref.slot)
            if row is None:
                value = None
            elif ref.field is M303Exonerado390ActivityField.ACTIVITY_CODE:
                value = row.codigo_actividad
            else:
                value = row.epigrafe_iae
        projected.append(M303Exonerado390FieldProjection(projection_ref=ref, value=value))
    if len(projected) != len(refs):
        raise RegistryValidationError("DP30304 projection reference population changed during projection")
    return M303Exonerado390RecordProjection(fields=tuple(projected))


def _validate_projection_refs(refs: tuple[_ExoneradoProjectionRef, ...]) -> frozenset[str]:
    identities = tuple(ref.model_dump_json() for ref in refs)
    if len(set(identities)) != len(identities):
        raise RegistryValidationError("DP30304 contains duplicate exonerado-390 projection references")
    expected = {
        M303Exonerado390ActivityProjectionRef(slot=slot, field=field).model_dump_json()
        for slot in range(1, 7)
        for field in M303Exonerado390ActivityField
    }
    expected.add(M303Exonerado390OperacionesTercerosProjectionRef().model_dump_json())
    actual = set(identities)
    if actual != expected:
        raise RegistryValidationError("DP30304 requires six activity-code/IAE pairs and one Modelo 347 marker")
    return frozenset(actual)


__all__ = [
    "M303Exonerado390FieldProjection",
    "M303Exonerado390RecordProjection",
    "project_m303_exonerado_390_activity_rows",
]
