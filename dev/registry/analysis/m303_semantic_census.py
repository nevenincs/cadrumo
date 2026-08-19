"""Source-pinned review census for every Modelo 303 semantic-map design epoch.

This is deliberately a verifier, not a mapper: all canonical homes are
authored in the TOML fragments.  It proves that those reviewed homes cover the
complete parsed source exactly once, retain the DP30300 envelope separately,
and preserve the S63 declaration-index boundary for simplified-regime rows.

ONE implementation serves every AEAT design epoch.  The per-epoch copies this
replaces were identical apart from their epoch label and their measured totals,
so each new AEAT re-layout cost another module; here it costs one row in
:data:`M303_SEMANTIC_CENSUS_EXPECTATIONS`.

The source identity is NOT restated here.  Each map fragment already declares
its own ``source_ref`` and ``source_sha256``, and the census asserts those
against the parsed design's own source, so the chain map -> source catalogue ->
bundled AEAT file closes without a Python-side copy of either value.  A
transcribed digest could only ever agree with the fragment it was copied from.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from ..pipeline._record_design_ir import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    RecordDesignIntermediateRelativeSuffixMarker,
    RecordDesignIntermediateVariableEnvelope,
)
from ..pipeline._semantic_map import SemanticMap, SemanticMapAnchor, SemanticMapEntry

__all__ = [
    "M303_SEMANTIC_CENSUS_EXPECTATIONS",
    "M303_VARIABLE_ENVELOPE_ANCHOR_COUNT",
    "M303_VARIABLE_ENVELOPE_ROLES",
    "EpochAnchorPairing",
    "M303SemanticCensus",
    "M303SemanticCensusExpectation",
    "SemanticHome",
    "census_m303_semantic_map",
    "design_declaration_key",
    "pair_epoch_anchors",
    "resolve_semantic_home",
]


#: The DP30300 auxiliary envelope prefix is one AEAT contract carried unchanged
#: across every bundled 303 design, so it is declared once rather than per
#: epoch.  An epoch that ever diverges fails the role comparison by name, which
#: is the signal to give the table its own column.
M303_VARIABLE_ENVELOPE_ROLES: Final[tuple[str, ...]] = (
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
M303_VARIABLE_ENVELOPE_ANCHOR_COUNT: Final[int] = len(M303_VARIABLE_ENVELOPE_ROLES)


@dataclass(frozen=True, slots=True)
class M303SemanticCensusExpectation:
    """The reviewed, epoch-specific totals one design must still measure."""

    design_epoch: str
    fixed_anchor_count: int
    #: Totals over the persisted ``kind`` of every semantic-map entry.
    class_totals: Mapping[str, int]
    #: Totals over the hand-reviewed semantic-home classes.  They are
    #: intentionally coarser than individual casilla ids, but distinguish every
    #: payload-owner family that needed a separate source/registry judgement in
    #: this epoch.  Kept alongside ``class_totals`` rather than derived from it:
    #: the two agree today only because every producer-keyed entry happens to be
    #: a header, which is a measurement rather than an invariant.
    review_home_totals: Mapping[str, int]
    #: The S63 declaration-index spans that carry simplified-regime projections.
    #: DP30302's simplified rows are a plain sequential AEAT numbering with no
    #: dotted or ``bis`` label, so the census still expresses them as ``int``
    #: here; :attr:`simplified_anchors` renders each to the printed ``str``
    #: ordinal the parser and semantic map now carry.
    simplified_ordinal_spans: tuple[range, ...]
    #: Ordinals inside those spans that the design reserves as fillers.
    simplified_filler_ordinals: frozenset[int]

    @property
    def total_anchor_count(self) -> int:
        """Return the fixed anchors plus the separate DP30300 envelope prefix."""
        return self.fixed_anchor_count + M303_VARIABLE_ENVELOPE_ANCHOR_COUNT

    @property
    def simplified_anchors(self) -> frozenset[tuple[str, str]]:
        """Return the exact DP30302 anchor index simplified projections must cover."""
        return frozenset(
            ("DP30302", str(ordinal))
            for span in self.simplified_ordinal_spans
            for ordinal in span
            if ordinal not in self.simplified_filler_ordinals
        )


M303_SEMANTIC_CENSUS_EXPECTATIONS: Final[Mapping[str, M303SemanticCensusExpectation]] = {
    "2022": M303SemanticCensusExpectation(
        # The 2022 semantic map was authored without its census expectation, so
        # every case that censuses this epoch refused with "no reviewed
        # expectation" -- the map exists and resolves, but nothing pinned its
        # shape. The anchor count is cross-checked against the design itself:
        # the 2022 diseno parses to 314 fields, which is the figure the map's
        # own authoring recorded.
        #
        # This epoch carries markedly fewer simplified-regime entries than 2023
        # (38 facts against 100) and no pure-INTEGER DP30302 slot at all: the
        # Regimen Simplificado actividad modules -- epigrafe, numero de unidades,
        # modulos -- arrive on DP30302 with the 2023 design.
        design_epoch="2022",
        fixed_anchor_count=314,
        class_totals={
            "casilla": 103,
            "computed": 5,
            "draft": 2,
            "filler": 7,
            "header": 24,
            "literal": 27,
            "projection": 146,
        },
        review_home_totals={
            "casilla": 103,
            "computed": 5,
            "draft": 2,
            "filler": 7,
            "literal": 27,
            "producer": 24,
            "projection:m303_differentiated_deduction": 36,
            "projection:m303_exonerado_390_activity": 12,
            "projection:m303_exonerado_390_operaciones_terceros": 1,
            "projection:m303_prorrata_activity": 25,
            "projection:m303_regimen_simplificado_activity": 6,
            "projection:m303_regimen_simplificado_fact": 38,
            "projection:m303_regimen_simplificado_module": 28,
        },
        # One contiguous span, verified gap-free: ordinals 6..77 inclusive, all
        # 72 carrying a simplified projection, so no ordinal is carved out.
        simplified_ordinal_spans=(range(6, 78),),
        simplified_filler_ordinals=frozenset(),
    ),
    "2023": M303SemanticCensusExpectation(
        design_epoch="2023",
        fixed_anchor_count=393,
        class_totals={
            "casilla": 106,
            "computed": 5,
            "draft": 2,
            "filler": 9,
            "header": 24,
            "literal": 39,
            "projection": 208,
        },
        review_home_totals={
            "casilla": 106,
            "computed": 5,
            "draft": 2,
            "filler": 9,
            "literal": 39,
            "producer": 24,
            "projection:m303_differentiated_deduction": 36,
            "projection:m303_exonerado_390_activity": 12,
            "projection:m303_exonerado_390_operaciones_terceros": 1,
            "projection:m303_prorrata_activity": 25,
            "projection:m303_regimen_simplificado_activity": 6,
            "projection:m303_regimen_simplificado_fact": 100,
            "projection:m303_regimen_simplificado_module": 28,
        },
        simplified_ordinal_spans=(range(6, 78), range(90, 152)),
        simplified_filler_ordinals=frozenset(),
    ),
    "2024-early": M303SemanticCensusExpectation(
        design_epoch="2024-early",
        fixed_anchor_count=393,
        class_totals={
            "casilla": 106,
            "computed": 5,
            "draft": 2,
            "filler": 13,
            "header": 24,
            "literal": 39,
            "projection": 204,
        },
        review_home_totals={
            "casilla": 106,
            "computed": 5,
            "draft": 2,
            "filler": 13,
            "literal": 39,
            "producer": 24,
            "projection:m303_differentiated_deduction": 36,
            "projection:m303_exonerado_390_activity": 12,
            "projection:m303_exonerado_390_operaciones_terceros": 1,
            "projection:m303_prorrata_activity": 25,
            "projection:m303_regimen_simplificado_activity": 6,
            "projection:m303_regimen_simplificado_fact": 96,
            "projection:m303_regimen_simplificado_module": 28,
        },
        simplified_ordinal_spans=(range(6, 78), range(90, 152)),
        simplified_filler_ordinals=frozenset({92, 94, 120, 122}),
    ),
    "2024-late": M303SemanticCensusExpectation(
        design_epoch="2024-late",
        fixed_anchor_count=413,
        class_totals={
            "casilla": 114,
            "computed": 4,
            "draft": 2,
            "filler": 12,
            "header": 28,
            "literal": 39,
            "projection": 214,
        },
        review_home_totals={
            "casilla": 114,
            "computed": 4,
            "draft": 2,
            "filler": 12,
            "literal": 39,
            "producer": 28,
            "projection:m303_differentiated_deduction": 36,
            "projection:m303_exonerado_390_activity": 12,
            "projection:m303_exonerado_390_operaciones_terceros": 1,
            "projection:m303_prorrata_activity": 25,
            "projection:m303_regimen_simplificado_activity": 6,
            "projection:m303_regimen_simplificado_fact": 106,
            "projection:m303_regimen_simplificado_module": 28,
        },
        simplified_ordinal_spans=(range(6, 78), range(90, 162)),
        simplified_filler_ordinals=frozenset({92, 94, 121, 123}),
    ),
    "2025": M303SemanticCensusExpectation(
        design_epoch="2025",
        fixed_anchor_count=416,
        class_totals={
            "casilla": 113,
            "computed": 4,
            "draft": 2,
            "filler": 13,
            "header": 28,
            "literal": 40,
            "projection": 216,
        },
        review_home_totals={
            "casilla": 113,
            "computed": 4,
            "draft": 2,
            "filler": 13,
            "literal": 40,
            "producer": 28,
            "projection:m303_differentiated_deduction": 36,
            "projection:m303_exonerado_390_activity": 12,
            "projection:m303_exonerado_390_operaciones_terceros": 1,
            "projection:m303_prorrata_activity": 25,
            "projection:m303_regimen_simplificado_activity": 6,
            "projection:m303_regimen_simplificado_fact": 108,
            "projection:m303_regimen_simplificado_module": 28,
        },
        simplified_ordinal_spans=(range(6, 78), range(90, 165)),
        simplified_filler_ordinals=frozenset({92, 94, 119, 121, 148}),
    ),
    "2026": M303SemanticCensusExpectation(
        design_epoch="2026",
        fixed_anchor_count=417,
        class_totals={
            "casilla": 114,
            "computed": 4,
            "draft": 2,
            "filler": 12,
            "header": 29,
            "literal": 40,
            "projection": 216,
        },
        review_home_totals={
            "casilla": 114,
            "computed": 4,
            "draft": 2,
            "filler": 12,
            "literal": 40,
            "producer": 29,
            "projection:m303_differentiated_deduction": 36,
            "projection:m303_exonerado_390_activity": 12,
            "projection:m303_exonerado_390_operaciones_terceros": 1,
            "projection:m303_prorrata_activity": 25,
            "projection:m303_regimen_simplificado_activity": 6,
            "projection:m303_regimen_simplificado_fact": 108,
            "projection:m303_regimen_simplificado_module": 28,
        },
        simplified_ordinal_spans=(range(6, 78), range(90, 165)),
        simplified_filler_ordinals=frozenset({92, 94, 119, 121, 148}),
    ),
}


@dataclass(frozen=True, slots=True)
class EpochAnchorPairing:
    """How two epochs' anchors correspond, by the designs' own declarations."""

    #: Target anchor -> the predecessor anchor declaring the same slot.
    paired: Mapping[tuple[str, str | None], tuple[str, str | None]]
    #: Target anchors the predecessor does not declare, or declares a different
    #: number of times. Every one is a hand-review question.
    unpaired_target: frozenset[tuple[str, str | None]]
    #: The mirror image: predecessor anchors this epoch stops declaring.
    unpaired_predecessor: frozenset[tuple[str, str | None]]


@dataclass(frozen=True, slots=True)
class SemanticHome:
    """One mapped anchor's semantic home, at the two granularities in use."""

    #: The payload-owner family, which the census totals count.
    review_class: str
    #: The full identity, distinguishing two homes of the SAME class -- two
    #: casillas, or two simplified-regime cohorts, slots or sub-indices.
    identity: str


