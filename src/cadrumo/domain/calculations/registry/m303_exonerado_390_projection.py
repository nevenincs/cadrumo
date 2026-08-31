"""Typed DP30304 projection from canonical exonerado-390 filing evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ....core.filing_projection_ref import (
    FilingProjectionRef,
    M303Exonerado390ActivityField,
    M303Exonerado390ActivityProjectionRef,
    M303Exonerado390OperacionesTercerosProjectionRef,
)
from ....core.models import STRICT_FROZEN_CONFIG
from .errors import RegistryValidationError

if TYPE_CHECKING:
    from ...modelos.calculation_revision_m303_evidence import (
        M303Exonerado390ActivityRowEvidence,
        M303Exonerado390FilingEvidence,
    )

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
    _require_operaciones_terceros_decision(evidence)
    rows_by_slot = {row.slot: row for row in evidence.activity_rows}
    projected = tuple(_project_exonerado_field(ref, evidence, rows_by_slot) for ref in projection_refs)
    _require_projected_reference_population(refs, projected)
    return M303Exonerado390RecordProjection(fields=projected)


def _require_operaciones_terceros_decision(evidence: M303Exonerado390FilingEvidence) -> None:
    """Require an applicable filing to carry the evidenced Modelo 347 decision."""
    if evidence.operaciones_terceros_declarables is None or evidence.operaciones_terceros_reference is None:
        raise RegistryValidationError("applicable exonerado-390 projection requires an evidenced Modelo 347 decision")


def _project_exonerado_field(
    ref: _ExoneradoProjectionRef,
    evidence: M303Exonerado390FilingEvidence,
    rows_by_slot: dict[int, M303Exonerado390ActivityRowEvidence],
) -> M303Exonerado390FieldProjection:
    """Project one authored exonerado-390 reference through typed evidence."""
    if isinstance(ref, M303Exonerado390OperacionesTercerosProjectionRef):
        value = "X" if evidence.operaciones_terceros_declarables else None
    else:
        row = rows_by_slot.get(ref.slot)
        value = None if row is None else _project_activity_field(ref, row)
    return M303Exonerado390FieldProjection(projection_ref=ref, value=value)


def _project_activity_field(
    ref: M303Exonerado390ActivityProjectionRef, row: M303Exonerado390ActivityRowEvidence
) -> str:
    """Project one activity pair field from its matching evidence row."""
    if ref.field is M303Exonerado390ActivityField.ACTIVITY_CODE:
        return row.codigo_actividad
    if ref.field is M303Exonerado390ActivityField.IAE_EPIGRAFE:
        return row.epigrafe_iae
    raise RegistryValidationError(f"unsupported exonerado-390 activity field {ref.field!r}")


def _require_projected_reference_population(
    refs: tuple[FilingProjectionRef, ...],
    projected: tuple[M303Exonerado390FieldProjection, ...],
) -> None:
    """Ensure projection preserves the authored reference population exactly."""
    projected_refs = tuple(field.projection_ref for field in projected)
    if len(projected_refs) != len(refs) or any(ref not in refs for ref in projected_refs):
        raise RegistryValidationError("DP30304 projection reference population changed during projection")


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
