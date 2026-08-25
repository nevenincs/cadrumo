"""Every bundled record design must produce a classified outcome, never silence.

The corpus ships official AEAT record designs and the parser reads them. Until
this module existed, nothing enforced that it reads them ALL: a design could sit
in the corpus unparsed and unreported indefinitely, and the only reason anyone
knew how many did was that somebody counted by hand. A count taken by hand is not
a gate -- it is correct on the day it is taken and silent every day after.

THE PROPERTY. Every bundled design must resolve to exactly one of four outcomes:
it parses completely, it parses completely only because a declared and sourced
correction fixed a blank AEAT's own publication left, it parses partially with
every skipped sheet named and reasoned, or it refuses with a stated cause. A
design producing none of those -- or never reached by the parser at all --
fails here. The refusal case is the one that matters most and is the reason the
enumeration below is deliberately naive.

WHY THE ENUMERATION IS INDEPENDENT, and it is the lesson this module is built on.
The sibling guard in ``test_revision_span_matches_published_designs`` exists to
catch its own inventory dropping a design file, and it derived its "what is on
disk" set with the SAME ``files/*`` glob shape the inventory used. Two derivations
of one fact, which is the right instinct -- but both inherited one directory-shape
assumption, so a design stored outside ``files/`` was invisible to the inventory
AND to the guard watching the inventory. A check that shares its subject's blind
spot cannot see it. This module therefore walks the corpus root recursively for
anything with a parseable suffix, asks the parser nothing about what exists, and
would fail loudly if the parser's own enumeration ever narrowed.

WHY THE REFUSALS ARE A WORKLIST RATHER THAN A COUNT. A design that cannot be
parsed is either a parser gap or a corpus defect, and either way it is work. It is
listed with its modelo, its filename and its cause, and the causes are grouped, so
the reader sees a small number of fixable CLASSES rather than a pile of individual
problems. Nothing is exempted: an allowlist here would recreate the honour-system
list this suite exists to remove, and an exemption is
indistinguishable from a fix in every downstream count.

NO COUNT IS PINNED. The number of designs, the number in each bucket and the size
of each cause class all move as the corpus grows and as the parser improves --
landing a header-spelling fix moved ten designs between buckets on the day this
was written. Gating on any of those tallies would encode that moment, train the
next author to bump a constant, and then detect nothing.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest

from .....core.directory_scan import DirectoryEntryKind, scan_directory
from .....core.resources import bundled_path
from .. import (
    RecordDesignCorrection,
    RecordDesignFieldTypeCorrection,
    RecordDesignHeaderCellCorrection,
    RecordDesignSinglePositionCorrection,
    extract_record_design,
)
from ..record_design import (
    _collapse_stuttered_row_prefix,
    _extract_pdf_text_lines,
    _join_wrapped_row_descriptions,
    _parse_pdf_row,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGN_ROOT_PARTS = ("corpus", "aeat_official", "disenos_registro")
#: Suffixes the shipped parser dispatches on. Declared here rather than imported
#: from the parser so a suffix quietly dropped there shows up as a design this
#: module enumerates and the parser refuses, instead of vanishing from both.
_PARSEABLE_SUFFIXES = frozenset({".pdf", ".xls", ".xlsx", ".xlsm"})

#: Refusal causes seen in the corpus, mapped to the class a fix would address.
#: A cause matching none of these is reported as UNCLASSIFIED rather than dropped
#: into a bucket that happens to exist -- an unrecognised failure mode is a new
#: finding, and silently folding it into "other" is how a class stops being
#: noticed the moment it stops being new.
_CAUSE_CLASSES: tuple[tuple[str, str], ...] = (
    ("incomplete or ambiguous relative closing", "variable-envelope closing not recognised"),
    ("incomplete variable-envelope composition", "variable-envelope composition incomplete"),
    ("mixes fixed", "fixed and variable geometry mixed in one sheet"),
    ("has a gap", "field geometry leaves a gap"),
    ("has an overlap", "field geometry overlaps"),
    ("declares duplicate", "duplicate declaration in one sheet"),
    ("total positions", "declared total disagrees with parsed extent"),
    ("no record-design sheets found", "no sheet carried a recognisable header"),
    ("did not contain parseable field rows", "no field rows parsed from the document"),
    ("missing type", "a field row declares no type"),
    ("missing description", "a field row declares no description"),
    ("misordered", "envelope composition markers out of order"),
)


def _correction_locus(item: RecordDesignCorrection) -> str:
    """Where in the design a correction applies, in that kind's own coordinates.

    Every kind carries ``sheet``, and nothing else is shared: a field-type
    correction addresses a data row, a header-cell correction a header row and
    column, a single-position correction a wire position. A locus built from
    whichever of those a kind happens to have is what lets the worklist and the
    grounding assertions below name a correction without knowing its kind.

    An unknown kind RAISES rather than degrading to a bare sheet name. This
    function used to fall through to the header shape for anything that was not
    a field-type correction, so when a third kind was added it raised
    AttributeError on a missing field -- and because every test in this module
    goes through ``_outcomes()``, the whole module errored instead of reporting
    its worklist. A loud failure here names the gap; a silent default would let
    the next kind land unnoticed.
    """
    if isinstance(item, RecordDesignFieldTypeCorrection):
        return f"{item.sheet!r} row {item.source_row}"
    if isinstance(item, RecordDesignHeaderCellCorrection):
        return f"{item.sheet!r} header row {item.header_row} col {item.column_index} ({item.column_role})"
    if isinstance(item, RecordDesignSinglePositionCorrection):
        return f"{item.sheet!r} position {item.position}"
    raise AssertionError(
        f"correction kind {getattr(item, 'kind', type(item).__name__)!r} has no locus branch here; "
        "add one rather than letting this gate error on a shape it cannot describe"
    )


def _describe_correction(item: RecordDesignCorrection) -> str:
    """Render one applied correction for the worklist, per its own kind."""
    if isinstance(item, RecordDesignFieldTypeCorrection):
        return f"{_correction_locus(item)}: type {item.corrected_type!r} -- {item.reason}"
    if isinstance(item, RecordDesignSinglePositionCorrection):
        return f"{_correction_locus(item)}: type {item.corrected_type!r} ({item.description}) -- {item.reason}"
    return f"{_correction_locus(item)} -- {item.reason}"


@dataclass(frozen=True)
class _Outcome:
    """One design's classified parse result."""

    modelo: str
    design: str
    kind: Literal["complete", "corrected", "partial", "refused"]
    detail: str
    #: For a partial read, whether the artefact is a field TABLE (a parser gap)
    #: or a form DIAGRAM (a corpus defect). Empty for every other outcome.
    shape: str = ""