@dataclass(frozen=True, slots=True)
class M303SemanticCensus:
    """Measured, source-keyed census for one complete design epoch."""

    design_epoch: str
    fixed_anchor_count: int
    variable_envelope_anchor_count: int
    total_anchor_count: int
    class_totals: dict[str, int]
    review_home_totals: dict[str, int]
    simplified_projection_anchor_count: int


def census_m303_semantic_map(
    intermediate: RecordDesignIntermediate,
    semantic_map: SemanticMap,
    *,
    design_epoch: str,
) -> M303SemanticCensus:
    """Verify every source anchor has exactly one already-authored canonical home."""
    expectation = M303_SEMANTIC_CENSUS_EXPECTATIONS.get(design_epoch)
    if expectation is None:
        raise ValueError(
            f"M303 semantic census has no reviewed expectation for design epoch {design_epoch!r}; "
            "a newly authored epoch must be reviewed and enrolled before it can be censused",
        )
    if semantic_map.design_epoch != design_epoch:
        raise ValueError(
            f"M303 {design_epoch} census requires a semantic map authored for that epoch, "
            f"not {semantic_map.design_epoch!r}",
        )
    if str(semantic_map.source_ref) != str(intermediate.source.source_ref):
        raise ValueError(
            f"M303 {design_epoch} semantic map cites source {str(semantic_map.source_ref)!r} "
            f"but the parsed design is {str(intermediate.source.source_ref)!r}",
        )
    if semantic_map.source_sha256 != intermediate.source.source_sha256:
        raise ValueError(f"M303 {design_epoch} semantic map does not match the parsed design digest")

    source_anchor_sequence = tuple(_field_anchor(field) for sheet in intermediate.sheets for field in sheet.fields)
    source_anchor_counts = Counter(source_anchor_sequence)
    duplicate_source_anchors = tuple(sorted(anchor for anchor, count in source_anchor_counts.items() if count != 1))
    if duplicate_source_anchors:
        raise ValueError(f"M303 {design_epoch} parsed source repeats anchors: {duplicate_source_anchors!r}")
    semantic_anchor_sequence = tuple(_semantic_anchor(entry.anchor) for entry in semantic_map.entries)
    semantic_anchor_counts = Counter(semantic_anchor_sequence)
    duplicate_semantic_anchors = tuple(sorted(anchor for anchor, count in semantic_anchor_counts.items() if count != 1))
    if duplicate_semantic_anchors:
        raise ValueError(
            f"M303 {design_epoch} semantic map assigns an anchor more than once: {duplicate_semantic_anchors!r}",
        )
    source_anchors = set(source_anchor_sequence)
    semantic_anchors = set(semantic_anchor_sequence)
    if source_anchors != semantic_anchors:
        missing = sorted(source_anchors - semantic_anchors)
        extra = sorted(semantic_anchors - source_anchors)
        raise ValueError(f"M303 {design_epoch} map/source anchor mismatch: missing={missing!r}, extra={extra!r}")
    if len(source_anchor_sequence) != expectation.fixed_anchor_count:
        raise ValueError(f"M303 {design_epoch} fixed source-anchor count drifted")

    class_totals = dict(sorted(Counter(entry.kind.value for entry in semantic_map.entries).items()))
    if class_totals != dict(expectation.class_totals):
        raise ValueError(f"M303 {design_epoch} semantic-home class totals drifted: {class_totals!r}")
    review_home_totals = dict(
        sorted(Counter(resolve_semantic_home(entry).review_class for entry in semantic_map.entries).items())
    )
    if review_home_totals != dict(expectation.review_home_totals):
        raise ValueError(f"M303 {design_epoch} reviewed semantic-home totals drifted: {review_home_totals!r}")

    simplified_entries = tuple(
        entry
        for entry in semantic_map.entries
        if entry.projection_ref is not None
        and str(entry.projection_ref.projection_kind).startswith("m303_regimen_simplificado")
    )
    simplified_anchors = {(entry.anchor.record_identity, entry.anchor.ordinal) for entry in simplified_entries}
    if simplified_anchors != set(expectation.simplified_anchors):
        raise ValueError(f"M303 {design_epoch} simplified projections must be exactly the S63 DP30302 anchor index")
    # An ordinal is carved out of the simplified index only because the design
    # reserves it, so the carve-out must be justified by the map rather than
    # merely tolerated: a reserved ordinal that acquired a payload owner would
    # otherwise leave the index silently short by one.
    misclassified_reserved = tuple(
        sorted(
            ordinal
            for ordinal in expectation.simplified_filler_ordinals
            if _entry_at(semantic_map, "DP30302", ordinal).kind.value != "filler"
        ),
    )
    if misclassified_reserved:
        raise ValueError(
            f"M303 {design_epoch} reserved S63 ordinals must stay fillers: {misclassified_reserved!r}",
        )

    envelopes = semantic_map.variable_envelopes
    if len(envelopes) != 1:
        raise ValueError(f"M303 {design_epoch} requires exactly one DP30300 semantic envelope")
    envelope = envelopes[0]
    parser_envelopes = intermediate.variable_envelopes
    if len(parser_envelopes) != 1:
        raise ValueError(f"M303 {design_epoch} parsed source requires exactly one DP30300 envelope")
    parser_envelope = parser_envelopes[0]
    envelope_anchors = tuple(_semantic_anchor(item.anchor) for item in envelope.prefix_fields)
    parser_prefix_anchors = tuple(_field_anchor(field) for field in parser_envelope.prefix_fields)
    if envelope_anchors != parser_prefix_anchors:
        raise ValueError(f"M303 {design_epoch} DP30300 prefix anchors do not match the parsed source")
    if len(envelope_anchors) != M303_VARIABLE_ENVELOPE_ANCHOR_COUNT:
        raise ValueError(f"M303 {design_epoch} DP30300 prefix cardinality drifted")
    envelope_roles = tuple(field.role.value for field in envelope.prefix_fields)
    if envelope_roles != M303_VARIABLE_ENVELOPE_ROLES:
        raise ValueError(f"M303 {design_epoch} DP30300 prefix semantic roles drifted")
    if _semantic_anchor(envelope.body_anchor) != _relative_anchor(parser_envelope, design_epoch, body=True):
        raise ValueError(f"M303 {design_epoch} DP30300 body anchor drifted")
    if _semantic_anchor(envelope.closer_anchor) != _relative_anchor(parser_envelope, design_epoch, body=False):
        raise ValueError(f"M303 {design_epoch} DP30300 closer anchor drifted")
    if (
        envelope.total_anchor.source_row != parser_envelope.total_source_row
        or envelope.total_anchor.source_cell != parser_envelope.total_source_cell
    ):
        raise ValueError(f"M303 {design_epoch} DP30300 total anchor drifted")

    return M303SemanticCensus(
        design_epoch=design_epoch,
        fixed_anchor_count=len(source_anchors),
        variable_envelope_anchor_count=len(envelope_anchors),
        total_anchor_count=len(source_anchors) + len(envelope_anchors),
        class_totals=class_totals,
        review_home_totals=review_home_totals,
        simplified_projection_anchor_count=len(simplified_entries),
    )


