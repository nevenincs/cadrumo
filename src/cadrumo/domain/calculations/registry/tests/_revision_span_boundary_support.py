"""Revision-span boundary-evidence test support."""

from __future__ import annotations

import unicodedata
from bisect import bisect_right
from functools import cache
from itertools import pairwise
from pathlib import Path

from .....core.resources.bundled_data import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from ..schema import ModeloRevision
from ._revision_span_design_support import (
    _BOX_MARKER,
    _PDF_FLATTENED_SHEET,
    _RESERVED_FIELD,
    _claimed_years,
    _design_coverage_years,
    _design_fingerprint,
    _design_sheets,
    _designs_in_publication_order,
    _occupancy,
    _page_lengths,
    _parse_design,
)


@cache
def _corpus_path_by_source_ref() -> dict[str, str]:
    """Every source ref mapped to the corpus path it records, unparsed."""
    _modelos, catalogues = bundled_registry_tree()
    return {
        ref: str(entry.corpus_path) for ref, entry in catalogues.sources.items() if getattr(entry, "corpus_path", None)
    }


@cache
def _design_fingerprint_for_ref(ref: str) -> tuple[object, ...] | None:
    """The fingerprint of the design a source ref names, or ``None`` if it names none.

    Resolved lazily, one ref at a time. Fingerprinting PARSES the design, so
    building this for every catalogue source up front costs a full corpus read
    on a question only a handful of refs per revision ever ask.

    Fingerprint rather than file name, and that is what makes the match work.
    The corpus bundles some designs twice under names differing only by a
    truncated extension; :func:`_designs_in_publication_order` collapses those
    twins and keeps whichever sorts first, which is not necessarily the one the
    catalogue cites. Modelo 303's late 2024 design is exactly that: the
    catalogue names ``...-381-kb-xls.xlsx`` while the walk keeps its
    byte-identical ``...-381-kb-x.xlsx``. Comparing names fails on two files
    that are the same design; comparing the identity this module already uses to
    collapse twins does not.
    """
    corpus_path = _corpus_path_by_source_ref().get(ref)
    if corpus_path is None:
        return None
    resolved = bundled_path() / corpus_path
    if not resolved.is_file() or not _design_sheets(resolved):
        return None
    return _design_fingerprint(resolved)


def _cited_design_fingerprints(revision: ModeloRevision) -> set[tuple[object, ...]]:
    """The designs this revision's own source refs name, by fingerprint."""
    found = (_design_fingerprint_for_ref(str(ref)) for ref in revision.source_refs)
    return {fingerprint for fingerprint in found if fingerprint is not None}


def _mid_year_span(revision: ModeloRevision) -> int | None:
    """The year a revision sits WHOLLY inside while covering less than all of it.

    ``None`` for a revision that covers a full year, several years, or is
    open-ended -- those claim their years outright and every design in them.
    """
    valid_from, valid_to = revision.valid_from, revision.valid_to
    if valid_from is None or valid_to is None or valid_from.year != valid_to.year:
        return None
    covers_whole_year = (valid_from.month, valid_from.day) == (1, 1) and (valid_to.month, valid_to.day) == (12, 31)
    return None if covers_whole_year else valid_from.year