def _bundled_designs() -> tuple[Path, ...]:
    """Every parseable design file under the corpus, enumerated independently.

    Recursive and suffix-only on purpose: it asks nothing of the parser, the
    registry or any inventory, so it cannot inherit a narrowing any of them
    acquires.
    """
    root = bundled_path(*_DESIGN_ROOT_PARTS)
    return tuple(
        path
        for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES)
        if path.suffix.lower() in _PARSEABLE_SUFFIXES
    )


def _cause_class(message: str) -> str:
    for needle, label in _CAUSE_CLASSES:
        if needle in message:
            return label
    return "UNCLASSIFIED -- a refusal shape this gate has not seen before"


def _classify(path: Path) -> _Outcome:
    root = bundled_path(*_DESIGN_ROOT_PARTS)
    modelo = path.relative_to(root).parts[0].removeprefix("modelo_")
    try:
        extraction = extract_record_design(path)
    except Exception as exc:
        # Catching broadly is the point rather than a shortcut: this gate classifies
        # EVERY refusal shape, including ones nobody has described. Narrowing to the
        # exception types currently known would let a new one escape as an error
        # rather than appear on the worklist, which is the silence being removed.
        return _Outcome(modelo=modelo, design=path.name, kind="refused", detail=_cause_class(str(exc)))
    if extraction.corrections:
        # Checked BEFORE ``is_complete``, and never merged into "complete": a
        # design that reads only because a declared, sourced correction fixed
        # a blank cell AEAT's own publication omitted is not the artefact AEAT
        # published, so it must never look identical to one that is.
        return _Outcome(
            modelo=modelo,
            design=path.name,
            kind="corrected",
            detail="; ".join(_describe_correction(item) for item in extraction.corrections),
        )
    if extraction.is_complete:
        return _Outcome(modelo=modelo, design=path.name, kind="complete", detail="")
    return _Outcome(
        modelo=modelo,
        design=path.name,
        kind="partial",
        shape=_partial_read_shape(path, extraction),
        detail=", ".join(f"{item.name!r} ({item.reason})" for item in extraction.skipped),
    )