def _entry_at(semantic_map: SemanticMap, record_identity: str, ordinal: int) -> SemanticMapEntry:
    for entry in semantic_map.entries:
        if entry.anchor.record_identity == record_identity and entry.anchor.ordinal == str(ordinal):
            return entry
    raise ValueError(f"semantic map has no entry at {record_identity}/{ordinal}")


def _field_anchor(field: RecordDesignIntermediateField) -> tuple[str, int, str | None, str | None, str]:
    return (
        str(field.sheet),
        int(field.source_row),
        field.source_cell,
        field.ordinal,
        str(field.record_identity),
    )


def _semantic_anchor(anchor: SemanticMapAnchor) -> tuple[str, int, str | None, str | None, str]:
    return (
        str(anchor.sheet),
        int(anchor.source_row),
        anchor.source_cell,
        anchor.ordinal,
        str(anchor.record_identity),
    )


def _relative_anchor(
    envelope: RecordDesignIntermediateVariableEnvelope,
    design_epoch: str,
    *,
    body: bool,
) -> tuple[str, int, str | None, str | None, str]:
    if body:
        # ``body_ordinal`` stays the marker's genuine ``int`` -- it is a
        # sequential envelope marker, never a printed field label -- so it is
        # rendered to ``str`` only here, at the boundary with the now-``str``
        # anchor it is compared against.
        return (
            str(envelope.sheet),
            int(envelope.body_source_row),
            envelope.body_source_cell,
            str(envelope.body_ordinal),
            str(envelope.record_identity),
        )
    closer = envelope.closing
    if not isinstance(closer, RecordDesignIntermediateRelativeSuffixMarker):
        raise ValueError(f"M303 {design_epoch} DP30300 requires one simple relative closer")
    return (
        str(envelope.sheet),
        int(closer.source_row),
        closer.source_cell,
        str(closer.ordinal),
        str(envelope.record_identity),
    )


