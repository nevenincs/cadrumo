"""Fixed-width placement validation for export records: contiguity and coverage.

The third member of the slot-geometry family, and the one that asks the question
the other two cannot. The byte-range check in
:mod:`cadrumo.domain.calculations.registry.export` asks whether two fields claim
the same positions, and
:func:`~.validate_export_field_widths.validate_draft_field_slot_width` asks
whether the positions one field claims can hold what it supplies. Neither asks
whether the record's declarations, taken together, account for every position
from the first onwards. A record can be free of overlaps and free of width
contradictions and still leave a hole nobody writes.

The rule, per record, over every position-claiming declaration sorted by
position:

    GAP                  ``end < next offset``   positions nobody writes
    OVERLAP              ``end > next offset``   positions written twice
    RECORD_STARTS_LATE   first offset > 1        the record's head is unclaimed

Both sources of a claim are the record's own layout
-----------------------------------------------------

A record's positions come from two declaration sites, and reading only the first
inverts the result. The obvious site is the record's inline
``ExportFieldDefinition`` rows. The second is the fixed export selector of every
binding naming the record's ``binding_record``: those materialise into the
record at export. Modelo 720 is the extreme case -- its ``type_1`` record
declares exactly ONE inline field, a reserved tail at position 181, while its
first 180 positions come from thirteen binding selectors beginning with
``tipo-de-registro`` at position 1 length 1. Judged on inline fields alone it
looks like a record whose first 180 positions are unwritten; judged on both, it
is contiguous from position 1. Measured across the corpus, including the binding
spans takes the 32 binding-derived records from 2 late starts and 52 gaps down
to 0 and 21. :func:`binding_export_spans` builds that index once per revision.

Why one refuses and the others advise
-------------------------------------

An OVERLAP is a REFUSAL. Two declarations claiming one position is never
legitimate under any record design: whichever renders second silently destroys
the other's datum, and no AEAT design asks for that. The live corpus carries
none under any grouping, so the refusal is wired with nothing to grandfather.

A GAP and a RECORD_STARTS_LATE are ADVISORIES, and are reported as two kinds
rather than one because a ruling on a hole in the middle of a record is not a
ruling on an unclaimed head. The reading that makes either a defect is the
project's own and is strong: AEAT declares a fixed-width record's whole byte
extent and the file carries every byte of it, so an unclaimed position is a
datum the application can never write, emitted as fill behind a structurally
valid digest. The registry has no record-length or trailer declaration to soften
it -- a record's extent is exactly the extent its declarations cover -- and a
deliberately empty span is declared, not omitted, as a
:attr:`~cadrumo.domain.calculations.export_field_kind.CasillaFieldKind.FILLER`
field carrying its own ``offset`` and ``length``, so a filler CLOSES a span
rather than excusing one.

What holds the promotion back is the authored corpus, not the argument: a live
read reports 115 gaps and 0 late starts across the loaded layouts, concentrated
in hand-authored envelope-header and page records. Many sit between spans AEAT
marks for itself, and whether the design intends those positions to be authored
or deliberately left to the administration is a question about the designs,
which this check does not read. Refusing them now would refuse the shipped
registry on a reading no source document has been checked against. So they are
REPORTED under their own names by :func:`export_record_placement_advisories` and
promoted once the designs have ruled -- not dropped, and not counted as clean.

One casilla split across two consecutive fields is coverage-complete and passes.
Modelo 296's 2024 casilla 03 is the worked case: an integer part at 160 length 13
followed by its fractional digits at 173 length 2. The split is a rendering
decision, and placement neither knows nor needs to know that the two slots belong
to one printed field.

WHAT THIS DOES NOT SEE, stated because a clean result invites over-reading: this
checks PLACEMENT, not FORMATTING. A field occupying exactly its positions with
the wrong justification, padding, data type, or value policy is invisible here.
Modelo 296's 2024 casilla 02 is the worked example -- 145 length 15 declared as
one pass-through text field where the design states sign, integer part and
decimal digits. Its placement is perfect and the question of whether it renders
correctly is untouched. A green placement result is not "the export is correct".

Run at registry build over every revision, so the refusal arrives when the
registry is validated rather than when a taxpayer's export happens to resolve
that one layout. It stays ONE authority: the export record validator calls it on
the record whose fields it already walks, so there is no second traversal.

See Also:
    :func:`~.validate_exports.validate_export_record`
        The registry-build export validator that invokes this check per record.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from types import MappingProxyType

from cadrumo.domain.calculations.registry.binding_selector_utils import (
    BindingFixedExportSelector,
    binding_export_selector,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportRecordDefinition

__all__ = [
    "FIRST_RECORD_POSITION",
    "NO_BINDING_SPANS",
    "PlacedSpan",
    "binding_export_spans",
    "export_record_placement_advisories",
    "record_placed_spans",
    "validate_export_record_field_placement",
]

#: The first position of every fixed-width export record. Offsets are one-based
#: throughout the registry, so a record whose leading span starts anywhere else
#: has left its opening positions unclaimed.
FIRST_RECORD_POSITION = 1

#: The empty binding-span index, for a caller checking a record that declares no
#: ``binding_record`` and therefore carries its whole layout inline.
NO_BINDING_SPANS: Mapping[str, tuple[PlacedSpan, ...]] = MappingProxyType[str, tuple["PlacedSpan", ...]]({})


@dataclass(frozen=True, slots=True, order=True)
class PlacedSpan:
    """One contiguous run of positions a single declaration claims.

    Carries where the claim came from, because the two sources are declared in
    different places and an advisory naming only a position is not actionable:
    ``origin`` is an export field id, or a binding id when the positions come
    from that binding's fixed export selector.
    """

    offset: int
    length: int
    origin: str

    @property
    def end(self) -> int:
        """Return the position one past the last this span claims."""
        return self.offset + self.length


def binding_export_spans(revision: ModeloRevision) -> Mapping[str, tuple[PlacedSpan, ...]]:
    """Index, per binding-record name, the positions bindings place into that record.

    Built once per revision so the placement check stays a single pass over the
    records rather than a per-record scan of every binding. A selector that does
    not resolve is skipped: that is the binding validator's refusal to raise,
    not this check's, and duplicating it here would report one defect twice
    under two names.

    Args:
        revision: The revision whose bindings are indexed.
    """
    spans: defaultdict[str, list[PlacedSpan]] = defaultdict(list)
    for binding in revision.bindings:
        try:
            selector = binding_export_selector(binding, revision=revision)
        except RegistryValidationError:
            continue
        if isinstance(selector, BindingFixedExportSelector):
            spans[selector.record].append(PlacedSpan(selector.offset, selector.length, str(binding.id)))
    return {record: tuple(sorted(record_spans)) for record, record_spans in spans.items()}


def validate_export_record_field_placement(
    *,
    prefix: str,
    record: ExportRecordDefinition,
    binding_spans: Mapping[str, tuple[PlacedSpan, ...]] = NO_BINDING_SPANS,
) -> list[str]:
    """Return placement REFUSALS for one export record.

    Refusals are the overlaps: positions two declarations both claim. The
    unclaimed-position population travels under its own names through
    :func:`export_record_placement_advisories`, which walks the same ordering.

    Args:
        prefix: Diagnostic prefix naming the modelo and revision under validation.
        record: The record whose placed spans are checked for double claims.
        binding_spans: Per-binding-record index from :func:`binding_export_spans`.
            Omitted means the record's inline fields are its whole layout, which
            holds for every record declaring no ``binding_record``.
    """
    return [
        _overlap_failure(prefix=prefix, record=record, previous=previous, following=following)
        for previous, following in pairwise(record_placed_spans(record, binding_spans))
        if previous.end > following.offset
    ]


def export_record_placement_advisories(
    *,
    prefix: str,
    record: ExportRecordDefinition,
    binding_spans: Mapping[str, tuple[PlacedSpan, ...]] = NO_BINDING_SPANS,
) -> tuple[str, ...]:
    """Return one advisory per span of positions this record leaves unclaimed.

    Two kinds, reported distinctly because they are unlike defects and a ruling
    on one need not be a ruling on the other. ``RECORD_STARTS_LATE`` says the
    record's earliest claimed position is not 1, leaving its head unclaimed --
    and the head is where AEAT puts the tipo-de-registro and modelo markers a
    parser keys on. ``GAP`` says positions between two claimed spans are claimed
    by nothing, a hole in the middle of an otherwise placed record.

    Args:
        prefix: Diagnostic prefix naming the modelo and revision under validation.
        record: The record whose placed spans are checked for contiguity.
        binding_spans: Per-binding-record index from :func:`binding_export_spans`.
    """
    placed = record_placed_spans(record, binding_spans)
    if not placed:
        return ()
    return (
        *_late_start_advisory(prefix=prefix, record=record, first=placed[0]),
        *(
            _gap_advisory(prefix=prefix, record=record, previous=previous, following=following)
            for previous, following in pairwise(placed)
            if previous.end < following.offset
        ),
    )


def record_placed_spans(
    record: ExportRecordDefinition,
    binding_spans: Mapping[str, tuple[PlacedSpan, ...]] = NO_BINDING_SPANS,
) -> tuple[PlacedSpan, ...]:
    """Return every run of positions the record claims, in position order.

    Public because a caller counting what the check walked must count the same
    thing the check walks. A census that reported only inline fields beside
    findings drawn from both sources would carry a denominator that does not
    belong to its numerator.

    An inline field declaring both ``offset`` and ``length`` holds positions;
    one declaring neither is logical-only; one declaring exactly half of the
    pair is refused by the layout-resolution range check that owns that
    contradiction, and is skipped here rather than reported a second time under
    a different name.
    """
    inline = tuple(
        PlacedSpan(field.offset, field.length, str(field.id))
        for field in record.fields
        if field.offset is not None and field.length is not None
    )
    bound = () if record.binding_record is None else binding_spans.get(record.binding_record, ())
    return tuple(sorted((*inline, *bound)))


def _late_start_advisory(
    *,
    prefix: str,
    record: ExportRecordDefinition,
    first: PlacedSpan,
) -> tuple[str, ...]:
    """Report the positions a record leaves unclaimed before its earliest span."""
    if first.offset == FIRST_RECORD_POSITION:
        return ()
    return (
        f"{prefix}: export record {record.id!r} RECORD_STARTS_LATE: positions "
        f"{FIRST_RECORD_POSITION}-{first.offset - 1} are claimed by nothing before {first.origin!r} "
        f"at position {first.offset}",
    )


def _gap_advisory(
    *,
    prefix: str,
    record: ExportRecordDefinition,
    previous: PlacedSpan,
    following: PlacedSpan,
) -> str:
    """Report the positions left unclaimed between two adjacent placed spans."""
    return (
        f"{prefix}: export record {record.id!r} GAP: {previous.origin!r} ends at position "
        f"{previous.end - 1} and {following.origin!r} starts at position {following.offset}, "
        f"leaving positions {previous.end}-{following.offset - 1} unwritten"
    )


def _overlap_failure(
    *,
    prefix: str,
    record: ExportRecordDefinition,
    previous: PlacedSpan,
    following: PlacedSpan,
) -> str:
    """Refuse the positions two adjacent placed spans both claim."""
    doubly_written_end = min(previous.end, following.end) - 1
    return (
        f"{prefix}: export record {record.id!r} OVERLAP: {previous.origin!r} ends at position "
        f"{previous.end - 1} and {following.origin!r} starts at position {following.offset}, "
        f"so positions {following.offset}-{doubly_written_end} are written twice"
    )