#: A published byte RULER: a long run of ascending positions AEAT prints across
#: the top of a form diagram. Six is comfortably past any field row's numbers.
_POSITION_RULER = re.compile(r"^\s*\d+(\s+\d+){6,}\s*$")


def _partial_read_shape(path: Path, extraction: object) -> str:
    """Return whether a partly-read design is a field TABLE or a form DIAGRAM.

    The two need opposite work and the worklist could not tell them apart. A
    TABLE is a real parser gap: thousands of rows parse and some drop, so fixing
    it is parser work on this repository. A DIAGRAM is a corpus defect: AEAT
    published a PICTURE of the form -- a position ruler along the top and
    free-floating labels -- with no ordinal/offset/length rows anywhere, so no
    parser change can read it and the fix is acquiring the tabular diseño.

    MEASURED WITH WHICH READER, THOUGH. This routine once answered from its own
    line scan, and that scan is not the extractor. It reported modelo 180's 2000
    orden design as ZERO parseable rows and 8 rulers -- a DIAGRAM, fix by acquiring
    the tabular diseño -- while the real extractor produced seventeen fields
    covering 205 of that record's 260 positions. The worklist therefore sent the
    reader on a corpus errand and hid a genuine fifty-five-position parser gap
    behind it. The lesson is the sibling one this module already carries, in the
    other direction: a check that re-derives its subject's output with a weaker
    reader does not describe the subject, it describes the replica.

    So coverage is taken from the extractor's own arithmetic, which it states in
    each skip reason, and the line scan is consulted only when that arithmetic
    shows nothing was read at all. Modelo 038's design remains the genuine DIAGRAM
    case: it is where this distinction was first paid for, the expensive way.
    """
    if path.suffix.lower() != ".pdf":
        return "TABLE"

    # The extractor's OWN coverage arithmetic decides this, because a second,
    # simpler row scan is not the same reader. Modelo 180's 2000 orden design was
    # labelled "DIAGRAM (8 position ruler(s), 0 parseable field rows)" by the line
    # scan below while the real extractor produced seventeen fields covering 205 of
    # its 260 positions -- so the worklist sent the reader to acquire a tabular
    # diseño for a document the parser already reads four fifths of, and hid a real
    # fifty-five-position parser gap behind a corpus errand.
    covered = _covered_positions_from_skip_reasons(extraction)
    if covered:
        return f"TABLE ({covered} position(s) already read; the rest is a parser gap)"

    lines = _collapse_stuttered_row_prefix(
        _join_wrapped_row_descriptions(_extract_pdf_text_lines(path.read_bytes(), source_label=path.name)),
    )
    rows = sum(1 for index, line in enumerate(lines) if _parse_pdf_row(line, index + 1) is not None)
    if rows:
        return "TABLE"
    rulers = sum(1 for line in lines if _POSITION_RULER.match(line))
    return f"DIAGRAM ({rulers} position ruler(s), no field row recognised by either reader)"


#: ``declares N total positions but 196-250, 300 were not read at all`` -- the
#: extractor's own statement of what it did and did not cover on one sheet.
_SKIP_COVERAGE = re.compile(r"declares (\d+) total positions but ([\d,\s-]+?) were not read")


def _covered_positions_from_skip_reasons(extraction: object) -> int:
    """Return how many positions the extractor DID read across its skipped sheets.

    Read from the skip reasons because a skipped sheet does not carry its parsed
    fields, and the reason is the extractor's own arithmetic rather than a
    re-derivation. A sheet whose holes span its entire declared extent contributes
    nothing, which is exactly the diagram case; any other sheet proves rows parsed.
    """
    covered = 0
    for sheet in getattr(extraction, "skipped", ()) or ():
        match = _SKIP_COVERAGE.search(getattr(sheet, "reason", "") or "")
        if match is None:
            continue
        total = int(match.group(1))
        holes = 0
        for run in match.group(2).split(","):
            run = run.strip()
            if not run:
                continue
            first, _, last = run.partition("-")
            if not first.isdigit():
                continue
            holes += (int(last) - int(first) + 1) if last.isdigit() else 1
        covered += max(total - holes, 0)
    return covered