def design_declaration_key(field: RecordDesignIntermediateField) -> tuple[str, str, str, int, str, str]:
    """Return everything the OFFICIAL DESIGN itself says about one slot.

    This is the only sanctioned way to decide that two epochs are talking about
    the same slot.  It reads the design's own declarations -- record, label,
    stated content, width, AEAT type, validation -- and deliberately excludes
    ordinal, row and offset, because a re-layout moves those while changing
    nothing about what the slot means.
    """
    return (
        str(field.record_identity),
        " ".join(field.normalized_description.split()),
        " ".join((field.content or "").split()),
        int(field.length),
        str(field.aeat_type).strip(),
        " ".join((field.validation or "").split()),
    )


def pair_epoch_anchors(
    predecessor: RecordDesignIntermediate,
    target: RecordDesignIntermediate,
) -> EpochAnchorPairing:
    """Correspond two epochs' anchors by what their design declares, never by position.

    A slot in one epoch corresponds to a slot in the other only when both
    designs declare it identically.  Where one declaration repeats inside a
    record -- the module slots the design distinguishes only by repetition --
    the occurrences correspond in order, and ONLY when both epochs declare the
    same number of them; an unequal count means the multiplicity changed, which
    is a review question rather than something to pair through.

    This is the single canonical correspondence: map authoring carries reviewed
    homes across an epoch boundary through it, and the epoch gates verify
    against it, so the two cannot hold different notions of "the same slot".
    """
    before: dict[tuple[str, str, str, int, str, str], list[tuple[str, str | None]]] = {}
    after: dict[tuple[str, str, str, int, str, str], list[tuple[str, str | None]]] = {}
    for source, sink in ((predecessor, before), (target, after)):
        for sheet in source.sheets:
            for field in sheet.fields:
                sink.setdefault(design_declaration_key(field), []).append(
                    (str(field.record_identity), field.ordinal),
                )

    paired: dict[tuple[str, str | None], tuple[str, str | None]] = {}
    unpaired_target: set[tuple[str, str | None]] = set()
    for key, anchors in after.items():
        counterparts = before.get(key, [])
        if len(counterparts) != len(anchors):
            unpaired_target.update(anchors)
            continue
        paired.update(zip(anchors, counterparts, strict=True))
    unpaired_predecessor = {
        anchor for key, anchors in before.items() if len(after.get(key, [])) != len(anchors) for anchor in anchors
    }
    return EpochAnchorPairing(
        paired=paired,
        unpaired_target=frozenset(unpaired_target),
        unpaired_predecessor=frozenset(unpaired_predecessor),
    )


