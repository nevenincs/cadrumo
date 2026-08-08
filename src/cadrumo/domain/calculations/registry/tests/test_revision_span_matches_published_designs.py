"""A registry revision must not span an AEAT record-design re-layout.

A revision carries exactly ONE export layout, so every filing year inside its
period selector is written at the SAME byte offsets. AEAT re-lays out its Diseños
de Registro whenever a block gains a rung, and every downstream offset shifts. A
revision whose span crosses such a boundary therefore encodes one byte layout
across two incompatible designs, and one of them is wrong.

The harm is not a wrong number in a box. Measured on Modelo 390: an export for a
filing year on the older side of a boundary succeeds and produces bytes laid out
for the newer design, so a reader using the correct design for that year finds
the declared total ABSENT where it expects it, a real value in a different box's
slot, and content past the end of the record.

WHY THIS IS KEYED ON DESIGN-TO-DESIGN AGREEMENT rather than on comparing each
layout field against its published box. The obvious framing needs a casilla ->
official box number mapping, and on several modelos that mapping barely exists:
casillas are semantic ids, the design is box-numbered, and the two vocabularies
do not intersect. A number-keyed check would report hundreds of false absences on
Modelo 390 alone. Design-to-design agreement needs no such mapping and states the
actual defect: one layout cannot cover years AEAT laid out differently.

The expected offsets are PARSED out of the bundled designs, never transcribed, so
the corpus is the authority and an author's misreading cannot enter the gate.

WHAT THIS DOES NOT CHECK, stated plainly so its silence is not over-read. It does
NOT verify that a revision's layout matches the design for its year -- only that
the revision does not CLAIM years whose designs disagree. A revision confined to
one design's years passes here even if every offset in its layout is wrong,
because that comparison needs the casilla-to-box mapping this module deliberately
avoids depending on. The two checks are complements: this one bounds the span,
and a per-modelo offset gate (where the box numbers exist) bounds the contents.

It also does NOT enforce the authoring policy that governs how a span is split.
The accepted posture is to split only at boundaries inside a modelo's reachable
filing window -- defined by prescripción, four years from the voluntary filing
deadline (LGT arts. 66-67), computed at implementation time -- and to refuse
export for years before the earliest split. This gate knows nothing of that. It
compares designs across whatever span a revision CLAIMS, so it catches a span
widened back over a boundary and objects to nothing if a revision is split where
the window no longer requires one. The asymmetry is deliberate: this instrument
guards byte-correctness, that policy guards authoring cost, and they answer
different questions. Its silence about a split is not approval of the split.

That window is itself dated and moves. Exercise 2021 prescribed on 2026-01-30,
so a boundary that required a split in December 2025 does not require one now,
and the next expiry shifts the answer again. Recompute it rather than reading a
boundary set off any record, including this one.

ANTI-VACUITY. A parser that cannot read a design returns the same answer as a
design with no divergence, so silence has to be loud: a design file this module
claims to read but extracts nothing from is a FAILURE, not a skip. Without that,
the gate goes green by not looking, which is this instrument's most likely rot
path.

No count is hardcoded. The number of designs, boundaries and shared boxes all
vary as the corpus grows; gating on any of them would encode today and detect
nothing tomorrow.

RUNTIME, stated here so the next reader meets it in the code rather than in CI.
Reading the design SOURCES rather than their markdown derivatives took this
module from roughly 28s to roughly 185s, a five-fold increase, because it now
parses spreadsheets and PDFs instead of pre-extracted text. Two things keep that
acceptable and both are worth knowing before anyone tries to "optimise" it. The
parsers are ``lru_cache``d, so the cost is paid ONCE PER SESSION rather than per
test -- the number that matters for CI is the one-off, not a multiple of it. And
it cannot be scoped away: restricting the parse to modelos that actually declare
an export layout removes only ~37% of the files and ~15% of the bytes, because
the largest designs belong to modelos that do export. The cost buys the offsets
and the field occupancy the derivatives do not carry, which is what the box and
retirement signals are made of.

THREE INDEPENDENT SIGNALS, ONE VERDICT -- and the third reports two directions.
The count in this heading was wrong for as long as the occupancy signal existed,
which is worth stating rather than quietly correcting: a module that miscounts its
own instruments invites a reader to act on the two it names. The box-offset diff sees which boxes moved
but needs bracketed box markers. The page-length diff sees only that a page
changed size, but reads designs the box table cannot -- several older PDF
extractions publish their page totals while yielding no box markers -- so it
measures years that would otherwise be blind. Neither subsumes the other: a
re-layout preserving every page length is caught by the first, a year only the
second can read is caught by the second. A year is reported UNMEASURED only when
BOTH are blind.

They report through ONE assertion rather than two, because reporting separately
was the instrument's own defect. The two see overlapping but DIFFERENT boundary
sets, so a fix owner acting on either list alone splits a revision at some of its
boundaries and leaves the rest standing -- a gate still red, reading as an
incomplete fix rather than a wrong one. Modelo 303 is the live case: two of its
six boundaries are visible only to the page-length signal. The failure text is
therefore the split specification, naming per revision every boundary, which
signal saw it, and how many revisions the span actually needs.

THIS MODULE IS LANDED RED, DELIBERATELY, AND THE FAILURES ARE THE FINDING RATHER
THAN A REGRESSION. It names two confirmed live defects: Modelo 390's single
revision spans five re-layouts, and Modelo 303's revisions span six more --
including a 2025-to-2026 shift affecting filings made today, where the box diff
shows 120 of 163 shared boxes moving and the page diff independently shows the
Liquidación page growing by five bytes. The Modelo 390 case was proved end to end
-- an export at an earlier filing year succeeds and writes bytes laid out for the
newest design. Weakening the assertions to land green would delete the evidence;
all of it goes green when the revisions are split at the boundaries the failure
text names, which is the fix.

The coverage guard is red for a different and much smaller reason: one year
inside a gated span has a design neither signal can read.

Mutation-proved from outside the repository, three directions. Narrowing Modelo
390's claimed span to the newest design removes exactly its own violations and
leaves every other modelo's standing. Widening every revision to claim all design
years implicates further modelos, so the gate detects a span that grows into a
boundary rather than only the spans that exist today. Breaking the box pattern
makes the coverage guard refuse instead of passing on an empty parse.
"""