def _outcomes() -> tuple[_Outcome, ...]:
    return tuple(_classify(path) for path in _bundled_designs())


def test_the_corpus_enumeration_reaches_designs_across_many_modelos() -> None:
    """Anti-vacuity: a gate over an empty or one-modelo corpus proves nothing.

    Gated on the property that the walk reaches a broad corpus, not on how many
    designs it holds. If the corpus path moves or the suffix set stops matching
    what AEAT publishes, every assertion below would pass over nothing, and that
    silence is exactly the failure mode this module exists to remove.
    """
    designs = _bundled_designs()
    assert designs, "no bundled design was enumerated at all; the corpus path or suffix set has moved"
    modelos = {path.relative_to(bundled_path(*_DESIGN_ROOT_PARTS)).parts[0] for path in designs}
    assert len(modelos) > 10, f"only {len(modelos)} modelo director(ies) reached; the walk has narrowed"


def test_every_bundled_design_produces_a_classified_outcome() -> None:
    """No design may be silent: each is complete, partial, or refused with a cause.

    This is the "never silence" property and it PASSES -- it asserts the parser
    reaches every design and says something about each, not that it succeeds. The
    worklist below is what says how many succeed.
    """
    outcomes = _outcomes()
    assert len(outcomes) == len(_bundled_designs())

    unclassified = [
        f"modelo {outcome.modelo} design {outcome.design!r}: {outcome.detail}"
        for outcome in outcomes
        if outcome.kind == "refused" and outcome.detail.startswith("UNCLASSIFIED")
    ]
    assert not unclassified, (
        "these designs refuse with a shape this gate does not recognise. That is a NEW failure "
        "class, not an 'other' bucket -- name it in the cause table so it can be grouped and "
        "fixed rather than absorbed:\n  " + "\n  ".join(unclassified)
    )

    silent = [
        f"modelo {outcome.modelo} design {outcome.design!r}"
        for outcome in outcomes
        if outcome.kind == "partial" and not outcome.detail
    ]
    assert not silent, (
        "these designs report a partial read without naming what was skipped, so the completeness "
        "notion is present but empty:\n  " + "\n  ".join(silent)
    )


def test_a_design_that_parses_completely_is_never_reported_as_failing() -> None:
    """The bite direction people skip, and the more expensive one to get wrong.

    The overwhelming majority of the corpus reads cleanly. A gate wrong in the
    STRICT direction would condemn all of them at once, which is a louder failure
    than the one this module exists to catch and a much easier one to ship by
    accident while chasing the interesting direction.
    """
    outcomes = _outcomes()
    complete = [outcome for outcome in outcomes if outcome.kind == "complete"]

    assert complete, (
        "not one bundled design parses completely. Either the parser has regressed across the "
        "whole corpus or this gate's classification is inverted; both are worse than the gap it "
        "was built to report."
    )
    assert all(not outcome.detail for outcome in complete), (
        "a design classified complete carries skipped-sheet detail, so 'complete' and 'partial' "
        "are not disjoint and the classification cannot be trusted in either direction"
    )
    assert len(complete) > len(outcomes) // 2, (
        f"only {len(complete)} of {len(outcomes)} designs parse completely. This gate does not pin "
        "a count, but a corpus where most designs fail means the parser regressed rather than the "
        "corpus grew, and the worklist below would be reporting the wrong thing entirely."
    )