def _designs_claimed_by(modelo_id: str, revision: ModeloRevision) -> tuple[Path, ...]:
    """The designs a revision's span claims, in publication order.

    KEYED ON THE DESIGN FILE, NOT ON THE PARSED YEAR, and that is the whole point. The
    per-signal inventories this replaced each kept ONE design per year through a
    ``setdefault`` over a filename sort, so where AEAT split an ejercicio mid-course the
    second half was silently discarded and the boundary INSIDE that year could not be
    seen by any signal. Modelo 303 does it three times, in 2018, 2021 and 2024, and the
    mid-2024 boundary is inside the reachable filing window.

    One walk feeds all three signals, rather than each rebuilding its own inventory.
    Three separate walks is how they came to disagree about which designs existed: a
    year readable by one signal and not another entered one map and not the others, so
    the same boundary was keyed differently per signal and the evidence for it split
    across keys that never met.
    """
    ordered, _unorderable = _designs_in_publication_order(modelo_id)
    every_year = {year for path in ordered for year in _design_coverage_years(path)}
    claimed = _claimed_years(revision, every_year)
    within = tuple(path for path in ordered if set(_design_coverage_years(path)) & claimed)

    # A revision covering only PART of one year claims only the design it cites
    # for that year. AEAT splits an ejercicio mid-course by publishing two
    # designs with the same coverage year, so a year-keyed claim hands both to
    # each half -- and the halves then report a (2024, 2024) boundary they do
    # not span. Modelo 303's 2024 halves and modelo 490's 2022 halves are the
    # cases: each declares its own months in its id AND names one design in its
    # source refs, and the design filenames say the same thing
    # ("hasta-periodos-08-y-2t" beside "a-partir-de-periodos-09-y-3t").
    #
    # Deliberately narrow. A revision covering a whole year, several years, or
    # an open-ended span is untouched, so the genuine cross-year spans this gate
    # exists to find -- modelo 184, 200, 322 and 347 -- keep reporting. And the
    # narrowing applies only where the revision actually cites a design, so a
    # revision citing none claims its years outright as before.
    mid_year = _mid_year_span(revision)
    if mid_year is None:
        return within
    cited = _cited_design_fingerprints(revision)
    if not cited:
        return within
    kept = tuple(
        path
        for path in within
        if _design_fingerprint(path) in cited or mid_year not in set(_design_coverage_years(path))
    )
    return kept or within


def _box_set_evidence(before_boxes: dict[str, int], after_boxes: dict[str, int]) -> str | None:
    """Evidence that the box SET changed, whether or not anything moved.

    A SEPARATE SIGNAL from displacement, not a refinement of it. The displacement check
    iterates the boxes two designs SHARE, so a box present in one and absent in the
    other falls outside its loop entirely. That is not a lesser event: a box the later
    design declares and the earlier one does not cannot be declared at all under the
    earlier layout, and a box the earlier one declares and the later one drops is a
    value written into space the later design puts to another use.

    Measured on Modelo 390, where the whole class was invisible: 2015 to 2016 adds six
    boxes and 2016 to 2017 removes twenty, both with ZERO movement, no readable
    page-length difference and no occupancy transition, so no signal in this module
    reported either boundary. Adding this one took that revision's verdict from six
    re-layouts to eight.

    The blindness survived because it is MASKED wherever membership changes alongside
    movement: the 2017 to 2018 boundary drops seventy-two boxes, and the displacement
    check reports that boundary anyway on its ninety-seven moved boxes, so a reader
    spot-checking the signal against that pair sees a membership change duly reported
    and concludes the set is compared.

    Extracted as a named helper rather than inlined so the signal has a seam a mutation
    can suppress on its own, leaving every other signal running. A mutation that has to
    break the whole comparison proves the module can fail, not that this signal works.
    """
    added = sorted(set(after_boxes) - set(before_boxes), key=int)
    removed = sorted(set(before_boxes) - set(after_boxes), key=int)
    if not added and not removed:
        return None
    parts = []
    if added:
        parts.append(f"{len(added)} added (e.g. {', '.join(f'[{box}]' for box in added[:3])})")
    if removed:
        parts.append(f"{len(removed)} removed (e.g. {', '.join(f'[{box}]' for box in removed[:3])})")
    return (
        f"box SET changed: {' and '.join(parts)} -- a box only one side declares cannot be carried "
        "by the other layout at all, which no displacement, length or digest check sees"
    )


def _position_content(path: Path) -> dict[tuple[str, int, int], str]:
    """``(sheet, offset, length) -> normalised description`` for EVERY field, boxed or not.

    Unlike :func:`_unnumbered_labels`, NOT filtered to box-token-free slots -- every
    field's declared content at its position. This is what lets
    :func:`_position_set_evidence` see a field added or removed where no box number
    exists to key membership on at all, closing a class of blindness measured
    directly: 62 of 174 bundled designs carry ZERO bracketed box numbers anywhere
    (29 modelos, including 111, 180, 232, 349, 360, 369 and 720 -- three of which
    can already file today), so :func:`_box_set_evidence`'s key never exists for
    them, not merely loses precision on them.

    ABSTAINS on a flattened PDF parse, for the same reason :func:`_unnumbered_labels`
    does: the synthetic single-sheet shape makes ``(sheet, offset, length)`` collide
    across unrelated pages.
    """
    sheets = _design_sheets(path)
    if len(sheets) == 1 and sheets[0].name == _PDF_FLATTENED_SHEET:
        return {}
    table: dict[tuple[str, int, int], str] = {}
    for sheet in sheets:
        for field in sheet.fields:
            table.setdefault((sheet.name, field.offset, field.length), " ".join(field.description.split()))
    return table