from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition
from .._authority import ValidatedRegistryAuthority
from .._record_design import (
    extract_record_design_pdf,
    extract_record_design_workbook,
    extract_record_design_xls_workbook,
)
from .._record_design_schema import RecordDesignSheet

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_DESIGN_ROOT_PARTS = ("corpus", "aeat_official", "disenos_registro")

# The extracted design tables render one field per row as
# "order | offset | length | kind | description [box] | ... ".
_BOX_MARKER = re.compile(r"\[(\d{1,4})\]")
_DESIGN_YEAR = re.compile(r"ejercicios?-(\d{4})(?:-(y|a|hasta)-(\d{4}))?")
#: A design filename may name TWO explicit ejercicios ("ejercicio-2015-y-2016"),
#: and the corpus holds four such spans (2007-y-2008, 2008-y-2009, 2015-y-2016,
#: 2019-y-2020). Taking only the first match attributed the design to its opening
#: year and left the second attributed to NOTHING -- 2016 and 2020 each had a
#: bundled design and no year claiming it. "y-siguientes" is deliberately NOT
#: expanded: its span is open-ended, so enumerating it would invent years.
#: The orden year in a filename ("orden-hap-2373-2014-...-ejercicio-2018") is not
#: a coverage year and must never be read as one, which is why this anchors on
#: "ejercicio-" rather than scanning for any four-digit run.
#: Case-INSENSITIVE on purpose. AEAT writes both `Reservado para la AEAT` and
#: `RESERVADO PARA LA A.E.A.T.`, and a case-sensitive substring test silently
#: misses the uppercase form -- which reads a reserved block's own growth as a
#: moved field and invents a boundary that is not there.
_RESERVED_FIELD = re.compile(r"reservado", re.IGNORECASE)
#: Design SOURCE suffixes, in preference order for a year bundled more than once.
_DESIGN_SUFFIXES = (".xlsx", ".xls", ".pdf")
#: The synthetic single-sheet name the PDF backend falls back to when a document
#: declares no per-page sections. Its presence means the parse is FLATTENED, so
#: per-page signals must abstain rather than compare one synthetic page against
#: a spreadsheet's real ones.
_PDF_FLATTENED_SHEET = "PDF record design"

# Each page closes with a "TOTAL <n> POSICIONES" row, in the pipe-delimited
# spreadsheet extractions and the space-delimited PDF ones alike. The sequence of
# page lengths is a SECOND, box-number-free signal: if a page's byte length
# changed, something inside it moved. It reaches designs the box table cannot --
# the older PDF extractions carry these rows while yielding no bracketed boxes.
_PAGE_TOTAL = re.compile(r"TOTAL\s*\|?\s*\|?\s*(\d+|variable)\s*\|?\s*POSICIONES", re.IGNORECASE)


def _authority() -> ValidatedRegistryAuthority:
    return ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())


def _design_dir(modelo_id: str) -> Path:
    return bundled_path(*_DESIGN_ROOT_PARTS, f"modelo_{modelo_id}")


def _sources_by_year(modelo_id: str) -> tuple[tuple[int, Path], ...]:
    """``(design year, source path)`` pairs, first source per year winning."""
    seen: dict[int, Path] = {}
    for path in _design_sources(modelo_id):
        if not _design_sheets(path):
            continue
        for year in _design_years(path.name):
            seen.setdefault(year, path)
    return tuple(sorted(seen.items()))


def _design_years(name: str) -> tuple[int, ...]:
    """Every ejercicio a design filename claims, expanded and ordered.

    AEAT names these four ways and they do NOT mean the same thing:

    * ``ejercicio-2024``            -- one year.
    * ``ejercicios-2024``           -- one year; the plural is a naming
      habit, not a range, and it appears on 61 bundled files.
    * ``ejercicio-2015-y-2016``     -- TWO discrete years ("and").
    * ``ejercicios-2004-a-2009`` /
      ``ejercicios-2016-hasta-2018`` -- an INCLUSIVE RANGE ("through"),
      so 2004-a-2009 claims six years, not two endpoints.

    Reading ``a``/``hasta`` as two endpoints silently drops every year
    between them, and matching only the singular ``ejercicio-`` misses 40 of
    the 209 bundled design files across 15 modelos entirely -- a design that
    is invisible to enumeration reads exactly like one that does not exist.

    ``y-siguientes`` is still NOT expanded: its span is open-ended, so
    enumerating it would invent years.
    """
    matched = _DESIGN_YEAR.search(name)
    if matched is None:
        return ()
    first, connector, second = matched.group(1), matched.group(2), matched.group(3)
    if second is None:
        return (int(first),)
    if connector == "y":
        return (int(first), int(second))
    return tuple(range(int(first), int(second) + 1))