def test_no_bundled_design_is_unreadable_or_only_partly_read() -> None:
    """THE WORKLIST. Landed red deliberately; the failures are the finding.

    Every design the parser cannot fully read, grouped by the class of defect a
    fix would address, so the reader sees a handful of fixable classes rather than
    a pile of unrelated files. Each entry names its modelo, its design and its
    cause.

    A partial read is listed alongside a refusal because both are work. Modelo
    232's skipped ``TABLAS`` tab is very likely a legitimate lookup table rather
    than a lost record -- but the extractor cannot tell a lookup tab from a
    dropped record body, and neither can this gate, so it reports the fact and
    declines to adjudicate. Deciding that one is benign is a judgement someone
    makes with the design open, and recording that judgement is a registry act,
    not an allowlist entry here.

    This test goes green when the parser reads every bundled design, which is the
    stated goal rather than an aspiration -- so do not weaken it, exempt from it,
    or narrow its enumeration to shorten the list.
    """
    outcomes = _outcomes()
    grouped: dict[str, list[str]] = defaultdict(list)
    for outcome in outcomes:
        # A "corrected" design is READ -- not a refusal or a partial read -- so
        # it belongs off this worklist exactly like "complete". Its visibility
        # lives in a dedicated test below, never here, because folding it into
        # this list would mean the ONLY way to see a correction fired is to
        # notice a red gate go green, which is worse than the silence "complete"
        # already avoids.
        if outcome.kind in {"complete", "corrected"}:
            continue
        label = outcome.detail if outcome.kind == "refused" else "partial read: sheets skipped"
        # A partial read carries its SHAPE on the line: the group tells you the
        # symptom, the shape tells you which kind of work fixes it.
        shape = f" [{outcome.shape}]" if outcome.shape else ""
        grouped[f"{outcome.kind.upper()} -- {label}"].append(
            f"modelo {outcome.modelo} {outcome.design!r}{shape}",
        )

    report = "\n".join(
        f"  [{len(entries)}] {label}\n" + "\n".join(f"      {entry}" for entry in sorted(entries))
        for label, entries in sorted(grouped.items())
    )
    readable = sum(1 for outcome in outcomes if outcome.kind in {"complete", "corrected"})
    assert not grouped, (
        f"{len(outcomes) - readable} of {len(outcomes)} bundled designs are not fully read. Each is "
        "a parser gap or a corpus defect and either way it is work; the grouping is by the class a "
        "fix would address:\n" + report
    )


def test_every_correction_is_visibly_distinct_from_complete_and_carries_its_grounding() -> None:
    """A design read via a correction is never silently indistinguishable from one AEAT published cleanly.

    This is the property the worklist test above cannot see: it treats
    "corrected" as read (correctly -- the values are right either way), but
    that test alone would let a correction fire invisibly, with no trace
    except a shrinking worklist. This test is the trace: every corrected
    design is named, and every correction it carries states which editions
    were read and why AEAT's own publication omitted the value -- never a
    bare "trust me".
    """
    outcomes = _outcomes()
    corrected = [outcome for outcome in outcomes if outcome.kind == "corrected"]

    assert corrected, (
        "no bundled design is currently classified 'corrected'. If a correction sidecar was removed "
        "or its target design now reads cleanly without it, this assertion should be updated "
        "deliberately -- not left to pass vacuously over an empty list."
    )

    complete_designs = {outcome.design for outcome in outcomes if outcome.kind == "complete"}
    corrected_designs = {outcome.design for outcome in outcomes if outcome.kind == "corrected"}
    assert not (complete_designs & corrected_designs), (
        "a design is classified as both 'complete' and 'corrected', so a correction is silently "
        "indistinguishable from a clean read -- exactly the outcome this classification exists to prevent"
    )

    for outcome in corrected:
        assert outcome.detail, f"modelo {outcome.modelo} {outcome.design!r} is 'corrected' with no stated grounding"
        matches = [path for path in _bundled_designs() if path.name == outcome.design]
        assert matches, f"corrected design {outcome.design!r} no longer resolves to a bundled file"
        extraction = extract_record_design(matches[0])
        for correction in extraction.corrections:
            # The locus is kind-agnostic on purpose: these messages used to name
            # ``correction.source_row``, which only a field-type correction has,
            # so the FAILURE path would itself raise AttributeError for the other
            # two kinds -- a gate that crashes instead of reporting exactly when
            # it has something to report.
            assert correction.editions_read, (
                f"modelo {outcome.modelo} {outcome.design!r} {_correction_locus(correction)} names no editions read"
            )
            assert correction.reason.strip(), (
                f"modelo {outcome.modelo} {outcome.design!r} {_correction_locus(correction)} states no reason"
            )