def _position_set_evidence(earlier: Path, later: Path) -> str | None:
    """SIXTH SIGNAL: a field added or removed at a position, independent of box number.

    Generalises :func:`_box_set_evidence`'s membership idea past its box-number key,
    the same relationship the box-SET signal has to the displacement check: a
    SEPARATE signal, not a refinement, because a field one side declares and the
    other does not falls outside a shared-key loop entirely. The box-SET signal is
    structurally blind wherever no bracketed box number exists to key on at all --
    a bracket-free field cannot be a member of a box-number SET, period, not merely
    an imprecisely-tracked one.

    KEYED ON ``(sheet, offset, length)``, NEVER ON DESCRIPTION TEXT, so a genuine
    content CHANGE at an UNMOVED position is deliberately NOT reported here -- that
    is :func:`_description_flip_evidence`'s job, including its no-separable-leaf
    branch. This signal reports only when a POSITION exists in one design and not
    the other: a field the later design declares that the earlier one has nowhere
    to put, or one the earlier design declares that the later one no longer
    reserves space for. The two signals are complementary rather than redundant --
    each answers a question the other structurally cannot.

    RESERVED POSITIONS ARE EXCLUDED, and this exclusion is measured, not assumed.
    Modelo 202's two 2019-era designs (the May 2020 and September 2019 updates)
    declare the identical reserved byte range 516-689 -- one as a single 173-byte
    ``Reservado para la Administracion`` field, the other split into a 1-byte field
    at 516 and a 172-byte field at 517. A first version of this signal, without the
    exclusion, reported that as one field added and two removed: a false positive
    from re-partitioning empty space, not a real layout change. A reserved slot
    changing SHAPE while staying reserved on both sides is not a field appearing or
    disappearing; a reserved slot changing OCCUPANCY (becoming real, or a real slot
    becoming reserved) is the occupancy signal's own job and stays there rather than
    being double-reported here.
    """
    before, after = _position_content(earlier), _position_content(later)
    added = sorted(key for key in set(after) - set(before) if not _RESERVED_FIELD.search(after[key]))
    removed = sorted(key for key in set(before) - set(after) if not _RESERVED_FIELD.search(before[key]))
    if not added and not removed:
        return None
    parts = []
    if added:
        parts.append(
            f"{len(added)} added (e.g. {', '.join(f'{sheet} offset {offset}' for sheet, offset, _l in added[:3])})"
        )
    if removed:
        parts.append(
            f"{len(removed)} removed (e.g. {', '.join(f'{sheet} offset {offset}' for sheet, offset, _l in removed[:3])})"
        )
    return (
        f"field SET changed at these positions: {' and '.join(parts)} -- independent of box number, "
        "so this catches a field added or removed where no bracket exists to key membership on"
    )


#: Marks a boundary whose ONLY evidence is the description-keyed pass, which is the
#: least precise signal here. Used by the verdict text and by the review assertion.
_DESCRIPTION_ONLY = "DESCRIPTION-KEYED PASS ONLY"

#: AEAT joins the containing block to a field's own name with this separator, so the
#: final segment is the slot's own label and everything before it is context.
_LABEL_SEPARATOR = " - "