#: AEAT's declared period bound for a design that covers only part of an ejercicio.
#: ``hasta-periodo(s)-06`` covers the year UP TO that period, so its coverage STARTS at
#: 01; ``desde-periodo-07`` and ``a-partir-de-periodos-09`` cover FROM that period on, so
#: their coverage starts there. Ordering on the declared coverage start is what puts the
#: two halves of a mid-split ejercicio in publication order.
_COVERAGE_BOUND = re.compile(r"(hasta|a-partir-de|desde)-periodos?-(\d{2})", re.IGNORECASE)


def _coverage_start_period(name: str) -> int | None:
    """The first period a design's own AEAT designation claims, or ``None``.

    WHY THIS IS NOT READ FROM THE FILE BODY, stated because the honest answer is that
    it cannot be. The design workbooks carry NO assertion of the periods they govern:
    measured across Modelo 303's two 2024 halves, both declare the identical sheet set
    and the identical ``Ejercicio de devengo (EEEE)`` and ``Período. (PP)`` header
    fields, because those are slots the FILER fills in, not metadata about the design's
    own coverage. Zero coverage assertions exist inside either file. AEAT's published
    designation is therefore the only place the boundary is stated at all, which is why
    this reads the designation rather than the document.

    WHAT THIS IS NOT. It is not the numeric filename prefix. AEAT numbers its published
    listing NEWEST FIRST -- Modelo 303's ``01`` is the 2026 design and its ``06`` is
    2025 -- so a filename sort is not merely arbitrary, it is close to REVERSED, and
    within one year it silently pairs the LATE half before the EARLY one. Nothing here
    depends on that numbering, so a change to AEAT's listing convention cannot move it.

    Returns ``None`` when the designation declares no period bound, which is a real
    case rather than a defect: Modelo 303's two 2018 designs are ``ejercicio-2018`` and
    ``ejercicio-2018-salvo-ultimo-periodo-12m-4t``, and "except the last period" fixes
    no start while the unqualified sibling asserts nothing at all. Ordering those two
    would be inference by elimination dressed as a measurement, so the caller is told
    the year is unorderable instead.
    """
    matched = _COVERAGE_BOUND.search(name)
    if matched is None:
        return None
    kind, period = matched.group(1).lower(), int(matched.group(2))
    return 1 if kind == "hasta" else period


def _designs_in_publication_order(modelo_id: str) -> tuple[tuple[Path, ...], tuple[int, ...]]:
    """``(designs oldest-first, years whose designs could not be ordered)``.

    Deduplicated by CONTENT, because the corpus bundles several designs twice under
    names differing only by a truncated extension, and a path-keyed pass reports the
    duplicate as a second design.

    A year holding two designs where at least one declares no coverage bound is
    reported in the second element and its members are left in a stable but
    UNASSERTED order, so a consumer can refuse rather than trust it.
    """
    by_year: dict[int, list[Path]] = {}
    seen: set[bytes] = set()
    for path in _design_sources(modelo_id):
        if not _design_sheets(path):
            continue
        years = _design_years(path.name)
        if not years:
            continue
        payload = path.read_bytes()
        if payload in seen:
            continue
        seen.add(payload)
        by_year.setdefault(min(years), []).append(path)

    ordered: list[Path] = []
    unorderable: list[int] = []
    for year in sorted(by_year):
        members = by_year[year]
        starts = [_coverage_start_period(path.name) for path in members]
        if len(members) > 1 and any(start is None for start in starts):
            unorderable.append(year)
            ordered.extend(sorted(members, key=lambda path: path.name))
            continue
        ordered.extend(sorted(members, key=lambda path: (_coverage_start_period(path.name) or 1, path.name)))
    return tuple(ordered), tuple(unorderable)


def _designs_by_year(modelo_id: str) -> dict[int, tuple[Path, ...]]:
    """``{year: every readable design source claiming it}`` -- one to MANY.

    AEAT splits an ejercicio mid-course, so a year can have two designs that differ
    in byte layout. Modelo 303 does it three times: 2018, 2021 and 2024 each ship a
    "hasta periodo N" design and a "desde/a partir de periodo N" one. The year-keyed
    maps below keep the FIRST by filename sort and silently discard the other, so a
    caller asking what a year looked like gets an arbitrary half with no signal a
    second exists. This map keeps both, so a consumer deriving epoch boundaries can
    see the split rather than land a boundary on the wrong side of it.
    """
    grouped: dict[int, list[Path]] = {}
    for path in _design_sources(modelo_id):
        if not _design_sheets(path):
            continue
        for year in _design_years(path.name):
            grouped.setdefault(year, []).append(path)
    return {year: tuple(paths) for year, paths in sorted(grouped.items())}


def _design_sources(modelo_id: str) -> list[Path]:
    """Every bundled design SOURCE for one modelo, deterministically ordered."""
    directory = _design_dir(modelo_id)
    if not directory.is_dir():
        return []
    return sorted(
        (path for path in directory.glob("files/*") if path.suffix.lower() in _DESIGN_SUFFIXES),
        key=lambda path: (path.name, path.suffix.lower()),
    )


