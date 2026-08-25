"""M303 exonerado-390 value arrival from one retained registry snapshot."""

from __future__ import annotations

from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ...core import M303Exonerado390ActivityProjectionRef, M303Exonerado390OperacionesTercerosProjectionRef, Modelo
from ...domain.calculations.registry.m303_exonerado_390_projection import (
    M303Exonerado390RecordProjection,
    project_m303_exonerado_390_activity_rows,
)
from ...domain.modelos import M303Exonerado390FilingEvidence
from .errors import ModeloApplicationError as FilingExportError

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
        raise FilingExportError(
            translated_message="application.filing.m303_exonerado_390.errors.record_design_source_not_snapshot_owned",
            context={
                "modelo": Modelo.M303.value,
                "record_design_id": record_design.id,
                "source_present": snapshot_source is not None,
                "source_kind": snapshot_source.kind if snapshot_source is not None else None,
            },
        )
    if snapshot_source != record_design:
        raise FilingExportError(
            translated_message="application.filing.m303_exonerado_390.errors.record_design_snapshot_mismatch",
            context={
                "modelo": Modelo.M303.value,
                "record_design_id": record_design.id,
                "snapshot_source_id": snapshot_source.id,
            },
        )
    return project_m303_exonerado_390_activity_rows(
        projection_refs=projection_refs,
        evidence=evidence,
    )


__all__ = ["project_m303_exonerado_390_value_arrival"]
