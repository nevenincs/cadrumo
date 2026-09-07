"""Every path-keyed evidence artefact must have something that notices it rotting.

The failure this exists to prevent is not a stale entry -- it is an artefact
that NOBODY CHECKS. A generated file keyed by source path is invalidated by any
relocation, and the invalidation is silent: the JSON still parses, the gate that
reads it still passes, and a symbol grep cannot see the breakage because these
artefacts name PATHS rather than symbols. The individual drift gates already
handle the artefacts they know about. What nothing handled is the next artefact
someone generates, which arrives with no detector and looks exactly like the
ones that have one.

So this asserts enrolment rather than freshness: for each generated evidence
file, SOME test module must name it. It deliberately does not check that the
gate is any good -- that is the owning gate's business -- because a weak
detector and no detector fail differently and only the second is invisible.

WHAT IS DELIBERATELY NOT ENROLLED, and why the distinction is the whole point.
A content-addressed SNAPSHOT of a past measurement is a different kind of
artefact from a path-keyed INVENTORY of the current tree. The benchmark
baseline's source manifest is the former: it records the tree as it stood when
a measurement was captured, so entries naming files that have since been
deleted are the artefact working correctly, not rotting. Measured on
2026-08-31, 541 of its 28,414 entries name paths that no longer exist, and a
shipped gate asserts that it IS stale against the current tree. Enrolling it
here, or "repairing" its paths, would break the measurement it exists to
preserve -- rewriting a recorded observation to match today is how a receipt
becomes a fabrication.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOT = Path(__file__).resolve().parents[2]
_GENERATED_EVIDENCE_DIR = _ROOT / "dev" / "quality"
_TEST_DIRS = (_ROOT / "dev" / "tests",)


def _generated_evidence_files() -> tuple[Path, ...]:
    """Every path-keyed evidence artefact this gate holds to enrolment."""
    return tuple(sorted(_GENERATED_EVIDENCE_DIR.glob("*.json")))


def _naming_modules(stem: str) -> tuple[Path, ...]:
    """Test modules that mention the artefact by name."""
    return tuple(
        path
        for directory in _TEST_DIRS
        for path in directory.rglob("test_*.py")
        if stem in path.read_text(encoding="utf-8")
    )


def test_the_search_population_is_empty_because_the_artefacts_were_retired() -> None:
    """The population is zero, and that is a recorded state rather than a broken glob.

    This asserted the population was NON-empty until the last artefact went. That
    was the right guard while any existed -- an empty glob makes the enrolment
    check below vacuous -- but every path-keyed evidence file under
    ``dev/quality`` has since been deliberately retired: four in the commit that
    closed the private-to-public module promotion, two more when the error-code
    and exec-outcome ledgers were withdrawn. Left as it was, this gate sat
    permanently red over a subject nobody intends to restore, and a gate that is
    always failing is read exactly as one that is never run.

    Inverted rather than deleted, because the module's reason survives its
    subject: the danger it names is "the next artefact someone generates, which
    arrives with no detector". Asserting emptiness keeps that watch -- the first
    new ``dev/quality/*.json`` turns this red, which is precisely the moment a
    human should decide whether it needs a drift gate. The parametrised check
    below then does the real work, and the predicate control proves it can fail.
    """
    found = _generated_evidence_files()
    assert found == (), (
        "generated evidence artefacts have reappeared under "
        f"{_GENERATED_EVIDENCE_DIR}: {[path.name for path in found]}. Each is keyed by source "
        "path, so a relocation invalidates it silently. Give each one a drift gate that "
        "regenerates and compares, then record the new population here."
    )


@pytest.mark.parametrize("artefact", _generated_evidence_files(), ids=lambda path: path.name)
def test_a_generated_evidence_artefact_is_named_by_some_gate(artefact: Path) -> None:
    """An artefact nothing reads is evidence nothing maintains."""
    stem = artefact.name.split(".", 1)[0]
    naming = _naming_modules(stem)
    assert naming, (
        f"{artefact.name} is generated evidence keyed by source path, and no test module under "
        f"{_TEST_DIRS[0].name}/ names it. A relocation will invalidate it silently: the file still "
        "parses and nothing re-derives it. Give it a drift gate that regenerates and compares, or "
        "delete it if it is no longer evidence for anything."
    )


def test_the_enrolment_check_can_actually_fail() -> None:
    """Drive the predicate over an artefact name nothing mentions.

    Without this the parametrised test above is only ever exercised on names
    that already pass, so a predicate that returned a non-empty tuple whatever
    it was asked would look identical to a working one.

    The probe name is ASSEMBLED rather than written, because the search reads
    test sources and this module is one of them: spelled as a literal, the file
    would find its own text and the check would report enrolment for a name
    nothing generates. A scan whose corpus includes the scanner needs its
    fixtures kept out of that corpus.
    """
    absent = "zz" + "-unenrolled-probe-" + "artefact"
    assert _naming_modules(absent) == ()