def _unnumbered_labels(path: Path) -> dict[tuple[str, int, int], str]:
    """``(sheet, offset, length) -> description`` for slots carrying NO box number.

    ABSTAINS on a flattened PDF parse by returning nothing. The PDF backend collapses a
    document to one synthetic sheet, so ``(sheet, offset, length)`` stops identifying a
    slot and starts colliding across pages -- measured, a corpus-wide run without this
    abstention returned 15366 "changes" that were overwhelmingly unrelated fields
    compared against each other.
    """
    sheets = _design_sheets(path)
    if len(sheets) == 1 and sheets[0].name == _PDF_FLATTENED_SHEET:
        return {}
    table: dict[tuple[str, int, int], str] = {}
    for sheet in sheets:
        for field in sheet.fields:
            if _BOX_MARKER.findall(field.description):
                continue
            table.setdefault((sheet.name, field.offset, field.length), " ".join(field.description.split()))
    return table


def _description_flip_evidence(earlier: Path, later: Path) -> str | None:
    """FIFTH SIGNAL: an UNNUMBERED slot whose declared meaning changes at a fixed position.

    The box-number key is structurally blind to a slot carrying no bracketed number, and
    two such slots on Modelo 303 do change meaning between the 2024 halves -- a one-byte
    flag and the reference beside it go from declaring a complementaria and its prior
    receipt to declaring an autoliquidacion rectificativa and its identifying receipt.
    Byte-valid, length-valid, digest-valid, and declaring something else.

    THE DISCRIMINATION, which is what makes this shippable. A text diff cannot tell a
    changed meaning from a reworded label, and the accepted sub-year record says so.
    AEAT writes these descriptions hierarchically, so this compares the FINAL segment: a
    changed leaf is the slot's own meaning, while an unchanged leaf under a changed
    prefix is the containing block being relabelled and is NOT reported. Validated
    against three hand-judged cases -- Modelo 390's ``Lorca`` becoming
    ``Reducciones (nota 2)`` at a fixed 17-byte slot is reported, Modelo 131 dropping La
    Palma from a one-byte deduction flag is reported, and Modelo 111's
    ``Identificacion. Ejercicio`` becoming ``Devengo. Ejercicio`` is correctly NOT, since
    only the heading above the field moved.

    WHERE IT CANNOT SEPARATE A LEAF, IT STILL ASSERTS -- as a WEAKER, DISTINCTLY MARKED
    finding, never as silence. A design carrying NO bracketed box numbers at all (an
    informative-return form, never a hierarchical ``Block - Field`` label) fails the
    leaf-separation test on every one of its changed slots, which is what silently
    discarded real divergence before this signal was fixed: Modelo 347's two boundaries
    each change dozens of unnumbered slots -- 38 of 41 shared, then 32 of 40 -- with EVERY
    ONE unseparable, so ``flipped`` stayed empty and the whole comparison returned
    ``None``, a "no boundary" verdict for a revision spanning a seventeen-year re-layout.
    That is not evidence of identity; it is the instrument declaring a limit and reporting
    silence instead of the limit. A design with no box tokens and no hierarchical labels is
    not thereby unexaminable -- position-content divergence at an unchanged offset and
    width is still real signal, it simply cannot be NAMED the way a separable leaf can.

    PRECISION, stated so the verdict is read correctly, for BOTH assertion shapes. On
    individual verdicts the separable-leaf pass runs roughly one false positive in three,
    and a measured example survives in the corpus: Modelo 303's 2014/2015 pair reports a
    leaf going from ``regimen simplificado`` to ``Regimen Simplificado (RS)``, which is a
    rewording. That costs nothing THERE because three other signals already name that
    boundary -- a false positive on an already-named boundary adds noise to evidence, not
    a wrong split. The unseparable-only shape is coarser still -- it can say THAT content
    at a position differs, never WHAT changed, so it cannot even apply the leaf-rewording
    filter -- which is the accepted trade for not discarding real divergence outright. The
    case that matters, for either shape, is a boundary this pass names ALONE, which the
    verdict marks so a reader knows it rests on the weakest instrument.

    Reserved transitions are excluded: those belong to the occupancy signal, and counting
    them here would double-report one event under two headings.
    """
    before, after = _unnumbered_labels(earlier), _unnumbered_labels(later)
    flipped: list[tuple[tuple[str, int, int], str, str]] = []
    unseparable = 0
    for slot in sorted(set(before) & set(after)):
        was, now = before[slot], after[slot]
        if _normalised(was) == _normalised(now):
            continue
        if _RESERVED_FIELD.search(was) or _RESERVED_FIELD.search(now):
            continue
        if _LABEL_SEPARATOR in was and _LABEL_SEPARATOR in now:
            leaf_was = was.rsplit(_LABEL_SEPARATOR, 1)[1]
            leaf_now = now.rsplit(_LABEL_SEPARATOR, 1)[1]
            if _normalised(leaf_was) == _normalised(leaf_now):
                continue
            flipped.append((slot, leaf_was, leaf_now))
        else:
            unseparable += 1
    if flipped:
        shown = "; ".join(
            f"{sheet} offset {offset} len {length}: {was!r} -> {now!r}"
            for (sheet, offset, length), was, now in flipped[:3]
        )
        note = (
            f"{len(flipped)} unnumbered slot(s) re-described at an unchanged position and width "
            f"(e.g. {shown}) -- the box-number key cannot see these, and no offset, length or "
            "digest check detects a slot that keeps its place while declaring something else"
        )
        if unseparable:
            note += (
                f" [plus {unseparable} slot(s) whose text changed but carries no separable leaf, "
                "NOT individually named -- see the instrument-limit note if this is the only signal]"
            )
        return note
    if unseparable:
        # No separable leaf anywhere, so nothing can be individually named -- but the
        # position-content divergence is still real, measured, and must not silently
        # collapse to "no boundary". Deliberately reuses the "unnumbered slot(s)
        # re-described" phrase so the same DESCRIPTION-ONLY marking in the callers below
        # covers this shape without a second matcher.
        return (
            f"{unseparable} unnumbered slot(s) re-described at an unchanged position and width, "
            "with NO separable leaf to name what changed -- INSTRUMENT LIMIT: this is the "
            "weakest signal in this module, reporting THAT content differs at a fixed position "
            "without being able to say WHAT, most often because the design carries no "
            "hierarchical Block-Field labels at all (an informative-return form); real "
            "divergence still, never proof of identity"
        )
    return None


