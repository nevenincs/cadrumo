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
parse is persisted across processes by the compiler's own record-design
extraction cache and memoized per process here, so it is paid once per corpus
rather than once per call. That claim was once written here while neither memo
existed: every helper re-entered the extractor per call, which is how this module
reached 403s in one run. Measure before trusting it again. And
it cannot be scoped away: restricting the parse to modelos that actually declare
an export layout removes only ~37% of the files and ~15% of the bytes, because
the largest designs belong to modelos that do export. The cost buys the offsets
and the field occupancy the derivatives do not carry, which is what the box and
retirement signals are made of.

"Once per corpus" still means once per cold cache, and a CI checkout always
starts cold. Read one source at a time, the cold corpus cost about 215s of the
first test's 370s on a workstation, which the 300s per-test ceiling every lane
applies cut off before a verdict; profiled, nearly all of it is pdfplumber
building per-character objects for the PDF designs. The sources are independent
and each is cached under its own key, so the first read now warms every missing
one in parallel through the same extraction (byte-identical entries, measured
across all 219 sources): about 36s for the corpus, about 115s for the whole cold
test, which the lane ceiling covers more than twice over. Re-measure it cold (an
empty ``CADRUMO_DEV_CACHE_ROOT``) when the corpus grows.

SIX INDEPENDENT SIGNALS, ONE VERDICT -- and the occupancy one reports two directions.
This heading has now been wrong three times in the same direction: TWO for as long as
the occupancy signal existed, THREE for as long as the box-SET signal has, and FOUR
for as long as the description-flip signal has, which is worth stating rather than
quietly correcting: a module that miscounts its own instruments invites a reader to act
on the ones it names and miss the rest. It compounded, too -- box-SET membership and
description-flip were both labelled "FOURTH SIGNAL" at their own definitions, an
internal collision nobody using either docstring alone would notice.

The signals, renumbered here rather than left to drift again: (1) box-offset
displacement, (2) page-length / record-count, (3) reserved-space occupancy
retire/revive, (4) box-SET membership -- a box added or removed with nothing
displaced, which the movement check structurally cannot see because it iterates only
the boxes both designs share -- (5) unnumbered-slot description flip, including its
no-separable-leaf branch, and (6) box-FREE position-SET membership -- a field added or
removed at a fixed offset with no bracketed number to key on at all, which (4)
structurally cannot see because its key is the box number itself. Measured directly:
62 of 174 bundled designs carry zero bracketed box numbers anywhere, so (4) never runs
for them and (6) is not a refinement of it but the only membership signal that exists
there.

The box-offset diff sees which boxes moved
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
from datetime import date
from itertools import pairwise
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    split_exercise_revisions,
)
from cadrumo.domain.calculations.registry.tests.revision_span_declaration_support import (
    NON_EJERCICIO_COVERAGE_AXIS,
    OPEN_BOUNDED_ERA_DESIGNS,
)

