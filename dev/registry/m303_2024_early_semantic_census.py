"""Source-pinned review census for the Modelo 303 2024-early semantic map.

This is deliberately a verifier, not a mapper: all canonical homes are
authored in the TOML fragments.  It proves that those reviewed homes cover the
complete parsed source exactly once, retain the DP30300 envelope separately,
and preserve the S63 declaration-index boundary for simplified-regime rows.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Final

from ._record_design_ir import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    RecordDesignIntermediateRelativeSuffixMarker,
    RecordDesignIntermediateVariableEnvelope,
)
from ._semantic_map import SemanticMap, SemanticMapAnchor, SemanticMapEntry

__all__ = [
    "M303_2024_EARLY_CLASS_TOTALS",
    "M303_2024_EARLY_FIXED_ANCHOR_COUNT",
    "M303_2024_EARLY_REVIEW_HOME_TOTALS",
    "M303_2024_EARLY_SOURCE_REF",
    "M303_2024_EARLY_SOURCE_SHA256",
    "M303_2024_EARLY_TOTAL_ANCHOR_COUNT",
    "M303_2024_EARLY_VARIABLE_ENVELOPE_ANCHOR_COUNT",
    "M303_2024_EARLY_VARIABLE_ENVELOPE_ROLES",
    "M303SemanticCensus2024Early",
    "census_m303_2024_early_semantic_map",
]


M303_2024_EARLY_SOURCE_REF: Final[str] = "aeat-dr-303-2024-early"
M303_2024_EARLY_SOURCE_SHA256: Final[str] = "8b1f74b58b9293e60f9ea6fa3cc352a35ca3fe7d09a6705f122585e7f7da65b9"
M303_2024_EARLY_FIXED_ANCHOR_COUNT: Final[int] = 393
M303_2024_EARLY_VARIABLE_ENVELOPE_ANCHOR_COUNT: Final[int] = 13
M303_2024_EARLY_TOTAL_ANCHOR_COUNT: Final[int] = 406
M303_2024_EARLY_CLASS_TOTALS: Final[dict[str, int]] = {
    "casilla": 105,
    "computed": 5,
    "draft": 2,
    "filler": 13,
    "header": 24,
    "literal": 40,
    "projection": 204,
}
# These are the hand-reviewed semantic-home classes.  They are intentionally
# coarser than individual casilla ids, but distinguish every payload-owner
# family that needed a separate source/registry judgement in this epoch.
M303_2024_EARLY_REVIEW_HOME_TOTALS: Final[dict[str, int]] = {
    "casilla": 105,
    "computed": 5,
    "draft": 2,
    "filler": 13,
    "literal": 40,
    "producer": 24,
    "projection:m303_differentiated_deduction": 36,
    "projection:m303_exonerado_390_activity": 12,
    "projection:m303_exonerado_390_operaciones_terceros": 1,
    "projection:m303_prorrata_activity": 25,
    "projection:m303_regimen_simplificado_activity": 6,
    "projection:m303_regimen_simplificado_fact": 96,
    "projection:m303_regimen_simplificado_module": 28,
}
M303_2024_EARLY_VARIABLE_ENVELOPE_ROLES: Final[tuple[str, ...]] = (
    "opening_tag",
    "modelo",
    "discriminant",
    "filing_year",
    "period",
    "record_type",
    "aux_opening_tag",
    "pre_program_filler",
    "program_identifier",
    "between_identities_filler",
    "developer_tax_id",
    "post_developer_filler",
    "aux_closing_tag",
)


@dataclass(frozen=True, slots=True)
class M303SemanticCensus2024Early:
    """Measured, source-keyed census for the complete 2024-early design."""

    fixed_anchor_count: int
    variable_envelope_anchor_count: int
    total_anchor_count: int
    class_totals: dict[str, int]
    review_home_totals: dict[str, int]
    simplified_projection_anchor_count: int


def census_m303_2024_early_semantic_map(
    intermediate: RecordDesignIntermediate,
    semantic_map: SemanticMap,
) -> M303SemanticCensus2024Early:
    """Verify every source anchor has exactly one already-authored canonical home."""
    if intermediate.source.source_ref != M303_2024_EARLY_SOURCE_REF:
        raise ValueError("M303 2024-early census requires the exact aeat-dr-303-2024-early source")
    if intermediate.source.source_sha256 != M303_2024_EARLY_SOURCE_SHA256:
        raise ValueError("M303 2024-early census requires the pinned 2024-early source digest")
    if (
        str(semantic_map.source_ref) != M303_2024_EARLY_SOURCE_REF
        or semantic_map.source_sha256 != M303_2024_EARLY_SOURCE_SHA256
        or semantic_map.design_epoch != "2024-early"
    ):
        raise ValueError("M303 2024-early semantic map does not match the pinned 2024-early source")

    source_anchor_sequence = tuple(_field_anchor(field) for sheet in intermediate.sheets for field in sheet.fields)
    source_anchor_counts = Counter(source_anchor_sequence)
    duplicate_source_anchors = tuple(sorted(anchor for anchor, count in source_anchor_counts.items() if count != 1))
    if duplicate_source_anchors:
        raise ValueError(f"M303 2024-early parsed source repeats anchors: {duplicate_source_anchors!r}")
    semantic_anchor_sequence = tuple(_semantic_anchor(entry.anchor) for entry in semantic_map.entries)
    semantic_anchor_counts = Counter(semantic_anchor_sequence)
    duplicate_semantic_anchors = tuple(sorted(anchor for anchor, count in semantic_anchor_counts.items() if count != 1))
    if duplicate_semantic_anchors:
        raise ValueError(
            "M303 2024-early semantic map assigns an anchor more than once: "
            f"{duplicate_semantic_anchors!r}",
        )
    source_anchors = set(source_anchor_sequence)
    semantic_anchors = set(semantic_anchor_sequence)
    if source_anchors != semantic_anchors:
        missing = sorted(source_anchors - semantic_anchors)
        extra = sorted(semantic_anchors - source_anchors)
        raise ValueError(f"M303 2024-early map/source anchor mismatch: missing={missing!r}, extra={extra!r}")
    if len(source_anchor_sequence) != M303_2024_EARLY_FIXED_ANCHOR_COUNT:
        raise ValueError("M303 2024-early fixed source-anchor count drifted")

    class_totals = dict(sorted(Counter(entry.kind.value for entry in semantic_map.entries).items()))
    if class_totals != M303_2024_EARLY_CLASS_TOTALS:
        raise ValueError(f"M303 2024-early semantic-home class totals drifted: {class_totals!r}")
    review_home_totals = dict(sorted(Counter(_review_home(entry) for entry in semantic_map.entries).items()))
    if review_home_totals != M303_2024_EARLY_REVIEW_HOME_TOTALS:
        raise ValueError(f"M303 2024-early reviewed semantic-home totals drifted: {review_home_totals!r}")

    simplified_source_anchors = {
        ("DP30302", ordinal)
        for ordinal in (*range(6, 78), *range(90, 152))
        if ordinal not in {92, 94, 120, 122}
    }
    simplified_entries = tuple(
        entry
        for entry in semantic_map.entries
        if entry.projection_ref is not None
        and str(entry.projection_ref.projection_kind).startswith("m303_regimen_simplificado")
    )
    simplified_anchors = {(entry.anchor.record_identity, entry.anchor.ordinal) for entry in simplified_entries}
    if simplified_anchors != simplified_source_anchors:
        raise ValueError("M303 2024-early simplified projections must be exactly the S63 DP30302 anchor index")

    envelopes = semantic_map.variable_envelopes
    if len(envelopes) != 1:
        raise ValueError("M303 2024-early requires exactly one DP30300 semantic envelope")
    envelope = envelopes[0]
    parser_envelopes = intermediate.variable_envelopes
    if len(parser_envelopes) != 1:
        raise ValueError("M303 2024-early parsed source requires exactly one DP30300 envelope")
    parser_envelope = parser_envelopes[0]
    envelope_anchors = tuple(_semantic_anchor(item.anchor) for item in envelope.prefix_fields)
    parser_prefix_anchors = tuple(_field_anchor(field) for field in parser_envelope.prefix_fields)
    if envelope_anchors != parser_prefix_anchors:
        raise ValueError("M303 2024-early DP30300 prefix anchors do not match the parsed source")
    if len(envelope_anchors) != M303_2024_EARLY_VARIABLE_ENVELOPE_ANCHOR_COUNT:
        raise ValueError("M303 2024-early DP30300 prefix cardinality drifted")
    envelope_roles = tuple(field.role.value for field in envelope.prefix_fields)
    if envelope_roles != M303_2024_EARLY_VARIABLE_ENVELOPE_ROLES:
        raise ValueError("M303 2024-early DP30300 prefix semantic roles drifted")
    if _semantic_anchor(envelope.body_anchor) != _relative_anchor(parser_envelope, body=True):
        raise ValueError("M303 2024-early DP30300 body anchor drifted")
    if _semantic_anchor(envelope.closer_anchor) != _relative_anchor(parser_envelope, body=False):
        raise ValueError("M303 2024-early DP30300 closer anchor drifted")
    if (
        envelope.total_anchor.source_row != parser_envelope.total_source_row
        or envelope.total_anchor.source_cell != parser_envelope.total_source_cell
    ):
        raise ValueError("M303 2024-early DP30300 total anchor drifted")

    return M303SemanticCensus2024Early(
        fixed_anchor_count=len(source_anchors),
        variable_envelope_anchor_count=len(envelope_anchors),
        total_anchor_count=len(source_anchors) + len(envelope_anchors),
        class_totals=class_totals,
        review_home_totals=review_home_totals,
        simplified_projection_anchor_count=len(simplified_entries),
    )


def _field_anchor(field: RecordDesignIntermediateField) -> tuple[str, int, str | None, int, str]:
    return (
        str(field.sheet),
        int(field.source_row),
        field.source_cell,
        int(field.ordinal),
        str(field.record_identity),
    )


def _semantic_anchor(anchor: SemanticMapAnchor) -> tuple[str, int, str | None, int, str]:
    return (
        str(anchor.sheet),
        int(anchor.source_row),
        anchor.source_cell,
        int(anchor.ordinal),
        str(anchor.record_identity),
    )


def _relative_anchor(
    envelope: RecordDesignIntermediateVariableEnvelope,
    *,
    body: bool,
) -> tuple[str, int, str | None, int, str]:
    if body:
        return (
            str(envelope.sheet),
            int(envelope.body_source_row),
            envelope.body_source_cell,
            int(envelope.body_ordinal),
            str(envelope.record_identity),
        )
    closer = envelope.closing
    if not isinstance(closer, RecordDesignIntermediateRelativeSuffixMarker):
        raise ValueError("M303 2024-early DP30300 requires one simple relative closer")
    return (
        str(envelope.sheet),
        int(closer.source_row),
        closer.source_cell,
        int(closer.ordinal),
        str(envelope.record_identity),
    )


def _review_home(entry: SemanticMapEntry) -> str:
    """Return the persisted reviewer class for one already-typed semantic home."""
    if entry.projection_ref is not None:
        return f"projection:{entry.projection_ref.projection_kind}"
    if entry.producer_key is not None:
        return "producer"
    return entry.kind.value
