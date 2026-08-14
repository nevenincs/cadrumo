"""Source-pinned review census for the Modelo 303 2023 semantic map.

This is deliberately a verifier, not a mapper: all canonical homes are
authored in the TOML fragments.  It proves that those reviewed homes cover the
complete parsed source exactly once, retain the DP30300 envelope separately,
and preserve the S63 declaration-index boundary for simplified-regime rows.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Final

from ._record_design_ir import RecordDesignIntermediate
from ._semantic_map import SemanticMap

__all__ = [
    "M303_2023_CLASS_TOTALS",
    "M303_2023_FIXED_ANCHOR_COUNT",
    "M303_2023_SOURCE_REF",
    "M303_2023_SOURCE_SHA256",
    "M303_2023_TOTAL_ANCHOR_COUNT",
    "M303_2023_VARIABLE_ENVELOPE_ANCHOR_COUNT",
    "M303_2023SemanticCensus",
    "census_m303_2023_semantic_map",
]


M303_2023_SOURCE_REF: Final[str] = "aeat-dr-303-2023"
M303_2023_SOURCE_SHA256: Final[str] = "72e463cb29984f535c9f56917d788ff0641965f116aeab47da5f76a59eecfbe4"
M303_2023_FIXED_ANCHOR_COUNT: Final[int] = 393
M303_2023_VARIABLE_ENVELOPE_ANCHOR_COUNT: Final[int] = 13
M303_2023_TOTAL_ANCHOR_COUNT: Final[int] = 406
M303_2023_CLASS_TOTALS: Final[dict[str, int]] = {
    "casilla": 105,
    "computed": 5,
    "draft": 2,
    "filler": 9,
    "header": 24,
    "literal": 40,
    "projection": 208,
}


@dataclass(frozen=True, slots=True)
class M303_2023SemanticCensus:
    """Measured, source-keyed census for the complete 2023 design."""

    fixed_anchor_count: int
    variable_envelope_anchor_count: int
    total_anchor_count: int
    class_totals: dict[str, int]
    simplified_projection_anchor_count: int


def census_m303_2023_semantic_map(
    intermediate: RecordDesignIntermediate,
    semantic_map: SemanticMap,
) -> M303_2023SemanticCensus:
    """Verify every source anchor has exactly one already-authored canonical home."""
    if intermediate.source.source_ref != M303_2023_SOURCE_REF:
        raise ValueError("M303 2023 census requires the exact aeat-dr-303-2023 source")
    if intermediate.source.source_sha256 != M303_2023_SOURCE_SHA256:
        raise ValueError("M303 2023 census requires the pinned 2023 source digest")
    if (
        str(semantic_map.source_ref) != M303_2023_SOURCE_REF
        or semantic_map.source_sha256 != M303_2023_SOURCE_SHA256
        or semantic_map.design_epoch != "2023"
    ):
        raise ValueError("M303 2023 semantic map does not match the pinned 2023 source")

    source_anchors = {_field_anchor(field) for sheet in intermediate.sheets for field in sheet.fields}
    semantic_anchors = {_semantic_anchor(entry.anchor) for entry in semantic_map.entries}
    if source_anchors != semantic_anchors:
        missing = sorted(source_anchors - semantic_anchors)
        extra = sorted(semantic_anchors - source_anchors)
        raise ValueError(f"M303 2023 map/source anchor mismatch: missing={missing!r}, extra={extra!r}")
    if len(source_anchors) != M303_2023_FIXED_ANCHOR_COUNT:
        raise ValueError("M303 2023 fixed source-anchor count drifted")

    class_totals = dict(sorted(Counter(entry.kind.value for entry in semantic_map.entries).items()))
    if class_totals != M303_2023_CLASS_TOTALS:
        raise ValueError(f"M303 2023 semantic-home class totals drifted: {class_totals!r}")

    simplified_source_anchors = {
        ("DP30302", ordinal)
        for ordinal in (*range(6, 78), *range(90, 152))
    }
    simplified_entries = tuple(
        entry
        for entry in semantic_map.entries
        if entry.projection_ref is not None
        and entry.projection_ref.projection_kind.startswith("m303_regimen_simplificado")
    )
    simplified_anchors = {(entry.anchor.record_identity, entry.anchor.ordinal) for entry in simplified_entries}
    if simplified_anchors != simplified_source_anchors:
        raise ValueError("M303 2023 simplified projections must be exactly the S63 DP30302 anchor index")

    envelopes = semantic_map.variable_envelopes
    if len(envelopes) != 1:
        raise ValueError("M303 2023 requires exactly one DP30300 semantic envelope")
    envelope = envelopes[0]
    parser_envelopes = intermediate.variable_envelopes
    if len(parser_envelopes) != 1:
        raise ValueError("M303 2023 parsed source requires exactly one DP30300 envelope")
    parser_envelope = parser_envelopes[0]
    envelope_anchors = tuple(_semantic_anchor(item.anchor) for item in envelope.prefix_fields)
    parser_prefix_anchors = tuple(_field_anchor(field) for field in parser_envelope.prefix_fields)
    if envelope_anchors != parser_prefix_anchors:
        raise ValueError("M303 2023 DP30300 prefix anchors do not match the parsed source")
    if len(envelope_anchors) != M303_2023_VARIABLE_ENVELOPE_ANCHOR_COUNT:
        raise ValueError("M303 2023 DP30300 prefix cardinality drifted")
    if _semantic_anchor(envelope.body_anchor) != _relative_anchor(parser_envelope, body=True):
        raise ValueError("M303 2023 DP30300 body anchor drifted")
    if _semantic_anchor(envelope.closer_anchor) != _relative_anchor(parser_envelope, body=False):
        raise ValueError("M303 2023 DP30300 closer anchor drifted")
    if (
        envelope.total_anchor.source_row != parser_envelope.total_source_row
        or envelope.total_anchor.source_cell != parser_envelope.total_source_cell
    ):
        raise ValueError("M303 2023 DP30300 total anchor drifted")

    return M303_2023SemanticCensus(
        fixed_anchor_count=len(source_anchors),
        variable_envelope_anchor_count=len(envelope_anchors),
        total_anchor_count=len(source_anchors) + len(envelope_anchors),
        class_totals=class_totals,
        simplified_projection_anchor_count=len(simplified_entries),
    )


def _field_anchor(field: object) -> tuple[str, int, str | None, int, str]:
    return (
        str(getattr(field, "sheet")),
        int(getattr(field, "source_row")),
        getattr(field, "source_cell"),
        int(getattr(field, "ordinal")),
        str(getattr(field, "record_identity")),
    )


def _semantic_anchor(anchor: object) -> tuple[str, int, str | None, int, str]:
    return (
        str(getattr(anchor, "sheet")),
        int(getattr(anchor, "source_row")),
        getattr(anchor, "source_cell"),
        int(getattr(anchor, "ordinal")),
        str(getattr(anchor, "record_identity")),
    )


def _relative_anchor(envelope: object, *, body: bool) -> tuple[str, int, str | None, int, str]:
    if body:
        return (
            str(getattr(envelope, "sheet")),
            int(getattr(envelope, "body_source_row")),
            getattr(envelope, "body_source_cell"),
            int(getattr(envelope, "body_ordinal")),
            str(getattr(envelope, "record_identity")),
        )
    closer = getattr(envelope, "closing")
    return (
        str(getattr(envelope, "sheet")),
        int(getattr(closer, "source_row")),
        getattr(closer, "source_cell"),
        int(getattr(closer, "ordinal")),
        str(getattr(envelope, "record_identity")),
    )
