"""M303 exonerado-390 activity-row value arrival before export targets."""

from __future__ import annotations

from ...core import (
    M303Exonerado390ActivityProjectionRef,
    M303Exonerado390OperacionesTercerosProjectionRef,
    Period,
)
from ...domain.calculations.registry import (
    M303Exonerado390RecordProjection,
    RegistryValidationError,
    SourceReference,
    project_m303_exonerado_390_activity_rows,
    resolve_record_design_binary,
)
from ...domain.filing import FilingExportError
from ...domain.modelos import M303Exonerado390FilingEvidence
from .runtime import RegistrySchemaAccessor


def project_m303_exonerado_390_value_arrival(
    *,
    period: Period,
    schema_provider: RegistrySchemaAccessor,
    evidence: M303Exonerado390FilingEvidence,
    record_design: SourceReference,
    projection_refs: tuple[
        M303Exonerado390ActivityProjectionRef | M303Exonerado390OperacionesTercerosProjectionRef,
        ...,
    ],
) -> M303Exonerado390RecordProjection | None:
    """Project the immutable S56 rows through the exact source selected by S59."""
    if schema_provider.source_root is None:
        raise FilingExportError("modelo 303 exonerado-390 projection requires the registry source root")
    subview = schema_provider.get_subview("303")
    if record_design.id not in subview.source_ref_ids:
        raise FilingExportError("modelo 303 exonerado-390 record design is not cited by the active revision")
    registry_source = schema_provider.sources.get(record_design.id)
    if registry_source is None or registry_source.kind != "record_design":
        raise FilingExportError("modelo 303 exonerado-390 requires a cited record-design source")
    if registry_source != record_design:
        raise FilingExportError("modelo 303 exonerado-390 record design no longer matches the registry")
    design_epoch = record_design.record_design_epoch
    if design_epoch is None:
        raise FilingExportError("modelo 303 exonerado-390 record design has no design epoch")
    resolved = resolve_record_design_binary(
        schema_provider.source_root,
        schema_provider.sources,
        source_ref=record_design.id,
        filing_year=period.filing_year,
        design_epoch=design_epoch,
    )
    try:
        if not resolved.path.is_file():
            raise RegistryValidationError("the resolved exonerado-390 record design is not a file")
        return project_m303_exonerado_390_activity_rows(projection_refs=projection_refs, evidence=evidence)
    except RegistryValidationError as exc:
        raise FilingExportError(f"modelo 303 exonerado-390 projection refused: {exc}") from exc


__all__ = ["project_m303_exonerado_390_value_arrival"]