from .revision_span_boundary_support import (
    DESCRIPTION_ONLY,
    boundaries_for,
    boundary_label,
    compare_design_pair,
    description_flip_evidence,
)
from .revision_span_design_support import (
    BOX_MARKER,
    DESIGN_ROOT_PARTS,
    DESIGN_SUFFIXES,
    authority,
    constant_ejercicio_years,
    content_ejercicio_years,
    coverage_start_period,
    declared_revisions,
    design_coverage_years,
    design_dir,
    design_sheets,
    design_sources,
    designs_by_year,
    designs_in_publication_order,
    layout_authority_receipts,
    occupancy,
    page_lengths,
    parse_design,
    revision_span_design_claimed_years,
    revision_span_design_design_years,
    revision_span_design_filing_revisions,
    sources_by_year,
    title_ejercicio_years,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Five consecutive exercises of the support envelope name the synthetic design filenames; the year
# below the floor stands in for the year of an orden, which is never coverage.
assert len(filing_year_envelope().years) >= 5, (
    "the support envelope must span at least 5 exercises for these synthetic editions"
)
_Y = filing_year_envelope().years[-5:]
_ORDEN = filing_year_envelope().floor - 1


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

    def description_suffix(evidence: tuple[str, ...]) -> str:
        if len(evidence) == 1 and "unnumbered slot(s) re-described" in evidence[0]:
            return " " + DESCRIPTION_ONLY
        return ""

    violations: list[str] = []
    for modelo, revision_id, revision in revision_span_design_filing_revisions():
        boundaries = boundaries_for(modelo.id, revision)
        if not boundaries:
            continue
        detail = "; ".join(
            # A key whose years are EQUAL is a mid-course split. Rendering it as
            # "2024/2024" reads as a typo and hides the finding the design-file keying
            # exists to surface, so it is named for what it is.
            f"{f'{earlier} mid-year' if earlier == later else f'{earlier}/{later}'}"
            # A boundary resting solely on the description-keyed pass is marked, because
            # that pass runs roughly one false positive in three on individual verdicts.
            # A false positive on a boundary other signals already name costs nothing; one
            # that NAMES a boundary alone is the case a reader must judge rather than act
            # on, and it is invisible unless the verdict says so.
            f"{description_suffix(tuple(evidence))}"
            f" ({' + '.join(evidence)})"
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
    for modelo_id in sorted({str(modelo.id) for modelo, _revision_id, _revision in declared_revisions()}):
        sources = dict(sources_by_year(modelo_id))
        for earlier, later in pairwise(sorted(sources)):
            before, after = occupancy(sources[earlier]), occupancy(sources[later])
            shared = set(before) & set(after)
            retired_seen.extend(
                f"modelo {modelo_id} {earlier}/{later} {slot[0]} offset {slot[1]}"
                for slot in shared
                if not before[slot] and after[slot]
            )
            revived_seen.extend(
                f"modelo {modelo_id} {earlier}/{later} {slot[0]} offset {slot[1]}"
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


def _year_in_name(pattern: str, name: str) -> int:
    """Return the year a design filename states under ``pattern``, read independently of the code under test."""
    match = re.search(pattern, name)
    assert match is not None, f"corpus anchor moved: {name}"
    return int(match.group(1))


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
    by_year = designs_by_year("303")
    assert by_year, "no Modelo 303 design was enumerated at all; the assertions below would be vacuous"
    # The two-year designs are found by an independent reading of their filenames.
    named_pairs = [
        match
        for path in sorted((design_dir("303") / "files").iterdir())
        if (match := re.search(r"ejercicio-(\d{4})-y-(\d{4})(?!\d)", path.name))
    ]
    assert named_pairs, "no Modelo 303 design names two ejercicios in its filename; the loop below would be vacuous"
    for match in named_pairs:
        for year in map(int, match.groups()):
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
    by_year = designs_by_year("303")
    assert by_year, "no Modelo 303 design was enumerated at all"
    # A split ejercicio is one that two distinct design payloads each claim, attributed file by file
    # rather than through the year-keyed map under test.
    claimed: dict[int, set[bytes]] = {}
    for path in design_sources("303"):
        for year in design_coverage_years(path):
            claimed.setdefault(year, set()).add(path.read_bytes())
    split_years = sorted(year for year, payloads in claimed.items() if len(payloads) >= 2)
    assert split_years, "no Modelo 303 ejercicio carries two distinct designs, so the assertion below would be vacuous"
    for year in split_years:
        distinct = {path.read_bytes() for path in by_year.get(year, ())}
        assert len(distinct) >= 2, (
            f"{year} should carry two distinct Modelo 303 designs (AEAT split it mid-course) "
            f"but {len(distinct)} distinct payload(s) survived enumeration"
        )


def test_the_box_marker_is_the_registry_canonical_one_and_reads_every_modelo() -> None:
    """This module must not hold its own box-number pattern, and must read every modelo.

    ASSERTS IDENTITY WITH THE CANONICAL DEFINITION, NOT A DIGIT WIDTH. Pinning "five
    digits" here would recreate the defect one modelo later and would train the next
    author to bump a literal; worse, it would make this module an independent authority
    on the pattern again, which is what went wrong. The durable property is that there is
    ONE definition and this module uses it.

    The concrete failure it closes: this module's private copy was capped at four digits
    while Modelo 200 numbers its boxes with five, so the box-offset and box-set signals
    read 23 of that modelo's 5561 bracketed tokens and reported nothing amiss. The
    canonical definition had already been widened to five for exactly this reason, and
    its own docstring records the same failure shape -- a matchless sweep reading as
    "0 casillas, 0 gap" for 36 of 38 revisions.

    The second assertion is the one that would have caught it: every modelo whose designs
    bracket a box number at all must yield boxes here. A modelo that parses designs but
    keys zero boxes is not clean, it is unread, and it reports identically to a modelo
    with nothing to find.
    """
    from .revision_span_design_support import CASILLA_TAG_RE

    assert BOX_MARKER is CASILLA_TAG_RE, (
        "this module re-declared the bracketed box-number pattern instead of using the registry's "
        "canonical one; two definitions of one concept is how the four-digit cap survived while "
        "production already read five"
    )

    unread: list[str] = []
    measured = 0
    for modelo_id in sorted({modelo.id for modelo, _, _ in revision_span_design_filing_revisions()}):
        ordered, _unorderable = designs_in_publication_order(modelo_id)
        for path in ordered:
            bracketed = any(
                re.search(r"\[\d+\]", field.description) for sheet in design_sheets(path) for field in sheet.fields
            )
            if not bracketed:
                continue
            measured += 1
            if not parse_design(path):
                unread.append(f"modelo {modelo_id} design {path.name!r}")
    assert measured, "no bundled design brackets a box number at all; the assertion below would be vacuous"
    assert not unread, (
        "these designs bracket box numbers that this module's marker does not match, so every box "
        "signal is silently switched off for them and reports identically to a design with no "
        "divergence:\n  " + "\n  ".join(sorted(set(unread)))
    )


def test_a_boundary_only_the_description_pass_sees_is_reported_and_marked_for_review() -> None:
    """The least precise signal must still reach the verdict, and must say when it is alone.

    A slot carrying no bracketed box number can change what it declares while keeping its
    offset and its width. Modelo 303 does exactly that between the 2024 halves, where a
    one-byte flag and the reference beside it stop declaring a complementaria and start
    declaring an autoliquidacion rectificativa. No offset check, length check, occupancy
    check or digest detects it, and the box-number key structurally cannot.

    TWO PROPERTIES, NEITHER A COUNT. First, the pass must have a positive case somewhere,
    or it has become unfalsifiable and its silence means nothing. Second, every boundary
    resting SOLELY on it must be marked in the verdict text.

    The marking is the honest part. This pass runs roughly one false positive in three on
    individual verdicts -- a measured example survives at Modelo 303 2014/2015, where a
    leaf goes from ``regimen simplificado`` to ``Regimen Simplificado (RS)``, a rewording
    rather than a meaning change. That costs nothing there, because three other signals
    already name that boundary and a false positive on an already-named boundary adds
    noise to the evidence rather than a wrong split. The case a reader must judge is a
    boundary this pass names ALONE, and that case is invisible unless the verdict says so.
    """
    positive: list[str] = []
    alone: list[tuple[str, str, tuple[int, int]]] = []
    for modelo_id in sorted({str(modelo.id) for modelo, _revision_id, _revision in declared_revisions()}):
        ordered, _unorderable = designs_in_publication_order(modelo_id)
        for earlier, later in pairwise(ordered):
            if bool(description_flip_evidence(earlier, later)):
                positive.append(f"modelo {modelo_id} {boundary_label(earlier, later)}")
    for modelo, revision_id, revision in declared_revisions():
        for key, evidence in boundaries_for(modelo.id, revision).items():
            if len(evidence) == 1 and "unnumbered slot(s) re-described" in evidence[0]:
                alone.append((modelo.id, revision_id, key))

    assert positive, (
        "no design pair anywhere re-describes an unnumbered slot at an unchanged position and "
        "width, so this pass can no longer fail and its silence about the complementaria-to-"
        "rectificativa class means nothing"
    )

    for modelo_id, revision_id, key in alone:
        modelo, revision = next(
            (candidate, current)
            for candidate, current_id, current in declared_revisions()
            if candidate.id == modelo_id and current_id == revision_id
        )
        boundaries = boundaries_for(modelo.id, revision)
        rendered = "; ".join(
            f"{f'{a} mid-year' if a == b else f'{a}/{b}'}"
            f"{' ' + DESCRIPTION_ONLY if len(ev) == 1 and 'unnumbered slot(s) re-described' in ev[0] else ''}"
            for (a, b), ev in sorted(boundaries.items())
        )
        assert DESCRIPTION_ONLY in rendered, (
            f"modelo {modelo_id} revision {revision_id!r} boundary {key} rests only on the "
            "description-keyed pass, which runs roughly one false positive in three, and the "
            "verdict does not mark it as such -- a reader cannot tell which boundaries to judge "
            "rather than act on"
        )


def _era_ordered_registered_designs(modelo_id: str) -> tuple[Path, ...]:
    """One path per REGISTERED design of a modelo, ordered by the era it declares.

    Deliberately not ``_design_sources``, which answers a different question. That
    walk returns every design FILE, so a design AEAT ships as both ``.xls`` and
    ``.xlsx`` appears twice, and it sorts by filename -- AEAT numbers newest-first
    -- so consecutive entries run backwards through time. Pairing it produces two
    kinds of nonsense: a design compared against its own format twin, and a later
    design read as the earlier one.

    Keyed on the SOURCE ID, which is one per design regardless of how many
    renderings the corpus holds, and ordered on ``applies_from``, which the
    catalogue states rather than a filename implies.
    """
    entries = []
    for source in authority().catalogues.sources.values():
        if getattr(source, "kind", None) != "record_design" or source.applies_from is None:
            continue
        posix = Path(str(source.corpus_path)).as_posix()
        marker = "disenos_registro/modelo_"
        if marker not in posix:
            continue
        if posix.split(marker, 1)[1].split("/", 1)[0] != modelo_id:
            continue
        path = bundled_path() / source.corpus_path
        if path.is_file() and path.suffix.lower() in DESIGN_SUFFIXES:
            entries.append((source.applies_from, source.id, path))
    return tuple(path for _, _, path in sorted(entries))


def _membership_only_design_pairs() -> tuple[tuple[str, Path, Path], ...]:
    """Consecutive registered designs whose ONLY difference is which boxes exist."""
    found: list[tuple[str, Path, Path]] = []
    for modelo in authority().modelos:
        for earlier, later in pairwise(_era_ordered_registered_designs(str(modelo.id))):
            before_boxes, after_boxes = parse_design(earlier), parse_design(later)
            if not before_boxes or not after_boxes:
                continue
            shared = set(before_boxes) & set(after_boxes)
            if any(before_boxes[box] != after_boxes[box] for box in shared):
                continue
            if set(before_boxes) == set(after_boxes):
                continue
            before_lengths, after_lengths = page_lengths(earlier), page_lengths(later)
            if before_lengths and after_lengths and before_lengths != after_lengths:
                continue
            before_occupancy, after_occupancy = occupancy(earlier), occupancy(later)
            if any(
                before_occupancy[slot] != after_occupancy[slot] for slot in set(before_occupancy) & set(after_occupancy)
            ):
                continue
            found.append((str(modelo.id), earlier, later))
    return tuple(found)


def test_a_box_added_or_removed_without_movement_reaches_the_verdict() -> None:
    """A boundary only the box-SET comparison can see must reach the failure text.

    The displacement check iterates the boxes two designs SHARE, so a box present in one
    and absent in the other falls outside its loop. Measured on Modelo 390, that left a
    whole class unreported: 2015 to 2016 adds six boxes and 2016 to 2017 removes twenty,
    both with zero movement, no readable page-length difference and no occupancy
    transition, so no signal in this module named either boundary.

    GATED ON THE MEMBERSHIP PROPERTY, never on the numbers. It does not assert six added
    or twenty removed -- those are today's corpus, and pinning them would train the next
    author to bump two constants and would then detect nothing. The durable property is
    that a pair whose ONLY difference is which boxes exist still produces a boundary.

    THE TWO SIDES ARE DERIVED INDEPENDENTLY, and that is deliberate rather than
    incidental. Availability is measured straight from the parsed designs; the reported
    side comes from the verdict builder. Deriving both from the verdict builder is the
    shape that has already caught this module's author twice: under mutation such a test
    reds on its own vacuity guard, which proves the function changed and nothing about
    whether the signal works.
        WHY THE PAIRS COME FROM THE CATALOGUE AND NOT FROM REVISIONS. This walked the
    designs each REVISION claims, which made its liveness depend on how revisions
    happen to be carved. As the spanning revisions were split, that
    population fell to two across the whole tree, and the assertion below began
    failing for want of an example rather than for want of the signal. The
    property being proved is about the COMPARATOR, so it is now measured over
    consecutive registered designs, a population that does not move when a
    revision is renamed.

    BOX KEYS ARE COMPARED RAW, deliberately. Stripping leading zeros looks like an
    obvious normalisation and is wrong here: 26 bundled designs declare ``001``
    and ``1`` as DISTINCT boxes, so collapsing them would merge real boxes and
    hide the very membership changes this signal exists to see.
    """
    membership_only = _membership_only_design_pairs()

    assert membership_only, (
        "no registered design pair differs ONLY in which boxes it declares, so this assertion "
        "would be vacuous -- the corpus that made the membership signal necessary has changed"
    )
    for modelo_id, earlier, later in membership_only:
        evidence = compare_design_pair(earlier, later)
        assert any("box SET changed" in item for item in evidence), (
            f"modelo {modelo_id}: {earlier.name} and {later.name} differ only in which boxes they "
            "declare -- no box moved, no page length changed, no slot changed occupancy -- and the "
            "comparison names no membership signal, so a box added or removed is invisible"
        )


def test_no_bundled_design_file_disappears_from_the_inventory() -> None:
    """A design the corpus holds but the inventory does not enumerate must FAIL, not vanish.

    THE FAILURE THIS CLOSES IS SILENT PROGRESS. Every other guard in this module asks
    whether the designs it was given disagree. None of them asks whether it was given
    all of them. Withhold a design file and the boundary it formed simply stops being
    reported: the verdict names fewer violations, which reads as a split landing rather
    than as an instrument going blind. That is the most dangerous direction for this
    gate, because a shorter verdict would then reward the gate's own blindness.

    THE ENUMERATION IS DERIVED INDEPENDENTLY, which is what makes the check possible at
    all. It globs the corpus directory itself rather than asking the inventory under
    test what exists -- a guard built on ``_design_sources`` would be blind to
    ``_design_sources`` dropping a file, which is precisely the defect. Two derivations
    of one fact, deliberately, in the one place where sharing an implementation destroys
    the check.

    GATED ON THE PROPERTY: every accepted-suffix file on disk is either enumerated, or
    named as unparseable by the sibling coverage guard. No count is pinned, so the
    corpus can grow without touching this.
    """
    missing: list[str] = []
    seen_any = 0
    # DELIBERATELY DOES NOT LOAD THE REGISTRY AUTHORITY. Whether a bundled file is
    # enumerated is a fact about the corpus and the inventory; nothing about it depends
    # on a legal catalogue validating or a revision declaring an export layout. An
    # earlier draft derived its modelo list from the exporting revisions and was taken
    # down by an unrelated peer condition -- a legal reference whose corpus sidecar had
    # not been generated yet. That is a blind spot rather than bad luck: a guard that
    # cannot run while another part of the tree is mid-edit is unavailable exactly when
    # a withheld file is most likely to slip in unnoticed.
    design_root = bundled_path(*DESIGN_ROOT_PARTS)
    for directory in scan_directory(design_root, pattern="modelo_*", select=DirectoryEntryKind.DIRECTORIES):
        modelo_id = directory.name.removeprefix("modelo_")
        # Recursive, matching _design_sources. The two derivations stayed independent
        # in their SET logic while sharing one glob SHAPE, so a design outside
        # ``files/`` was invisible to the inventory AND to the guard that exists to
        # catch the inventory dropping a file. Two derivations of one fact protect
        # nothing where both inherit the same blind spot.
        on_disk = {
            path
            for path in scan_directory(directory, recursive=True, select=DirectoryEntryKind.FILES)
            if path.suffix.lower() in DESIGN_SUFFIXES
        }
        if not on_disk:
            continue
        seen_any += len(on_disk)
        enumerated = set(design_sources(modelo_id))
        missing.extend(f"modelo {modelo_id} design {path.name!r}" for path in sorted(on_disk - enumerated))
    assert seen_any, "no bundled design file was found on disk at all; the corpus path has moved"
    assert not missing, (
        "these design files exist in the bundled corpus but the inventory does not enumerate them, so "
        "every boundary they form is silently absent from the verdict and the gate getting shorter "
        "would read as progress:\n  " + "\n  ".join(missing)
    )


def test_the_verdict_names_a_mid_course_boundary_where_aeat_split_an_ejercicio() -> None:
    """A boundary INSIDE one ejercicio must reach the verdict, not just the ones between years.

    This is what the design-file keying buys, and it is the assertion that makes the
    keying provable. The per-signal inventories this replaced kept ONE design per year
    through a ``setdefault`` over a filename sort, so the second half of a mid-course
    ejercicio was discarded before any comparison ran and a boundary inside that year
    could not be reported by any signal. The gate's silence about it was therefore not
    evidence of anything -- and silence that looks like a clean result is this
    instrument's worst failure mode, because a split authored on it would leave the
    boundary live.

    GATED ON THE PROPERTY: the verdict must contain at least one boundary whose two
    years are EQUAL, which is what a mid-course split looks like once the inventory can
    see both halves. It pins no year, no modelo and no count, so it survives AEAT
    splitting a different ejercicio and it cannot be satisfied by a stale constant.

    Guarded against vacuity from the other side too: it first confirms the corpus
    actually HOLDS a mid-split ejercicio inside a gated span, so a corpus that lost one
    fails loudly here instead of passing by having nothing to find.
    """
    mid_split_available: list[str] = []
    mid_course_reported: list[str] = []
    for modelo, revision_id, revision in revision_span_design_filing_revisions():
        # The availability side is derived from the raw publication-order enumeration
        # rather than from the span helper the verdict uses. Deriving both sides from one
        # function makes this test notice only that the function changed, so a defect in
        # it would red the vacuity guard and never reach the assertion that matters.
        ordered, _unorderable = designs_in_publication_order(modelo.id)
        claimed_years = revision_span_design_claimed_years(
            revision, {year for path in ordered for year in design_coverage_years(path)}
        )
        by_year: dict[int, int] = {}
        for path in ordered:
            opening = min(design_coverage_years(path))
            if set(design_coverage_years(path)) & claimed_years:
                by_year[opening] = by_year.get(opening, 0) + 1
        mid_split_available.extend(
            f"modelo {modelo.id} revision {revision_id!r} ejercicio {year}"
            for year, count in sorted(by_year.items())
            if count > 1
        )
        mid_course_reported.extend(
            f"modelo {modelo.id} revision {revision_id!r} ejercicio {earlier}"
            for earlier, later in boundaries_for(modelo.id, revision)
            if earlier == later
        )

    assert mid_split_available, (
        "no gated revision claims an ejercicio carrying two designs, so this assertion would be "
        "vacuous -- the corpus that made the design-file keying necessary has changed"
    )

    # PROVEN ON A CONSTRUCTED SPAN, because no DECLARED revision spans a
    # mid-course boundary any more and that is the tree being right rather than
    # the instrument being blind. Every mid-course split AEAT published is now
    # partitioned into halves, and a half scoped to its own months claims only
    # the design it cites, so it reports nothing -- correctly.
    #
    # Widening one of those halves back across the whole ejercicio reconstructs
    # the case the keying exists for. If an inventory ever returns to keeping one
    # design per year, this reports no boundary and fails, which is the same
    # protection the original assertion gave when the tree still carried a
    # spanning revision.
    widened_reported: list[str] = []
    for modelo, revision_id, revision in revision_span_design_filing_revisions():
        if revision.valid_to is None:
            continue
        if revision.valid_from.year != revision.valid_to.year:
            continue
        year = revision.valid_from.year
        widened = revision.model_copy(
            update={
                "valid_from": date(year, 1, 1),
                "valid_to": date(year, 12, 31),
                "period_selector": revision.period_selector.model_copy(update={"periods": ()}),
            },
        )
        widened_reported.extend(
            f"modelo {modelo.id} revision {revision_id!r} ejercicio {earlier}"
            for earlier, later in boundaries_for(modelo.id, widened)
            if earlier == later
        )

    assert widened_reported, (
        "the corpus holds a mid-course split inside a gated span "
        f"({sorted(set(mid_split_available))}) but widening a revision across the whole ejercicio "
        "still names no boundary inside a single year, so an inventory is back to keeping one "
        "design per year and its silence about that boundary means nothing"
    )
    assert not mid_course_reported, "a DECLARED revision spans a mid-course boundary: " + ", ".join(
        sorted(set(mid_course_reported))
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
    ordered, unorderable = designs_in_publication_order("303")
    assert ordered, "no Modelo 303 design was enumerated at all; the assertions below would be vacuous"

    grouped: dict[int, list[Path]] = {}
    for path in ordered:
        grouped.setdefault(min(design_coverage_years(path)), []).append(path)
    multi = {year: paths for year, paths in grouped.items() if len(paths) > 1}
    assert multi, "no ejercicio carries two designs, so this ordering assertion would be vacuous"

    for year, paths in sorted(multi.items()):
        if year in unorderable:
            continue
        declared = [coverage_start_period(path.name) for path in paths]
        # A year reported orderable must have a bound on every member; otherwise the
        # unorderable report is itself wrong and the comparisons below are meaningless.
        assert all(start is not None for start in declared), (
            f"ejercicio {year} was reported orderable but a design declares no coverage bound: "
            f"{[path.name for path in paths]}"
        )
        starts = [start for start in declared if start is not None]
        assert starts == sorted(starts), f"ejercicio {year} designs are not in declared-coverage order: {starts}"
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

    unbounded = {
        year for year, paths in multi.items() if any(coverage_start_period(path.name) is None for path in paths)
    }
    assert unbounded, "every Modelo 303 pair declares its period bounds, so the unorderable report is untested"
    assert unbounded <= set(unorderable), (
        f"ejercicio(s) {sorted(unbounded - set(unorderable))} have a pair declaring no period bound on a half, "
        "so each must be reported as unorderable rather than silently ordered by filename"
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

    def numbered(path: Path) -> set[str]:
        found: set[str] = set()
        for sheet in design_sheets(path):
            for field in sheet.fields:
                boxes = BOX_MARKER.findall(field.description)
                if boxes:
                    found.add(boxes[-1])
        return found

    # Walk the ORDERED sequence adjacently, exactly as a boundary-deriving consumer
    # does. Re-deriving the order here from the coverage helper would make this test
    # insensitive to the ordering function it exists to guard.
    ordered, _unorderable = designs_in_publication_order("303")
    # The mid-year split is the authored revision pair serving the 08/2T and 09/3T periods of one
    # exercise; the transition into it starts from the exercise authored just before.
    early, _late = split_exercise_revisions("303", early_period="2T", late_period="3T")
    authored = authored_revisions("303")
    split_year = early.valid_from.year
    previous_year = authored[authored.index(early) - 1].valid_from.year
    window = [path for path in ordered if min(design_coverage_years(path)) >= previous_year]
    assert len(window) >= 3, (
        f"fewer than three Modelo 303 designs from {previous_year} on; this assertion would be vacuous"
    )

    introduced: dict[str, set[str]] = {}
    for earlier, later in pairwise(window):
        left, right = max(design_coverage_years(earlier)), min(design_coverage_years(later))
        label = f"{left} mid-year" if left == right else f"{left}/{right}"
        introduced[label] = numbered(later) - numbered(earlier)

    transition, mid_year = f"{previous_year}/{split_year}", f"{split_year} mid-year"
    for label in (transition, mid_year):
        assert label in introduced, (
            f"the {label} boundary is absent from the ordered walk, so this assertion would be vacuous"
        )

    assert not introduced[transition], (
        f"the {previous_year}-to-early-{split_year} transition must introduce NO new numbered box -- boxes "
        f"{sorted(introduced[transition], key=int)} attributed there instead, which is the "
        f"signature of the two {split_year} halves being paired in the wrong order"
    )
    assert introduced[mid_year], (
        f"the mid-{split_year} transition must introduce the numbered boxes AEAT added at periods "
        "09 and 3T, but none attributed there, so the halves are paired in the wrong order"
    )


def test_the_orden_year_in_a_filename_is_not_read_as_a_coverage_year() -> None:
    """``orden-hap-2373-2014-...-ejercicio-2018`` covers 2018, not 2014.

    The negative control for the widened attribution: anchoring on ``ejercicio-``
    rather than scanning for four-digit runs is what keeps a legislative
    instrument's own year out of the coverage map.
    """
    assert revision_span_design_design_years(
        f"13-303-orden-hap-2373-{_ORDEN}-de-9-de-diciembre-ejercicio-{_Y[2]}-salvo.xlsx"
    ) == (_Y[2],)
    assert revision_span_design_design_years(
        f"10-303-orden-hap-2373-{_ORDEN}-ejercicio-{_Y[0]}-y-{_Y[1]}-247-kb-xlsx.xlsx"
    ) == (_Y[0], _Y[1])
    assert revision_span_design_design_years(
        f"02-303-ejercicio-{_Y[3]}-y-siguientes-actualizado-27-12-{_ORDEN}.xlsx"
    ) == (_Y[3],)
    assert revision_span_design_design_years(f"07-303-orden-eha-3786-{_ORDEN}-v1-1-36-kb-pdf.pdf") == ()


def test_the_plural_and_range_naming_variants_are_read() -> None:
    """AEAT names an ejercicio four ways and two of them are not two years.

    Matching only the singular ``ejercicio-`` missed 40 of the 209 bundled
    design files across 15 modelos, and reading ``a``/``hasta`` as a pair of
    endpoints drops every year between them. Both failures are silent: an
    unenumerated design is indistinguishable from an absent one.
    """
    # plural, single year
    assert revision_span_design_design_years(
        f"01-115-orden-eha-3435-{_ORDEN}-ejercicios-{_Y[3]}-y-siguientes.xlsx"
    ) == (_Y[3],)
    # "y" is AND -- two discrete years, nothing between them
    assert revision_span_design_design_years(f"10-303-ejercicio-{_Y[0]}-y-{_Y[1]}.xlsx") == (_Y[0], _Y[1])
    # "a" and "hasta" are THROUGH -- an inclusive range
    assert revision_span_design_design_years(f"02-111-ejercicios-{_Y[0]}-a-{_Y[4]}-49-kb-pdf.pdf") == _Y
    assert revision_span_design_design_years(f"06-111-ejercicios-{_Y[0]}-hasta-{_Y[2]}.pdf") == _Y[:3]
    # the orden year is still never coverage
    assert revision_span_design_design_years(
        f"01-111-orden-eha-3127-{_ORDEN}-ejercicios-{_Y[3]}-y-siguientes.xlsx"
    ) == (_Y[3],)


def test_a_period_qualified_designation_yields_its_ejercicio() -> None:
    """A pago-fraccionado design names its coverage by PERIOD, and that is still coverage.

    The year-follows-``ejercicio-`` anchor misses these because a period token sits
    between the word and the digits, so three Modelo 202 designs enumerated as
    covering nothing. Widening to the period token is not the orden-year
    relaxation: the anchor is still an explicit coverage designation, which is why
    the negative controls below keep passing.
    """
    assert revision_span_design_design_years(
        f"07-202-orden-hap-1552-{_ORDEN}-ejercicio-2p-y-3p-{_Y[1]}-128-kb-xlsx.xlsx"
    ) == (_Y[1],)
    assert revision_span_design_design_years(
        f"09-202-orden-hap-2214-{_ORDEN}-ejercicios-3p-{_Y[0]}-y-{_Y[1]}-46-kb-pdf.pdf"
    ) == (_Y[0], _Y[1])
    assert revision_span_design_design_years(f"10-202-orden-hap-523-{_ORDEN}-1p-{_Y[1]}-124-kb-xlsx.xlsx") == (_Y[1],)
    # An orden number carries no period token, so it still supplies no year, and a
    # period-scoped span with no year attached still enumerates nothing rather than
    # borrowing the update year beside it.
    assert (
        revision_span_design_design_years(f"14-202-orden-eha-664-{_ORDEN}-adaptada-a-la-ultima-normativa-vigente.pdf")
        == ()
    )
    assert revision_span_design_design_years(f"01-763-desde-{_Y[0]}-4t-y-siguientes-actualizado-en-{_Y[1]}.xlsx") == ()


def test_a_design_title_is_read_as_coverage_where_the_filename_states_nothing() -> None:
    """The design's own title states the ejercicio the filename withholds.

    THE POSITIVE HALF of the attribution bite proof. Modelo 180's 2014-orden design
    and Modelo 303's 2008-orden design both state their ejercicio in their heading,
    and neither filename carries one, so before this the pair entered no map at all
    and their modelo's ``boundaries`` was empty for want of anything to compare
    rather than for want of a boundary.
    """
    m180 = design_dir("180") / "files" / "03-180-orden-hap-1732-2014-de-24-de-septiembre-105-kb-pdf.pdf"
    m303 = design_dir("303") / "files" / "07-303-orden-eha-3786-2008-v1-1-36-kb-pdf.pdf"
    for path in (m180, m303):
        assert path.is_file(), f"corpus anchor moved: {path}"

    # The filename rule refuses both, exactly as it should.
    assert revision_span_design_design_years(m180.name) == ()
    assert revision_span_design_design_years(m303.name) == ()
    # The document states what the filename does not, and the orden year is NOT it:
    # 2014 -> 2021 is a seven-year divergence, which is why the filename cannot be
    # trusted to supply it by proximity or by sequence.
    assert title_ejercicio_years(m180) == (2021,)
    assert title_ejercicio_years(m303) == (2009,)
    assert design_coverage_years(m180) == (2021,)
    assert design_coverage_years(m303) == (2009,)


def test_a_filename_carrying_only_an_orden_year_is_still_attributed_nothing() -> None:
    """THE NEGATIVE HALF: a design whose content is silent stays unattributed.

    The attribution reads the document, so a document that asserts no ejercicio must
    yield nothing rather than falling back on the orden year the filename carries.
    Modelo 840's design is the case: its filename offers ``2003`` and its content
    offers nothing, and inferring 2003 from the orden is the precise regression the
    filename rule exists to prevent.
    """
    m840 = design_dir("840") / "files" / "01-840-orden-hac-2572-2003-99-kb-pdf.pdf"
    m720 = design_dir("720") / "files" / "01-720-599-kb-pdf.pdf"
    for path in (m840, m720):
        assert path.is_file(), f"corpus anchor moved: {path}"
    for path in (m840, m720):
        assert revision_span_design_design_years(path.name) == ()
        assert content_ejercicio_years(path) == ()
        assert design_coverage_years(path) == ()


def test_a_constant_ejercicio_slot_is_read_and_a_filer_supplied_one_is_not() -> None:
    """The second content signal, with the discrimination that makes it safe.

    Modelo 714's 2025 design states no ejercicio in its heading and fixes one in a
    field: ``Ejercicio | Constante 2025``. Reading it recovers a design the title
    rule alone leaves unattributed.

    The negative control is the point. Modelo 303 declares an ``Ejercicio de devengo``
    slot on every one of its designs and fixes NONE of them, because that is a value
    the filer writes. A rule keyed on the word alone would attribute all six M303
    designs to whatever year sat beside that slot; keyed on the constant, it
    attributes none of them and their filenames continue to carry the coverage.
    """
    # The anchors are the newest design files of each name shape; the year each states is read
    # independently from its filename.
    m714 = max((design_dir("714") / "files").glob("DR714_*.xls"))
    m714_year = _year_in_name(r"DR714_(\d{4})\.xls", m714.name)
    assert m714.is_file(), f"corpus anchor moved: {m714}"
    assert revision_span_design_design_years(m714.name) == ()
    assert title_ejercicio_years(m714) == ()
    assert constant_ejercicio_years(m714) == (m714_year,)
    assert design_coverage_years(m714) == (m714_year,)

    m303 = max((design_dir("303") / "files").glob("01-303-ejercicio-*-y-siguientes-*.xlsx"))
    m303_year = _year_in_name(r"ejercicio-(\d{4})-y-siguientes", m303.name)
    assert m303.is_file(), f"corpus anchor moved: {m303}"
    assert constant_ejercicio_years(m303) == (), (
        "Modelo 303's 'Ejercicio de devengo' slot is filled by the FILER, so reading it as "
        "the design's own coverage would attribute the design to an arbitrary year"
    )
    assert design_coverage_years(m303) == (m303_year,)


def test_a_title_naming_one_ejercicio_does_not_shorten_a_filename_naming_a_span() -> None:
    """Content ADDS coverage and never removes it -- the regression proof for the union.

    A design published for one ejercicio and applying through several heads its
    first page with the opening year alone: Modelo 130's
    ``ejercicios-2009-a-2014`` design states ``Ejercicio 2009`` and nothing more.
    Reading the title as the design's coverage rather than as one of its years
    discards 2010 through 2014, and the loss is silent -- those years then form no
    boundary, and a verdict with fewer boundaries reads as a split having landed.

    Four designs in the corpus have this shape and twelve design-years ride on it.
    Pinned on the property (nothing is lost) rather than on the year lists, so it
    survives AEAT republishing any of them.
    """
    spans = {
        "130": "04-130-orden-eha-580-2009-ejercicios-2009-a-2014-36-kb-pdf.pdf",
        "131": "08-131-orden-eha-580-2009-ejercicios-2009-a-2014-26-kb-pdf.pdf",
    }
    checked = 0
    for modelo_id, filename in spans.items():
        path = design_dir(modelo_id) / "files" / filename
        assert path.is_file(), f"corpus anchor moved: {path}"
        filename_years = set(revision_span_design_design_years(path.name))
        content_years = set(content_ejercicio_years(path))
        assert len(filename_years) > 1, f"{filename!r} no longer names a span; pick another anchor"
        assert content_years, f"{filename!r} no longer states an ejercicio in its content; pick another anchor"
        assert content_years < filename_years, (
            f"{filename!r} no longer has the shape this guards -- its content used to name FEWER "
            "years than its filename, which is what makes preferring the content lossy"
        )
        assert filename_years <= set(design_coverage_years(path)), (
            f"attribution DROPPED years for {filename!r}: filename claims {sorted(filename_years)} "
            f"but coverage resolved to {list(design_coverage_years(path))}. A content signal may "
            "add coverage; it may never take it away."
        )
        checked += 1
    assert checked == len(spans)


def test_a_design_title_never_contradicts_a_trustworthy_filename_year() -> None:
    """Where BOTH signals speak, they must agree -- the title never wins silently.

    This is what makes ranking the title above the filename safe. A bare precedence
    rule would resolve a conflict by preferring one source and saying nothing, which
    would bury exactly the divergence that established the precedence in the first
    place.

    EXERCISED, NOT VACUOUS, and the distinction matters because this module elsewhere
    refuses to ship a signal with no observations. Seventeen designs carry both a
    trustworthy ``ejercicio-`` filename token and a title ejercicio, and all
    seventeen agree; the assertion below runs seventeen real comparisons and finds
    no conflict. That is a live check with a clean result, not a check with nothing
    to look at -- so the population itself is asserted non-empty, and a corpus that
    lost every overlapping design fails here rather than passing by having nothing
    to compare.
    """
    compared = 0
    conflicts: list[str] = []
    design_root = bundled_path(*DESIGN_ROOT_PARTS)
    for directory in scan_directory(design_root, pattern="modelo_*", select=DirectoryEntryKind.DIRECTORIES):
        modelo_id = directory.name.removeprefix("modelo_")
        for path in design_sources(modelo_id):
            filename_years = set(revision_span_design_design_years(path.name))
            content_years = set(content_ejercicio_years(path))
            if not filename_years or not content_years:
                continue
            compared += 1
            if not filename_years & content_years:
                conflicts.append(
                    f"modelo {modelo_id} design {path.name!r}: filename claims "
                    f"{sorted(filename_years)} but the design itself states {sorted(content_years)}"
                )
    assert compared, (
        "no bundled design carries BOTH a filename ejercicio and a title ejercicio, so the "
        "title-over-filename precedence is unchecked. It is ranked higher on the strength of "
        "this comparison; with nothing to compare, the ranking is an unverified assumption."
    )
    assert not conflicts, (
        "a design's title and its filename disagree about which ejercicio it covers. The title "
        "is ranked higher, so the coverage maps have silently taken it -- resolve which is right "
        "rather than letting the precedence decide:\n  " + "\n  ".join(conflicts)
    )


def test_a_bundled_design_whose_coverage_cannot_be_read_is_reported_unmeasured() -> None:
    """A design nothing can attribute is UNMEASURED, never absorbed under a guess.

    Same discipline this module already applies to a design it cannot PARSE: a file
    that enters no map is indistinguishable from a file that does not exist, and the
    verdict getting shorter reads as progress. Attribution is the second way a design
    can vanish, and until now it vanished without saying so -- twenty modelos have
    every bundled design named for an orden rather than an ejercicio, so their
    ``boundaries`` was empty because nothing was ever compared, not because nothing
    diverged.

    THE TEMPTATION THIS REFUSES. Reading the title recovers most of them, and the
    near-miss makes the rest look inferrable: an orden-named design plausibly runs
    from promulgation until superseded, so the sequence could supply what the content
    withholds. Measured, that inference is wrong --
    ``03-180-orden-hap-1732-2014-de-24-de-septiembre.pdf`` states ``Ejercicio 2021``,
    seven years from its orden -- so the remainder is genuinely unknown rather than
    merely unstated, and a guess here would put a filing year under another year's
    layout.

    Several of these are not defects at all and are named anyway: Modelo 036 is
    scoped by an in-force DATE and Modelo 210 by a devengo span, so they have real
    coverage expressed on an axis that is not an ejercicio. Enumerating those into
    years would invent years for the same reason ``y-siguientes`` is not expanded.
    Being visible as unattributed is the correct outcome for them; being silently
    absent is not.
    """
    unattributed: list[str] = []
    attributed = 0
    filing_revisions = revision_span_design_filing_revisions()
    filing_modelos = {modelo.id for modelo, _revision_id, _revision in filing_revisions}
    cited_design_sources = {
        str(source.corpus_path): source
        for _modelo, _revision_id, revision in filing_revisions
        for source in layout_authority_receipts(_modelo.id, revision)
        if source.kind == "record_design"
    }
    design_root = bundled_path(*DESIGN_ROOT_PARTS)
    for directory in scan_directory(design_root, pattern="modelo_*", select=DirectoryEntryKind.DIRECTORIES):
        modelo_id = directory.name.removeprefix("modelo_")
        if modelo_id not in filing_modelos:
            continue
        for path in design_sources(modelo_id):
            relative = path.relative_to(bundled_path()).as_posix()
            source_receipt = cited_design_sources.get(relative)
            if source_receipt is None:
                continue
            if design_coverage_years(path):
                attributed += 1
                continue
            if source_receipt.record_design_epoch is not None:
                attributed += 1
                continue  # catalogue receipt states the epoch the filename omits
            if (modelo_id, path.name) in NON_EJERCICIO_COVERAGE_AXIS:
                continue  # coverage stated on a declared non-ejercicio axis
            if (modelo_id, path.name) in OPEN_BOUNDED_ERA_DESIGNS:
                continue  # era stated, but open on one side and so not enumerable
            unattributed.append(f"modelo {modelo_id} design {path.name!r}")
    assert attributed, "no bundled design could be attributed to any year at all; attribution has broken"
    assert not unattributed, (
        "these bundled designs state no ejercicio in their filename OR their own title, so they "
        "enter no comparison and this module's silence about the years they cover means nothing. "
        "They are UNMEASURED, not clean -- attribute them from a source that actually says, or "
        "record why the design has no ejercicio to state:\n  " + "\n  ".join(unattributed)
    )