def _design_sheets(path: Path) -> tuple[RecordDesignSheet, ...]:
    """Parse one design SOURCE, dispatching on its suffix.

    The sources are read directly rather than their ``.extracted.md``
    derivatives. The markdown extraction of a PDF drops the offset column and
    the page-total rows, so every PDF-sourced design read that way reports as
    unreadable while the shipped parser reads the same file correctly -- 21 of
    the 24 designs this module called unmeasured were readable all along, six
    of them consecutive Modelo 100 years. Reading the source removes the whole
    class rather than special-casing it.

    Returns an empty tuple for a genuinely unparseable file, so the caller's
    unreadable-reporting path still names it. A parse that fails must stay
    visible as unmeasured; only a parse that never ran should disappear.
    """
    parsers = {
        ".xlsx": extract_record_design_workbook,
        ".xls": extract_record_design_xls_workbook,
        ".pdf": extract_record_design_pdf,
    }
    parser = parsers.get(path.suffix.lower())
    if parser is None:
        return ()
    try:
        return parser(path)
    except Exception:
        return ()


def _parse_extracted(path: Path) -> dict[str, int]:
    """box number -> offset from a design's ``.extracted.md`` derivative.

    Retained as a FALLBACK, not as the primary read. Measured: switching to the
    sources alone closed 21 PDF-sourced designs but OPENED new blind spots on
    `.xls` files whose markdown parses while the binary does not, so the
    unreadable count moved 24 -> 21 rather than 24 -> 3. Source-first with a
    derivative fallback is strictly better than either alone -- the source
    yields offsets and occupancy the markdown cannot, and the markdown covers
    the binaries the parsers refuse.
    """
    derivative = path.with_name(path.name + ".extracted.md")
    if not derivative.is_file():
        return {}
    table: dict[str, int] = {}
    for line in derivative.read_text(encoding="utf-8", errors="replace").splitlines():
        if "|" not in line:
            continue
        columns = [column.strip() for column in line.split("|")]
        if len(columns) < 5:
            continue
        try:
            offset = int(columns[1])
        except (IndexError, ValueError):
            continue
        boxes = _BOX_MARKER.findall(line)
        if boxes:
            table.setdefault(boxes[-1], offset)
    return table


def _parse_design(path: Path) -> dict[str, int]:
    """box number -> record offset for one design, source first, derivative second."""
    table: dict[str, int] = {}
    for sheet in _design_sheets(path):
        for field in sheet.fields:
            offset = field.offset
            boxes = _BOX_MARKER.findall(field.description)
            if not boxes:
                continue
            # A field's OWN number is the LAST bracket on its row. Formula totals cite
            # their operands first -- "Total cuota devengada ([152]+[167]+...) [27]"
            # -- so first-match keying would file the total under an operand, and
            # requiring a single bracket would drop it entirely. Modelo 303 has
            # eleven such rows, including its three most load-bearing totals; Modelo
            # 390 has none, which is why this only surfaced on the second modelo.
            #
            # A box can also appear once per régimen segment at the same offset; keep
            # the first and never overwrite, so a later segment cannot mask a move.
            #
            # Modelo 390 proves this is not hypothetical: box [114] carries one
            # `Código CNAE` per prorrata row -- once in the 2016 design and FIVE
            # times in 2017. A last-wins map compares 2016's first row against
            # 2017's fifth and reports a +332 "move" that never happened.
            table.setdefault(boxes[-1], offset)
    return table or _parse_extracted(path)


def _page_lengths(path: Path) -> tuple[str, ...]:
    """The per-sheet declared record length, source first, derivative second.

    ABSTAINS on a flattened PDF parse. The PDF backend returns ONE synthetic
    sheet covering the whole document, so its "page lengths" are a one-element
    tuple describing no page at all. Compared against a spreadsheet's nine real
    per-page totals it differs unconditionally, which reports a re-layout
    between every PDF-sourced year and its neighbour -- a boundary manufactured
    by the parser shape rather than by AEAT.

    Measured: with the flattened tuple emitted, Modelo 390 gained a false
    2015->2016 boundary, while a box-keyed comparison of the same two designs
    finds 345 shared boxes and ZERO moved. Returning nothing lets the box signal
    carry those years and keeps this one honest about what it cannot see.
    """
    sheets = _design_sheets(path)
    if len(sheets) == 1 and sheets[0].name == _PDF_FLATTENED_SHEET:
        return ()
    lengths = tuple("variable" if sheet.total_positions is None else str(sheet.total_positions) for sheet in sheets)
    if lengths:
        return lengths
    derivative = path.with_name(path.name + ".extracted.md")
    if not derivative.is_file():
        return ()
    return tuple(_PAGE_TOTAL.findall(derivative.read_text(encoding="utf-8", errors="replace")))


