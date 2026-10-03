"""Canonical exact-anchor and duplicate helpers for render-profile validation."""

from __future__ import annotations

from collections.abc import Iterable

from .record_design_intermediate import RecordDesignIntermediateField
from .render_profile_model_base import RenderProfileAnchor


def _field_anchor(field: RecordDesignIntermediateField) -> RenderProfileAnchor:
    # ``ordinal_absent`` is DERIVED here rather than authored: this anchor is
    # built from the parser field itself, so a missing ordinal is an observed
    # fact about the design and not an authoring claim. The authored side keeps
    # the explicit declaration, which is what the comparison below is against.
    return RenderProfileAnchor(
        sheet=field.sheet,
        source_row=field.source_row,
        semantic_part_offset=field.semantic_part_offset,
        source_cell=field.source_cell,
        ordinal=field.ordinal,
        ordinal_absent=field.ordinal is None,
        record_identity=field.record_identity,
    )


def _duplicates[T](values: Iterable[T]) -> tuple[T, ...]:
    seen: set[T] = set()
    duplicates: set[T] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return tuple(sorted(duplicates, key=repr))


def _anchor_key(anchor: RenderProfileAnchor) -> tuple[str, int, int, str, str, str]:
    """Return a deterministic, total sort key -- presentation order, not AEAT order.

    Plain string ordering on ``ordinal`` is fine here: every use is a stable,
    reproducible listing (an error message, a persisted artefact), never an
    AEAT-numeric position a downstream index depends on.
    """
    return (
        anchor.sheet,
        anchor.source_row,
        anchor.semantic_part_offset or 0,
        anchor.ordinal or "",
        anchor.source_cell or "",
        anchor.record_identity,
    )


def _anchor_key_tuple(anchor: RenderProfileAnchor) -> tuple[str, int, str | None, str | None, str, int | None]:
    return (
        anchor.sheet,
        anchor.source_row,
        anchor.source_cell,
        anchor.ordinal,
        anchor.record_identity,
        anchor.semantic_part_offset,
    )