def _normalised(text: str) -> str:
    """Case- and diacritic-insensitive form, so an accent or casing fix is not a flip."""
    folded = unicodedata.normalize("NFKD", " ".join(text.split()).casefold())
    return "".join(char for char in folded if not unicodedata.combining(char))


def _boundary_label(earlier: Path, later: Path) -> tuple[int, int]:
    """``(left year, right year)``; the two are EQUAL for a mid-course split."""
    return max(_design_coverage_years(earlier)), min(_design_coverage_years(later))


def _boundaries_for(modelo_id: str, revision: ModeloRevision) -> dict[tuple[int, int], list[str]]:
    """Every re-layout boundary inside one revision's span, keyed year-pair to evidence.

    Both signals contribute to ONE verdict rather than reporting separately,
    because they see overlapping-but-different boundary sets and a reader
    unioning two lists by hand will miss the ones only the weaker signal saw.

    A key whose two years are EQUAL is a mid-course split, where AEAT re-laid out a
    form partway through one ejercicio.
    """
    boundaries: dict[tuple[int, int], list[str]] = {}
    claimed_designs = _designs_claimed_by(modelo_id, revision)

    for earlier, later in pairwise(claimed_designs):
        evidence = _compare_design_pair(earlier, later)
        if evidence:
            boundaries[_boundary_label(earlier, later)] = evidence

    return boundaries