def _occupancy(path: Path) -> dict[tuple[str, int], bool]:
    """``(sheet, offset) -> is_reserved`` for every field in one design.

    The reserved flag is carried as a VALUE rather than applied as a filter, and
    that is the whole point. Excluding reserved rows from a comparison makes a
    field RETIRED INTO reserved space invisible: it is real on one side and
    reserved on the other, so the exclusion drops one side and the pair is never
    compared. Measured on Modelo 390, three `Reg. Simplificado - Reducción
    aplicable` slots were retired between the 2024 and 2025 designs at offsets
    223, 543 and 1205, and a reserved-excluding diff reported the two years
    identical.

    A filter that drops a category cannot see movement into or out of that
    category. Keying on the position and classifying afterwards makes the
    transition a first-class result.
    """
    return {
        (sheet.name, field.offset): _RESERVED_FIELD.search(field.description) is not None
        for sheet in _design_sheets(path)
        for field in sheet.fields
    }


def _page_lengths_for(modelo_id: str) -> dict[int, tuple[str, ...]]:
    """``{design year: page-length sequence}`` for every readable design."""
    lengths: dict[int, tuple[str, ...]] = {}
    for path in _design_sources(modelo_id):
        found = _page_lengths(path)
        if not found:
            continue
        for year in _design_years(path.name):
            lengths.setdefault(year, found)
    return lengths


def _designs_for(modelo_id: str) -> tuple[dict[int, dict[str, int]], dict[int, str]]:
    """Return ``{design year: {box: offset}}`` and ``{year: filename}`` for unreadable ones.

    A design whose year cannot be read off the filename is excluded from both
    maps: it can neither be compared nor attributed to a revision's span, so
    counting it either way would be a guess.
    """
    parsed: dict[int, dict[str, int]] = {}
    unreadable: dict[int, str] = {}
    for path in _design_sources(modelo_id):
        table = _parse_design(path)
        for year in _design_years(path.name):
            if table:
                parsed.setdefault(year, table)
            elif year not in parsed:
                unreadable.setdefault(year, path.name)
    return parsed, unreadable


def _span_years(revision) -> set[int]:
    """Every filing year the revision's period selector claims."""
    selector = revision.period_selector
    if selector.years:
        return set(selector.years)
    if selector.year_from is None:
        return set()
    upper = selector.year_to
    if upper is None:
        # Open-ended: the gate can only speak about years the corpus covers, so
        # the span is bounded by the newest bundled design rather than by a
        # literal ceiling that would go stale.
        return {selector.year_from}
    return set(range(selector.year_from, upper + 1))


def _exporting_revisions() -> list[tuple[ModeloDefinition, str, object]]:
    return [
        (modelo, revision_id, revision)
        for modelo in _authority().modelos
        for revision_id, revision in modelo.revisions.items()
        if revision.export_layouts
    ]


def _claimed_years(revision, design_years: set[int]) -> set[int]:
    """Design years the revision claims, honouring an open-ended upper bound."""
    selector = revision.period_selector
    explicit = _span_years(revision)
    if selector.years or selector.year_from is None:
        return explicit & design_years
    if selector.year_to is None:
        return {year for year in design_years if year >= selector.year_from}
    return explicit & design_years


def test_the_design_parser_reads_every_markdown_design_it_claims() -> None:
    """A design that parses to nothing must fail, never pass by silence.

    This is the gate's anti-vacuity guard and its most likely rot path. If the
    extraction shape changes, or a regex stops matching, every comparison below
    would run over an empty table and agree trivially. An unreadable design is
    reported as UNMEASURED here rather than quietly dropped, because a parser
    that cannot read a format returns the same answer as a format with no
    divergence.
    """
    blind_spots: list[str] = []
    measured = 0
    for modelo, revision_id, revision in _exporting_revisions():
        designs, unreadable = _designs_for(modelo.id)
        measured += len(designs)
        if not unreadable:
            continue
        # Only a design INSIDE a gated revision's span can hide a divergence from
        # this gate. One outside every span is a corpus file nothing compares,
        # so failing on it would be noise about the extractor rather than about
        # coverage.
        # A year is only a blind spot when BOTH signals are blind. A design that
        # yields no bracketed boxes but does publish its per-page lengths is
        # still measured by the page-length check below, so reporting it here
        # would overstate the gap.
        page_lengths = _page_lengths_for(modelo.id)
        opaque = {year for year in unreadable if year not in page_lengths}
        in_span = _claimed_years(revision, opaque)
        blind_spots.extend(
            f"modelo {modelo.id} revision {revision_id!r} claims {year}, but its design "
            f"{unreadable[year]!r} yields neither box offsets nor page lengths"
            for year in sorted(in_span)
        )
    assert measured, "no bundled design parsed at all; the extractor or the corpus path has moved"
    assert not blind_spots, (
        "these years are UNMEASURED rather than clean -- the gate cannot see a re-layout there, "
        "so its silence about them means nothing:\n  " + "\n  ".join(sorted(set(blind_spots)))
    )


