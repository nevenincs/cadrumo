"""Attribute a party's address values by the block of the document they sit in.

The structural answer to party attribution, for every document whose layout can
carry it. The model's job does not change and the prompt does not grow: it
copies values and quotes role evidence for the two identity fields, exactly as
before. CODE attributes, which is where every other attribution in this design
already lives.

**Two layouts are partitioned, because real documents print both.** A STACKED
header states one heading per line and its region runs to the next heading; that
is :func:`_regions`. A TWO-COLUMN header -- issuer left, recipient right -- is
emitted by a reading-order text extractor as ONE line carrying both parties, and
it was for a long time the measured reason no real document could be partitioned
at all. It is now segmented by :func:`_side_by_side_regions`, which reads the
column boundary off the printed gutter between the two headings and cuts the
following lines at the same boundary, so each party gets only its own column.

**Neither path guesses.** A line that does not present exactly one column per
party -- no gutter where the boundary is, or content running across it --
contributes to no region at all. Values printed only on such lines stay
unresolved, which keeps the unverified-attribution stamp and the operator
advisory on exactly the part of the document that could not be separated. See
:func:`~application.ledger.party_attribution.stamp_unverified_party_attribution`.
The failure direction stays safe: unresolved keeps the warning.

**The mechanism is containment, never proximity.** A party's role evidence is a
printed heading the reader copied -- ``FACTURAR A``, ``Verkaufer``, the label a
NIF sits under -- and it is already checked to occur in the document. Those
headings partition the transcription into regions, and a value belongs to the
party whose region contains it. A nearest-neighbour or reading-order-distance
rule would be inference dressed as determinism: it would answer confidently on
a two-column layout where the nearest heading belongs to the other party.

**Segmentation is by line and by printed gutter, never by blank line.** Measured
against the real evidence corpus, not assumed: every text-layer transcription in
it carries zero blank lines, because a PDF text extractor emits reading-order
lines and the visual gap between two address blocks leaves no character behind.
A blank-line-delimited implementation would have been correct-looking and dead
-- never firing on any real document, which is the same failure as evidence no
resolver consumes, in mirror image. The horizontal gap between two columns does
leave characters behind, a run of two or more spaces, and that run is the only
thing the two-column path reads.

**Three outcomes, and the third is the honest one.** A value found in exactly
its own party's region is ATTRIBUTED. A value found only in the OTHER party's
region is CONTRADICTED -- the transposition this whole apparatus exists for, and
the one case where refusing is right. Everything else is UNRESOLVED: no role
evidence to segment on, a value in both regions, a value in neither. Unresolved
keeps the unverified-attribution stamp and the operator advisory rather than inventing a
verdict, because a document that cannot answer the question has not answered it.

The zugferd specimen in the corpus is why the both-regions case is not
theoretical: it prints the supplier's postal code a second time in a remarks
block below the customer heading, so that value genuinely occurs on both sides
and no containment rule can honestly resolve it.

See Also:
    :func:`~application.ledger.party_attribution.stamp_unverified_party_attribution`
        The unverified-attribution stamp this resolution clears or leaves standing,
        and which on a real prose document it leaves standing.
    :func:`~application.ledger.grounding_anchor.printed_excerpt_occurs_in_text`
        The one authority for whether a region prints a given form.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.models import STRICT_FROZEN_CONFIG
from .grounding_anchor import printed_excerpt_occurs_in_text
from .party_attribution import PARTY_ATTRIBUTED_ADDRESS_FIELDS, party_addresses

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .document_transcription import DocumentTranscription
    from .invoice_draft_records import DraftDiscrepancyFinding, FieldProvenance, InvoiceDraft

__all__ = [
    "PartyAttributionOutcome",
    "PartyColocationResolution",
    "party_attribution_findings",
    "party_regions",
    "resolve_party_attribution_by_colocation",
]


class PartyAttributionOutcome(StrEnum):
    """What co-location settled about one address value's party.

    Attributes:
        ATTRIBUTED: The value occurs inside its own party's region and not the
            other's. The reader's assignment is confirmed by the document's own
            layout, so the unverified-attribution stamp is cleared.
        CONTRADICTED: The value occurs only inside the OTHER party's region.
            The reader filed it under the wrong party -- the transposition the
            territory axis is silently wrong on -- and it is refused rather than
            corrected, because swapping it here would substitute one unverified
            assignment for another.
        UNRESOLVED: The document did not answer. No role evidence to segment on,
            the value printed on both sides, or printed on neither. The
            stamp stays and the operator keeps the advisory.
    """

    ATTRIBUTED = "attributed"
    CONTRADICTED = "contradicted"
    UNRESOLVED = "unresolved"


class PartyColocationResolution(BaseModel):
    """What co-location settled for every address value on one draft.

    Attributes:
        outcomes: Per draft field name. Only the per-party address fields the
            establishment ladder consumes appear; a field the draft did not
            carry a value for is absent rather than ``UNRESOLVED``, because
            there was no attribution to make.
    """

    model_config = STRICT_FROZEN_CONFIG

    outcomes: dict[str, PartyAttributionOutcome] = Field(default_factory=dict)

    @property
    def contradicted_fields(self) -> tuple[str, ...]:
        """Return the fields the document filed under the wrong party."""
        return tuple(
            field for field, outcome in self.outcomes.items() if outcome is PartyAttributionOutcome.CONTRADICTED
        )


_NO_RESOLUTION: Final = PartyColocationResolution()


def _role_evidence_by_field(envelopes: tuple[FieldProvenance, ...]) -> dict[str, str]:
    """Return the role-evidence excerpt each identity field carries, if any."""
    return {
        envelope.field: envelope.role_evidence
        for envelope in envelopes
        if envelope.role_evidence is not None and envelope.role_evidence.strip()
    }


def _region_start(excerpt: str, *, lines: list[str]) -> int | None:
    """Return the index of the first line printing *excerpt*, or ``None``.

    Matched through the shared printed-token search rather than a bare ``in``,
    so a heading is recognised on the same Unicode and whitespace terms the
    anchor check uses. A heading the document does not print anchors nothing and
    yields ``None``, which collapses the whole resolution to unresolved -- the
    fail-safe direction.
    """
    for index, line in enumerate(lines):
        if printed_excerpt_occurs_in_text(excerpt, text=line):
            return index
    return None


def _regions(
    *,
    lines: list[str],
    anchors: dict[str, int],
) -> dict[str, tuple[int, int]]:
    """Return each party's half-open line span, bounded by the next party's anchor.

    A party's region runs from its own heading to the next party heading in
    reading order, and the last one runs to the end of the document. That is the
    whole segmentation: the headings are the only boundaries the document
    actually states, and inventing others -- a fixed line budget, an indentation
    rule -- would be layout inference the record forbids here.

    A party whose region would be empty is dropped rather than kept as a
    zero-width span, so two headings printed on one line cannot produce a region
    that matches nothing and reads as a clean negative. Keeping such a span
    would attribute one party's values to the other, which is the transposition
    this module exists to refuse.

    **This function answers the VERTICAL layout only, by design.** A two-column
    header reaches the resolver as one line carrying both parties, so both
    anchors resolve to the same index and no vertical span separates them.
    That layout is segmented horizontally instead, by
    :func:`_side_by_side_regions`, and :func:`party_regions` routes between the
    two on whether the anchors share a line. Widening this function to cover it
    would make one primitive answer two different questions about the page.
    """
    ordered = sorted(anchors.items(), key=lambda item: item[1])
    spans: dict[str, tuple[int, int]] = {}
    for position, (role, start) in enumerate(ordered):
        end = ordered[position + 1][1] if position + 1 < len(ordered) else len(lines)
        if end > start:
            spans[role] = (start, end)
    return spans


#: A run of two or more spaces INSIDE a line: what a reading-order text
#: extractor leaves behind where a document printed two columns side by side.
#: A single space is ordinary word spacing and is never a column boundary, which
#: is what keeps ``EMISOR DESTINATARIO`` -- a header whose gap the extractor did
#: not preserve -- unsegmentable rather than split on a guess.
_COLUMN_GUTTER: Final = re.compile(r"[^\S\n]{2,}")


def _columns_on(line: str) -> tuple[str, ...]:
    """Return *line* cut at its printed gutters, or an empty tuple for a blank line.

    Leading and trailing whitespace is trimmed before the cut rather than read as
    a gutter. An indented line is one column that was indented, not an empty
    column followed by a full one, and reading it as the latter would invent a
    party's silence out of the document's margin.
    """
    body = line.strip()
    if not body:
        return ()
    columns: list[str] = []
    cut = 0
    for gutter in _COLUMN_GUTTER.finditer(body):
        columns.append(body[cut : gutter.start()])
        cut = gutter.end()
    columns.append(body[cut:])
    return tuple(columns)


def _column_order(line: str, *, excerpts: Mapping[str, str]) -> tuple[str, ...] | None:
    """Return the roles in printed column order, or ``None`` when the line is unusable.

    The whole boundary derivation. Every role's heading must sit in its own
    column of the same line, which is what makes the gutter between them a
    boundary the DOCUMENT states rather than one this function chose. Anything
    else -- a heading found in two columns, two headings sharing one column, a
    third column between them, a column carrying no heading at all -- returns
    ``None`` and leaves the whole page unpartitioned, because a boundary that
    cannot be located cannot be used to attribute anything.
    """
    columns = _columns_on(line)
    if len(columns) != len(excerpts):
        return None
    placed: dict[int, str] = {}
    for role, excerpt in excerpts.items():
        located = [
            index for index, column in enumerate(columns) if printed_excerpt_occurs_in_text(excerpt, text=column)
        ]
        if len(located) != 1 or located[0] in placed:
            return None
        placed[located[0]] = role
    return tuple(placed[index] for index in sorted(placed))


def _side_by_side_regions(
    *,
    lines: list[str],
    header: int,
    excerpts: Mapping[str, str],
) -> dict[str, str]:
    """Return each party's region text for a header printing every party on one line.

    The two-column answer. The header line's own gutters fix how many columns the
    page has and which party owns each one; every line from the header onwards is
    cut the same way, and a line's Nth column joins the Nth party's region.

    **A line that does not present exactly one column per party contributes to
    NOBODY.** No gutter where the boundary is, a value running across it, an
    extra column, a full-width footer: each of those is a line the document did
    not separate, and assigning it to the party whose column it happens to start
    under would be proximity dressed as containment -- the inference this module
    refuses everywhere else. Dropping it costs only resolution: the values
    printed there stay unresolved and keep their stamp and advisory.

    Args:
        lines: The transcription's lines, in reading order.
        header: Index of the line carrying every party's heading.
        excerpts: Each party's role-evidence heading, keyed by role.

    Returns:
        Region text per role, or an empty mapping when the header states no
        usable column boundary or a party's column stayed empty.
    """
    order = _column_order(lines[header], excerpts=excerpts)
    if order is None:
        return {}
    columns: dict[str, list[str]] = {role: [] for role in order}
    for line in lines[header:]:
        cut = _columns_on(line)
        if len(cut) != len(order):
            continue
        for role, column in zip(order, cut, strict=True):
            columns[role].append(column)
    regions = {role: "\n".join(text) for role, text in columns.items() if text}
    return regions if len(regions) == len(order) else {}


def _region_text(lines: list[str], span: tuple[int, int]) -> str:
    start, end = span
    return "\n".join(lines[start:end])


def resolve_party_attribution_by_colocation(
    *,
    draft: InvoiceDraft,
    transcription: DocumentTranscription,
) -> PartyColocationResolution:
    """Return what the document's own layout settles about each address value's party.

    Deterministic and side-effect free. Reads the draft and the transcription and
    returns a verdict per enrolled address field; it never rewrites a draft value
    and never re-assigns one to the other party.

    **It does not correct a transposition, it reports one.** Moving a value to
    the region that contains it would replace the reader's unverified assignment
    with this function's, and the two rest on the same single reading of one
    document. A contradiction is surfaced for a person to settle.

    Args:
        draft: The read draft, carrying each party's identity role evidence on
            its provenance envelopes.
        transcription: The independently produced document text, line structure
            intact -- which is why it is taken rather than a normalised string.

    Returns:
        :class:`PartyColocationResolution`: an outcome per enrolled address field
        the draft carried a value for. Empty when the document states no usable
        party heading, or states them in a layout whose columns it does not
        separate, which leaves every value on the unverified-attribution stamp.
    """
    region_text = party_regions(draft=draft, transcription=transcription)
    if len(region_text) < 2:
        return _NO_RESOLUTION

    outcomes: dict[str, PartyAttributionOutcome] = {}
    for party in party_addresses():
        own = region_text.get(party.role)
        others = [text for role, text in region_text.items() if role != party.role]
        if own is None:
            continue
        for field in (party.postal_field, party.country_field, party.country_code_field):
            if field not in PARTY_ATTRIBUTED_ADDRESS_FIELDS:
                continue
            value = getattr(draft, field, None)
            if not isinstance(value, str) or not value.strip():
                continue
            outcomes[field] = _outcome_for_value(value, own=own, others=others)
    return PartyColocationResolution(outcomes=outcomes)


def _outcome_for_value(value: str, *, own: str, others: list[str]) -> PartyAttributionOutcome:
    """Return the outcome for one value against its own region and the others.

    The both-sides case is UNRESOLVED rather than ATTRIBUTED, and that is the
    load-bearing choice. A value printed in both parties' regions is evidence
    that containment cannot separate them on this document -- reading the
    presence in its own region as confirmation would let any repeated figure
    launder itself into an attributed one.
    """
    in_own = printed_excerpt_occurs_in_text(value, text=own)
    in_other = any(printed_excerpt_occurs_in_text(value, text=text) for text in others)
    if in_own and not in_other:
        return PartyAttributionOutcome.ATTRIBUTED
    if in_other and not in_own:
        return PartyAttributionOutcome.CONTRADICTED
    return PartyAttributionOutcome.UNRESOLVED


def party_attribution_findings(
    resolution: PartyColocationResolution,
) -> tuple[DraftDiscrepancyFinding, ...]:
    """Return one blocking finding per value the document filed under the wrong party.

    The consuming half, without which the resolver would detect a transposition
    and drop it -- computed evidence nothing acts on, which is the failure this
    whole design keeps arriving back at. A contradiction that reaches no operator
    is indistinguishable from a check that never ran.

    Only CONTRADICTED yields a finding. An unresolved value stays on the advisory
    stamp: firing a blocker on every document whose layout cannot be separated
    would refuse the ordinary case, which is the alert fatigue that makes an
    alert worthless on the case that matters.

    Args:
        resolution: What co-location settled for the draft.

    Returns:
        The findings, in field order. Empty when nothing was contradicted.
    """
    # Call-time import for the cycle-break reason the sibling checks use: the
    # draft module reaches the parsers and the reading package, so binding it at
    # module scope would make this leaf pay for all of it.
    from .invoice_draft_records import DraftDiscrepancyFinding

    return tuple(
        DraftDiscrepancyFinding(
            kind=DraftDiscrepancyKind.PARTY_ATTRIBUTION_CONTRADICTED,
            field=field,
            # Names the observable fact and not the inference. The operator is
            # told where the value was printed relative to the headings, which
            # is checkable against the page; telling them "the parties are
            # swapped" would assert a conclusion the document does not settle.
            detail=(
                f"the value in {field} is printed inside the other party's block on this document, "
                f"and not inside the block the reader assigned it to; the address blocks may have "
                f"been read the wrong way round, which would place both parties in the wrong IVA "
                f"territory"
            ),
        )
        for field in resolution.contradicted_fields
    )


def party_regions(
    *,
    draft: InvoiceDraft,
    transcription: DocumentTranscription,
) -> dict[str, str]:
    """Return each party's region text, keyed by role, or an empty mapping.

    The partition itself, exposed rather than kept private because a gate
    asserting only the outcomes cannot distinguish "the partition was right and
    the values landed in it" from "the partition collapsed and everything read
    unresolved". Both are green on an outcome assertion alone, and only one is
    the behaviour under test.

    **Both sides are required.** One heading partitions nothing: with a single
    anchor every value on the page falls inside its region by construction,
    which would attribute the other party's values to it. Fewer than two usable
    regions yields an empty mapping, and that is an honest unresolved case
    rather than an error.

    **The layout decides which segmentation runs, and the document states which
    layout it is.** Headings on different lines are a stacked header, segmented
    vertically by :func:`_regions`. Headings on the SAME line are a two-column
    header, segmented horizontally by :func:`_side_by_side_regions`. The choice
    is read off the anchor line indices, never guessed from the page's shape.

    Args:
        draft: The read draft, carrying identity role evidence on its envelopes.
        transcription: The document text with its line structure intact.

    Returns:
        Region text per party role, or an empty mapping when the document states
        no usable partition.
    """
    lines = transcription.text.split("\n")
    role_evidence = _role_evidence_by_field(draft.provenance)
    anchors: dict[str, int] = {}
    excerpts: dict[str, str] = {}
    for party in party_addresses():
        excerpt = role_evidence.get(party.tax_id_field)
        if excerpt is None:
            continue
        start = _region_start(excerpt, lines=lines)
        if start is not None:
            anchors[party.role] = start
            excerpts[party.role] = excerpt
    if len(anchors) < 2:
        return {}
    if len(set(anchors.values())) == 1:
        # Every heading on one line: the page separates its parties horizontally,
        # so the boundary is the printed gutter rather than the next heading.
        return _side_by_side_regions(lines=lines, header=next(iter(anchors.values())), excerpts=excerpts)
    spans = _regions(lines=lines, anchors=anchors)
    if len(spans) < 2:
        return {}
    return {role: _region_text(lines, span) for role, span in spans.items()}