def resolve_semantic_home(entry: SemanticMapEntry) -> SemanticHome:
    """Return the one canonical reading of where a mapped anchor's value comes from.

    This is the SOLE place that decides what an entry's semantic home is.  Two
    granularities are needed -- the census counts homes by class, while the
    per-epoch delta review compares them by full identity -- but they are two
    presentations of one decision, never two decisions.  Splitting them let a
    cohort or slot swap read as "same class, nothing changed" in one place while
    being a different home in the other.
    """
    if entry.projection_ref is not None:
        payload = entry.projection_ref.model_dump(exclude_none=True)
        kind = payload.pop("projection_kind")
        arguments = ",".join(f"{name}={value}" for name, value in sorted(payload.items()))
        return SemanticHome(review_class=f"projection:{kind}", identity=f"projection:{kind}({arguments})")
    if entry.producer_key is not None:
        return SemanticHome(review_class="producer", identity=f"producer:{entry.producer_key.value}")
    if entry.casilla_id is not None:
        return SemanticHome(review_class=entry.kind.value, identity=f"casilla:{entry.casilla_id}")
    if entry.computed_key is not None:
        return SemanticHome(review_class=entry.kind.value, identity=f"computed:{entry.computed_key.value}")
    record = entry.anchor.record_identity
    if entry.literal is not None:
        return SemanticHome(review_class=entry.kind.value, identity=f"literal:{entry.literal!r}@{record}")
    # Structural homes carry no payload to name them apart, so they are
    # qualified by their record and collide within it by design; their
    # cardinality is the census totals' job, not the identity's.
    return SemanticHome(review_class=entry.kind.value, identity=f"{entry.kind.value}@{record}")