def _boundaries_for(modelo_id: str, revision) -> dict[tuple[int, int], list[str]]:
    """Every re-layout boundary inside one revision's span, keyed year-pair to evidence.

    Both signals contribute to ONE verdict rather than reporting separately,
    because they see overlapping-but-different boundary sets and a reader
    unioning two lists by hand will miss the ones only the weaker signal saw.
    """
    boundaries: dict[tuple[int, int], list[str]] = {}

    lengths = _page_lengths_for(modelo_id)

    def _record_count_delta(earlier: int, later: int) -> str | None:
        """``'9 -> 10 records'`` when the design's record SET changed, else None."""
        if earlier not in lengths or later not in lengths:
            return None
        before, after = len(lengths[earlier]), len(lengths[later])
        return None if before == after else f"{before} -> {after} records"

    designs, _ = _designs_for(modelo_id)
    box_years = sorted(_claimed_years(revision, set(designs)))
    for earlier, later in pairwise(box_years):
        before_boxes, after_boxes = designs[earlier], designs[later]
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
            if _record_count_delta(earlier, later):
                note += " -- NOT a clean in-record displacement: the record set also changed"
            boundaries.setdefault((earlier, later), []).append(note)

    page_years = sorted(_claimed_years(revision, set(lengths)))
    for earlier, later in pairwise(page_years):
        if lengths[earlier] == lengths[later]:
            continue
        delta = _record_count_delta(earlier, later)
        # Say what a page-length change MEANS before showing the raw tuples. A
        # record-count change is a different and larger event than a page growing,
        # and stated as bare tuples it was under-read for hours by everyone
        # looking at it, including its author.
        headline = (
            f"RECORD SET CHANGED ({delta}) -- the design's record decomposition differs, so this is not an offset shift"
            if delta
            else "page byte-lengths differ, so something moved inside a record"
        )
        boundaries.setdefault((earlier, later), []).append(f"{headline}: {lengths[earlier]} vs {lengths[later]}")

    # THIRD SIGNAL: a slot RETIRED into reserved space. It moves no box and
    # changes no page length -- the reserved block absorbs the freed bytes
    # exactly -- so neither signal above can see it, and a digest cannot either.
    # It is still a re-layout: a field present in one design and absent in the
    # next means a filing written under the older layout puts declared values
    # into space AEAT now marks reserved.
    #
    # Measured live on Modelo 390, where three `Reg. Simplificado - Reducción
    # aplicable` slots were retired between the 2024 and 2025 designs while both
    # signals above reported the years identical.
    #
    # BOTH DIRECTIONS are asserted, and the reverse one was withheld on a claim
    # that was never checked against the corpus it described. This module used to
    # record that reserved -> real "measures zero across the whole bundled corpus,
    # so an assertion for it would ship vacuous and pass silently forever."
    # Measured through these very helpers, it is 32 transitions across four
    # modelos and twelve boundaries -- twice the 16 retirements the direction that
    # WAS asserted finds. A rationale for withholding an assertion is itself a
    # measurement, and this one was reasoned rather than run.
    #
    # Nor is it the lesser half. A slot revived OUT of reserved space is a field
    # the later design declares and the earlier one does not, so a filing written
    # under the earlier layout cannot declare that quantity at all while the
    # later one can -- the same harm as a retirement with the two sides
    # exchanged, and equally invisible to an offset check, a length check and a
    # digest. On Modelo 303 it is the only signal in this module that names a
    # boundary at 2017/2018.
    occupancy_years = sorted(_claimed_years(revision, {year for year, _ in _sources_by_year(modelo_id)}))
    sources = dict(_sources_by_year(modelo_id))
    for earlier, later in pairwise(occupancy_years):
        before, after = _occupancy(sources[earlier]), _occupancy(sources[later])
        shared = set(before) & set(after)
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
            boundaries.setdefault((earlier, later), []).append(
                f"{len(slots)} slot(s) {headline} (e.g. {sample}) -- no box moved and no page "
                "length changed, so one side of this boundary declares a quantity at a position "
                "the other side marks reserved"
            )

    return boundaries


def test_no_revision_spans_a_design_relayout() -> None:
    """One revision, one byte layout — so its span must not cross a re-layout.

    ONE verdict from BOTH signals, deliberately. Reporting them as separate
    failures was the instrument's own defect: the offset diff and the page-length
    diff see overlapping but different boundary sets, so a fix owner reading
    either list alone splits a revision at some of its boundaries and leaves the
    rest standing — a gate still red, looking like an incomplete fix rather than
    a wrong one. Modelo 303 is the live case: two of its boundaries are visible
    only to the page-length signal.

    The failure text is therefore the split specification. For each revision it
    names every boundary, which signal saw it, and how many revisions the span
    actually needs, so nobody has to union two lists by hand to act on it.
    """
    violations: list[str] = []
    for modelo, revision_id, revision in _exporting_revisions():
        boundaries = _boundaries_for(modelo.id, revision)
        if not boundaries:
            continue
        detail = "; ".join(
            f"{earlier}/{later} ({' + '.join(evidence)})" for (earlier, later), evidence in sorted(boundaries.items())
        )
        violations.append(
            f"modelo {modelo.id} revision {revision_id!r} spans {len(boundaries)} re-layout(s) "
            f"and needs {len(boundaries) + 1} revisions -- {detail}"
        )
    assert not violations, (
        "a revision carries ONE export layout, so a span crossing a re-layout writes prior-year "
        "filings at the wrong byte offsets. Split each revision at every boundary listed; "
        "splitting at only the ones one signal saw leaves the rest live:\n  " + "\n  ".join(violations)
    )