def _compare_design_pair(earlier: Path, later: Path) -> list[str]:
    """Every signal's evidence that two designs diverge; empty when they agree.

    THE ONE INSTRUMENT this module compares designs with, extracted so it has
    exactly one caller-independent body. :func:`_boundaries_for` calls this once
    per ADJACENT pair inside a revision's own claimed span, to prove no
    re-layout crosses the span. The single-year neighbour check
    (:func:`_neighbour_divergence`) calls the SAME function once against the
    immediately adjacent revision's design, to prove a single-year split was
    warranted. Two questions, one comparator -- never a second, parallel diff.
    """
    evidence: list[str] = []
    before_lengths, after_lengths = _page_lengths(earlier), _page_lengths(later)

    def _record_count_delta(
        before: tuple[str, ...] = before_lengths, after: tuple[str, ...] = after_lengths
    ) -> str | None:
        """``'9 -> 10 records'`` when the design's record SET changed, else None."""
        if not before or not after or len(before) == len(after):
            return None
        return f"{len(before)} -> {len(after)} records"

    before_boxes, after_boxes = _parse_design(earlier), _parse_design(later)
    shared = set(before_boxes) & set(after_boxes)
    moved = sorted(box for box in shared if before_boxes[box] != after_boxes[box])
    if moved:
        sample = ", ".join(f"[{box}] {before_boxes[box]}->{after_boxes[box]}" for box in moved[:3])
        note = f"{len(moved)} of {len(shared)} shared boxes moved (e.g. {sample})"
        # A displacement count measured across a decomposition change is not a
        # clean in-record figure: a box that migrated into a NEW record counts
        # as "moved" alongside one that shifted within its own. Both are real
        # movement, but comparing the magnitude against a same-record
        # boundary's is comparing different quantities.
        if _record_count_delta():
            note += " -- NOT a clean in-record displacement: the record set also changed"
        evidence.append(note)

    # FOURTH SIGNAL: the box SET changed, whether or not anything moved.
    #
    # The comparison above reads only DISPLACEMENT -- it iterates the boxes the two
    # designs SHARE -- so a box present in one design and absent in the other is
    # outside its loop entirely. That is not a lesser event: a box the later design
    # declares and the earlier one does not cannot be declared at all under the
    # earlier layout, and a box the earlier one declares and the later one drops is
    # a value written into space the later design puts to another use.
    #
    # Measured on Modelo 390, where the whole class was invisible: 2015 to 2016 adds
    # six boxes and 2016 to 2017 removes twenty, both with ZERO movement, identical
    # or unreadable page lengths and no occupancy transition, so no signal in this
    # module reported either boundary.
    #
    # The blindness survived because it is MASKED wherever membership changes
    # alongside movement: the 2017 to 2018 boundary drops seventy-two boxes, and the
    # displacement check reports that boundary anyway on its ninety-seven moved
    # boxes, so a reader spot-checking the signal against that pair sees a
    # membership change duly reported and concludes the set is compared.
    membership = _box_set_evidence(before_boxes, after_boxes)
    if membership:
        evidence.append(membership)

    if before_lengths and after_lengths and before_lengths != after_lengths:
        delta = _record_count_delta()
        # Say what a page-length change MEANS before showing the raw tuples. A
        # record-count change is a different and larger event than a page growing,
        # and stated as bare tuples it was under-read for hours by everyone
        # looking at it, including its author.
        headline = (
            f"RECORD SET CHANGED ({delta}) -- the design's record decomposition differs, so this is not an offset shift"
            if delta
            else "page byte-lengths differ, so something moved inside a record"
        )
        evidence.append(f"{headline}: {before_lengths} vs {after_lengths}")

    evidence.extend(_occupancy_evidence(earlier, later))

    # SIXTH SIGNAL: a field added or removed at a position, independent of box number.
    # See _position_set_evidence's own docstring for the full rationale and the
    # measured false positive (Modelo 202's reserved-space repartition) its exclusion
    # closes.
    position_membership = _position_set_evidence(earlier, later)
    if position_membership:
        evidence.append(position_membership)

    description = _description_flip_evidence(earlier, later)
    if description:
        evidence.append(description)

    # SEVENTH SIGNAL: a pure displacement, which every signal above is blind to.
    straddle = _straddle_evidence(earlier, later)
    if straddle:
        evidence.append(straddle)

    return evidence


