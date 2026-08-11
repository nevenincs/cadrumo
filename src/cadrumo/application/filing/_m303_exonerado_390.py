"""M303 exonerado-390 value arrival from immutable revision evidence."""

from __future__ import annotations

from ...core import Period
from ...domain.calculations.registry import (
    M303Exonerado390RecordProjection,
    RegistryValidationError,
    SourceReference,
    extract_record_design,
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
) -> M303Exonerado390RecordProjection | None:
    """Resolve the cited source and project the canonical S56 row owner."""
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
    try:
        resolved = resolve_record_design_binary(
            schema_provider.source_root,
            schema_provider.sources,
            source_ref=record_design.id,
            filing_year=period.filing_year,
            design_epoch=design_epoch,
        )
        sheet = next((item for item in extract_record_design(resolved.path) if item.name == "DP30304"), None)
        if sheet is None:
            raise RegistryValidationError("resolved record design has no DP30304 exonerado-390 sheet")
        return project_m303_exonerado_390_activity_rows(
            sheet,
            design_epoch=design_epoch,
            expected_design_epoch=design_epoch,
            evidence=evidence,
        )
    except RegistryValidationError as exc:
        raise FilingExportError(f"modelo 303 exonerado-390 projection refused: {exc}") from exc


__all__ = ["project_m303_exonerado_390_value_arrival"]