def test_both_occupancy_directions_have_a_positive_case_in_the_corpus() -> None:
    """Neither occupancy direction may be asserted over a corpus that cannot show it.

    This is the companion guard to the reserved-space signal, and it exists
    because the reverse direction was once withheld from the verdict on the
    recorded ground that it "measures zero across the whole bundled corpus, so
    an assertion for it would ship vacuous". That was a reasoned claim, not a
    measured one, and it was wrong by a factor of two in the direction that
    mattered. This test is what makes the same mistake impossible to repeat in
    either direction: if a corpus change ever leaves one of them with no
    instance, the signal becomes unfalsifiable and this fails LOUDLY rather than
    the verdict silently passing over it.

    GATED ON THE PROPERTY, NEVER ON A TALLY. It asserts each direction has AT
    LEAST ONE instance, not how many. The counts move every time AEAT publishes,
    so pinning today's 16 retirements and 32 revivals would encode this moment,
    train the next author to bump two constants, and detect nothing. "The signal
    can still be observed" is the durable property; "the signal is observed
    exactly n times" is a snapshot wearing an assertion's clothes.

    Deliberately spans the WHOLE corpus rather than one revision's claimed span.
    A positive case anywhere proves the signal is live; requiring one inside
    every span would fail on modelos that simply never re-layout, which is not a
    defect.
    """
    retired_seen: list[str] = []
    revived_seen: list[str] = []
    for modelo, _revision_id, revision in _exporting_revisions():
        sources = dict(_sources_by_year(modelo.id))
        for earlier, later in pairwise(sorted(_claimed_years(revision, set(sources)))):
            before, after = _occupancy(sources[earlier]), _occupancy(sources[later])
            shared = set(before) & set(after)
            retired_seen.extend(
                f"modelo {modelo.id} {earlier}/{later} {slot[0]} offset {slot[1]}"
                for slot in shared
                if not before[slot] and after[slot]
            )
            revived_seen.extend(
                f"modelo {modelo.id} {earlier}/{later} {slot[0]} offset {slot[1]}"
                for slot in shared
                if before[slot] and not after[slot]
            )
    assert retired_seen, (
        "no slot anywhere in the bundled corpus is RETIRED into reserved space, so that half of the "
        "occupancy signal can no longer fail and its contribution to the verdict is vacuous"
    )
    assert revived_seen, (
        "no slot anywhere in the bundled corpus is REVIVED out of reserved space, so that half of the "
        "occupancy signal can no longer fail and its contribution to the verdict is vacuous"
    )


def test_every_ejercicio_a_design_names_is_attributed_to_it() -> None:
    """A design naming two ejercicios must be attributed to BOTH.

    ``ejercicio-(\\d{4})`` taken as a first match attributed a two-year design to
    its opening year only, so Modelo 303's 2015-y-2016 and 2019-y-2020 designs
    left 2016 and 2020 claimed by nothing -- years the corpus covers and the
    enumeration reported as unmeasured.

    The emptiness guard is deliberate: the subject of this assertion is a map
    built by globbing a directory, and a glob that matches nothing would satisfy
    every ``for`` below vacuously.
    """
    by_year = _designs_by_year("303")
    assert by_year, "no Modelo 303 design was enumerated at all; the assertions below would be vacuous"
    for year in (2015, 2016, 2019, 2020):
        assert year in by_year, f"{year} is covered by a bundled design but attributed to nothing"


def test_a_year_aeat_split_mid_course_keeps_both_of_its_designs() -> None:
    """AEAT split three Modelo 303 ejercicios mid-course; both halves must survive.

    The year-keyed maps keep the first design by filename sort and discard the
    rest, so a consumer deriving an epoch boundary from "the 2024 design" reads
    an arbitrary half of a year that has two incompatible layouts.

    Counted by CONTENT, not by path: the corpus bundles three of these designs
    twice under names differing only by a truncated extension, and a path count
    would report the duplicate as a second design and pass while proving nothing.
    """
    by_year = _designs_by_year("303")
    assert by_year, "no Modelo 303 design was enumerated at all"
    for year in (2018, 2021, 2024):
        distinct = {path.read_bytes() for path in by_year.get(year, ())}
        assert len(distinct) >= 2, (
            f"{year} should carry two distinct Modelo 303 designs (AEAT split it mid-course) "
            f"but {len(distinct)} distinct payload(s) survived enumeration"
        )


def test_a_mid_split_ejercicio_orders_its_halves_by_declared_coverage_not_by_filename() -> None:
    """The two halves of a mid-split year order on what AEAT declares, never on the filename.

    GATED ON THE ORDERING PROPERTY, not on today's filename-to-year mapping. It asserts
    that a design bounded ABOVE (``hasta``) precedes one bounded BELOW (``desde`` /
    ``a-partir-de``) for the same ejercicio, which is what "covers the earlier periods"
    means. It pins no prefix, no year and no count, so AEAT renumbering its published
    listing cannot break it and no author is trained to bump a table.

    A year whose designs do not all declare a bound must be REPORTED as unorderable
    rather than ordered on a guess. Modelo 303's 2018 pair is the live case.
    """
    ordered, unorderable = _designs_in_publication_order("303")
    assert ordered, "no Modelo 303 design was enumerated at all; the assertions below would be vacuous"

    grouped: dict[int, list[Path]] = {}
    for path in ordered:
        grouped.setdefault(min(_design_years(path.name)), []).append(path)
    multi = {year: paths for year, paths in grouped.items() if len(paths) > 1}
    assert multi, "no ejercicio carries two designs, so this ordering assertion would be vacuous"

    for year, paths in sorted(multi.items()):
        if year in unorderable:
            continue
        starts = [_coverage_start_period(path.name) for path in paths]
        assert starts == sorted(starts), (
            f"ejercicio {year} designs are not in declared-coverage order: {starts}"
        )
        assert len(set(starts)) == len(starts), (
            f"ejercicio {year} has two designs declaring the same coverage start {starts}, "
            "so their order is not determined by what AEAT published"
        )
        # The bounded-above half must come first, which is the direction the whole
        # ordering exists to get right.
        assert "hasta" in paths[0].name.lower(), (
            f"ejercicio {year} sorts {paths[0].name!r} first, but the half covering the "
            "earlier periods is the one AEAT bounds with 'hasta'"
        )

    assert 2018 in unorderable, (
        "Modelo 303's 2018 pair declares no period bound on either half ('ejercicio-2018' "
        "and 'ejercicio-2018-salvo-ultimo-periodo-12m-4t'), so it must be reported as "
        "unorderable rather than silently ordered by filename"
    )


