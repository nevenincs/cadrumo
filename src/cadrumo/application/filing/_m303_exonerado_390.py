"""M303 exonerado-390 value arrival from one retained registry snapshot."""

from __future__ import annotations

from ...core import M303Exonerado390ActivityProjectionRef, M303Exonerado390OperacionesTercerosProjectionRef
from ...domain.calculations.registry import (
    M303Exonerado390RecordProjection,
    RegistrySnapshot,
    SourceReference,
    project_m303_exonerado_390_activity_rows,
)
from ...domain.filing import FilingExportError
from ...domain.modelos import M303Exonerado390FilingEvidence

type _ExoneradoProjectionRef = M303Exonerado390ActivityProjectionRef | M303Exonerado390OperacionesTercerosProjectionRef


def project_m303_exonerado_390_value_arrival(
    *,
    registry_snapshot: RegistrySnapshot,
    projection_refs: tuple[_ExoneradoProjectionRef, ...],
    evidence: M303Exonerado390FilingEvidence,
    record_design: SourceReference,
) -> M303Exonerado390RecordProjection | None:
    """Project the atomic DP30304 owner through the selected snapshot only."""
    snapshot_source = registry_snapshot.sources.get(record_design.id)
    if snapshot_source is None or snapshot_source.kind != "record_design":
        raise FilingExportError("modelo 303 exonerado-390 requires a snapshot-owned record-design source")
    if snapshot_source != record_design:
        raise FilingExportError("modelo 303 exonerado-390 record design does not match the selected snapshot")
    return project_m303_exonerado_390_activity_rows(
        projection_refs=projection_refs,
        evidence=evidence,
    )


__all__ = ["project_m303_exonerado_390_value_arrival"]
