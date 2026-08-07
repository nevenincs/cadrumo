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

ANTI-VACUITY. A parser that cannot read a design returns the same answer as a
design with no divergence, so silence has to be loud: a design file this module
claims to read but extracts nothing from is a FAILURE, not a skip. Without that,
the gate goes green by not looking, which is this instrument's most likely rot
path.

No count is hardcoded. The number of designs, boundaries and shared boxes all
vary as the corpus grows; gating on any of them would encode today and detect
nothing tomorrow.

TWO INDEPENDENT SIGNALS, ONE VERDICT. The box-offset diff sees which boxes moved
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
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition
from .._authority import ValidatedRegistryAuthority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_DESIGN_ROOT_PARTS = ("corpus", "aeat_official", "disenos_registro")

# The extracted design tables render one field per row as
# "order | offset | length | kind | description [box] | ... ".
_BOX_MARKER = re.compile(r"\[(\d{1,4})\]")
_DESIGN_YEAR = re.compile(r"ejercicio-(\d{4})")

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


def _parse_design(path: Path) -> dict[str, int]:
    """box number -> record offset for one extracted design table."""
    table: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
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
        table.setdefault(boxes[-1], offset)
    return table


def _page_lengths(path: Path) -> tuple[str, ...]:
    """The per-page ``TOTAL n POSICIONES`` sequence for one design."""
    return tuple(_PAGE_TOTAL.findall(path.read_text(encoding="utf-8", errors="replace")))


def _page_lengths_for(modelo_id: str) -> dict[int, tuple[str, ...]]:
    """``{design year: page-length sequence}`` for every readable design."""
    directory = _design_dir(modelo_id)
    if not directory.is_dir():
        return {}
    lengths: dict[int, tuple[str, ...]] = {}
    for path in sorted(directory.glob("files/*.extracted.md")):
        matched = _DESIGN_YEAR.search(path.name)
        if matched is None:
            continue
        found = _page_lengths(path)
        if found:
            lengths.setdefault(int(matched.group(1)), found)
    return lengths


def _designs_for(modelo_id: str) -> tuple[dict[int, dict[str, int]], dict[int, str]]:
    """Return ``{design year: {box: offset}}`` and ``{year: filename}`` for unreadable ones.

    A design whose year cannot be read off the filename is excluded from both
    maps: it can neither be compared nor attributed to a revision's span, so
    counting it either way would be a guess.
    """
    directory = _design_dir(modelo_id)
    if not directory.is_dir():
        return {}, {}
    parsed: dict[int, dict[str, int]] = {}
    unreadable: dict[int, str] = {}
    for path in sorted(directory.glob("files/*.extracted.md")):
        matched = _DESIGN_YEAR.search(path.name)
        if matched is None:
            continue
        year = int(matched.group(1))
        table = _parse_design(path)
        if table:
            parsed.setdefault(year, table)
        elif year not in parsed:
            unreadable.setdefault(year, path.name)
    return parsed, unreadable


def _span_years(revision) -> set[int]:  # noqa: ANN001 - registry model, typed at the boundary
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


def _claimed_years(revision, design_years: set[int]) -> set[int]:  # noqa: ANN001
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


def _boundaries_for(modelo_id: str, revision) -> dict[tuple[int, int], list[str]]:  # noqa: ANN001
    """Every re-layout boundary inside one revision's span, keyed year-pair to evidence.

    Both signals contribute to ONE verdict rather than reporting separately,
    because they see overlapping-but-different boundary sets and a reader
    unioning two lists by hand will miss the ones only the weaker signal saw.
    """
    boundaries: dict[tuple[int, int], list[str]] = {}

    designs, _ = _designs_for(modelo_id)
    box_years = sorted(_claimed_years(revision, set(designs)))
    for earlier, later in zip(box_years, box_years[1:]):
        before, after = designs[earlier], designs[later]
        shared = set(before) & set(after)
        moved = sorted(box for box in shared if before[box] != after[box])
        if moved:
            sample = ", ".join(f"[{box}] {before[box]}->{after[box]}" for box in moved[:3])
            boundaries.setdefault((earlier, later), []).append(
                f"{len(moved)} of {len(shared)} shared boxes moved (e.g. {sample})"
            )

    lengths = _page_lengths_for(modelo_id)
    page_years = sorted(_claimed_years(revision, set(lengths)))
    for earlier, later in zip(page_years, page_years[1:]):
        if lengths[earlier] != lengths[later]:
            boundaries.setdefault((earlier, later), []).append(
                f"page lengths differ: {lengths[earlier]} vs {lengths[later]}"
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
            f"{earlier}/{later} ({' + '.join(evidence)})"
            for (earlier, later), evidence in sorted(boundaries.items())
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