def test_the_added_boxes_attach_to_the_epoch_that_introduced_them() -> None:
    """The eight boxes AEAT added mid-2024 belong to the mid-year boundary, not to 2023/2024.

    THIS IS THE ASSERTION THAT CATCHES THE ORDERING DEFECT, and it exists because a
    count-based one structurally cannot. Three consecutive designs yield two boundaries
    in ANY order, so the boundary COUNT is identical whether the two 2024 halves are
    paired early-then-late or late-then-early. Measured: under filename order the eight
    added boxes attributed to the 2023-to-2024 boundary and the mid-year boundary showed
    only occupancy movement; corrected, the eight attach to the mid-year boundary where
    AEAT introduced them and the 2023 transition shows no box-set change at all.

    A split authored against the wrong attribution puts those boxes in the wrong
    revision, and no offset check, length check or digest would detect it.

    Asserts the DIRECTION, never the tally: "no box-set change" against "some box-set
    change". The eight could become nine at the next publication without touching this.
    """
    ordered, _unorderable = _designs_in_publication_order("303")
    by_start: dict[tuple[int, int], Path] = {}
    for path in ordered:
        year = min(_design_years(path.name))
        by_start[(year, _coverage_start_period(path.name) or 1)] = path
    for key in ((2023, 1), (2024, 1), (2024, 9)):
        assert key in by_start, f"the Modelo 303 design for {key} is absent, so this assertion would be vacuous"

    def numbered(path: Path) -> set[str]:
        found: set[str] = set()
        for sheet in _design_sheets(path):
            for field in sheet.fields:
                boxes = _BOX_MARKER.findall(field.description)
                if boxes:
                    found.add(boxes[-1])
        return found

    across_years = numbered(by_start[(2024, 1)]) - numbered(by_start[(2023, 1)])
    within_2024 = numbered(by_start[(2024, 9)]) - numbered(by_start[(2024, 1)])

    assert not across_years, (
        "the 2023-to-early-2024 transition must introduce NO new numbered box -- boxes "
        f"{sorted(across_years, key=int)} attributed there instead, which is the signature "
        "of the two 2024 halves being paired in the wrong order"
    )
    assert within_2024, (
        "the mid-2024 transition must introduce the numbered boxes AEAT added at periods "
        "09 and 3T, but none attributed there, so the halves are paired in the wrong order"
    )


def test_the_orden_year_in_a_filename_is_not_read_as_a_coverage_year() -> None:
    """``orden-hap-2373-2014-...-ejercicio-2018`` covers 2018, not 2014.

    The negative control for the widened attribution: anchoring on ``ejercicio-``
    rather than scanning for four-digit runs is what keeps a legislative
    instrument's own year out of the coverage map.
    """
    assert _design_years("13-303-orden-hap-2373-2014-de-9-de-diciembre-ejercicio-2018-salvo.xlsx") == (2018,)
    assert _design_years("10-303-orden-hap-2373-2014-ejercicio-2015-y-2016-247-kb-xlsx.xlsx") == (2015, 2016)
    assert _design_years("02-303-ejercicio-2022-y-siguientes-actualizado-27-12-2021.xlsx") == (2022,)
    assert _design_years("07-303-orden-eha-3786-2008-v1-1-36-kb-pdf.pdf") == ()


def test_the_plural_and_range_naming_variants_are_read() -> None:
    """AEAT names an ejercicio four ways and two of them are not two years.

    Matching only the singular ``ejercicio-`` missed 40 of the 209 bundled
    design files across 15 modelos, and reading ``a``/``hasta`` as a pair of
    endpoints drops every year between them. Both failures are silent: an
    unenumerated design is indistinguishable from an absent one.
    """
    # plural, single year
    assert _design_years("01-115-orden-eha-3435-2007-ejercicios-2019-y-siguientes.xlsx") == (2019,)
    # "y" is AND -- two discrete years, nothing between them
    assert _design_years("10-303-ejercicio-2015-y-2016.xlsx") == (2015, 2016)
    # "a" and "hasta" are THROUGH -- an inclusive range
    assert _design_years("02-111-ejercicios-2004-a-2009-49-kb-pdf.pdf") == (2004, 2005, 2006, 2007, 2008, 2009)
    assert _design_years("06-111-ejercicios-2016-hasta-2018.pdf") == (2016, 2017, 2018)
    # the orden year is still never coverage
    assert _design_years("01-111-orden-eha-3127-2009-ejercicios-2019-y-siguientes.xlsx") == (2019,)
