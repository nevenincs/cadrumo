"""Shared Modelo 200 source and parser-anchor lookup primitives."""

from __future__ import annotations

from collections.abc import Mapping

from ..pipeline.record_design_intermediate import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    intermediate_anchor_key,
)


def record_design_source(source_refs: tuple[str, ...], sources: Mapping[str, object]) -> str:
    """Resolve exactly one record-design source from a revision's source list."""
    matches = tuple(
        source_ref for source_ref in source_refs if getattr(sources.get(source_ref), "kind", None) == "record_design"
    )
    if len(matches) != 1:
        raise ValueError(f"M200 revision must have exactly one record-design source, found {matches!r}")
    return str(matches[0])


def record_design_field_index(
    design: RecordDesignIntermediate,
) -> dict[tuple[object, ...], RecordDesignIntermediateField]:
    """Index parser-read fields by their complete source anchor."""
    return {intermediate_anchor_key(field): field for sheet in design.sheets for field in sheet.fields}