def _straddle_evidence(earlier: Path, later: Path) -> str | None:
    """SEVENTH SIGNAL: a field DISPLACED so it overlaps another without containing it.

    The signal every other one here is blind to, and the blindness is structural
    rather than incidental. The box signals key on a bracketed number, so a
    design that prints none -- Modelo 347's do not -- gives them nothing to
    watch. The membership signals key on a field being added or removed, so a
    pure WIDENING leaves them seeing the same set before and after. Modelo 347's
    2010 and 2011 declarante records have the SAME field count and the same
    descriptions; all that changed is that ``IMPORTE TOTAL ANUAL`` grew from 15
    bytes to 16 and pushed everything after it one position along.

    That is a re-layout by any useful definition -- a filing written at the
    wrong one is a byte out from position 145 to the end of the record -- and it
    went unreported.

    WHAT STRADDLING MEANS, AND WHY IT IS THE RIGHT TEST. Where a field of one
    design sits wholly INSIDE a field of the other, the narrower is a
    subdivision of the wider: AEAT split or merged a slot, and the bytes still
    correspond. Where two fields overlap with neither containing the other, each
    covers bytes the other does not, and no correspondence survives. So
    containment is tolerated and straddling is evidence, which is the same
    distinction the record-design contiguity rules already turn on.

    Reads BYTES, so it needs neither a box number nor a description change.
    """
    before = {sheet.name: sheet for sheet in _design_sheets(earlier)}
    after = {sheet.name: sheet for sheet in _design_sheets(later)}

    straddles: list[str] = []
    for name in sorted(set(before) & set(after)):
        later_fields = sorted(after[name].fields, key=lambda field: field.offset)
        starts = [field.offset for field in later_fields]
        for a in before[name].fields:
            a_start, a_end = a.offset, a.offset + a.length - 1
            # Only fields starting at or before a_end can overlap; walk back far
            # enough to catch one that starts earlier and reaches into a.
            index = bisect_right(starts, a_end)
            for b in reversed(later_fields[:index]):
                b_start, b_end = b.offset, b.offset + b.length - 1
                if b_end < a_start:
                    break
                if (a_start >= b_start and a_end <= b_end) or (b_start >= a_start and b_end <= a_end):
                    continue
                straddles.append(f"{name} @{a_start}-{a_end} vs @{b_start}-{b_end}")

    if not straddles:
        return None
    return f"{len(straddles)} field(s) displaced so they straddle the other design's boundaries (e.g. {straddles[0]})"


def _occupancy_evidence(earlier: Path, later: Path) -> list[str]:
    """THIRD SIGNAL: a slot moving into or out of reserved space.

    It moves no box and changes no page length -- the reserved block absorbs the freed
    bytes exactly -- so neither signal above can see it, and a digest cannot either. It
    is still a re-layout: a field present in one design and absent in the next means a
    filing written under the older layout puts declared values into space AEAT now marks
    reserved.

    Measured live on Modelo 390, where three ``Reg. Simplificado - Reducción aplicable``
    slots were retired between the 2024 and 2025 designs while both signals above
    reported the years identical.

    BOTH DIRECTIONS are asserted, and the reverse one was withheld on a claim that was
    never checked against the corpus it described. This module used to record that
    reserved -> real "measures zero across the whole bundled corpus, so an assertion for
    it would ship vacuous and pass silently forever." Measured through these very
    helpers, it is 32 transitions across four modelos and twelve boundaries -- twice the
    16 retirements the direction that WAS asserted finds. A rationale for withholding an
    assertion is itself a measurement, and this one was reasoned rather than run.

    Nor is it the lesser half. A slot revived OUT of reserved space is a field the later
    design declares and the earlier one does not, so a filing written under the earlier
    layout cannot declare that quantity at all while the later one can -- the same harm
    as a retirement with the two sides exchanged, and equally invisible to an offset
    check, a length check and a digest. On Modelo 303 it is the only signal in this
    module that names a boundary at 2017/2018.
    """
    before, after = _occupancy(earlier), _occupancy(later)
    shared = set(before) & set(after)
    evidence: list[str] = []
    for slots, headline in (
        (
            sorted(slot for slot in shared if not before[slot] and after[slot]),
            "RETIRED into reserved space",
        ),
        (
            sorted(slot for slot in shared if before[slot] and not after[slot]),
            "REVIVED out of reserved space",
        ),
    ):
        if not slots:
            continue
        sample = ", ".join(f"{sheet} offset {offset}" for sheet, offset in slots[:3])
        evidence.append(
            f"{len(slots)} slot(s) {headline} (e.g. {sample}) -- no box moved and no page "
            "length changed, so one side of this boundary declares a quantity at a position "
            "the other side marks reserved"
        )
    return evidence
