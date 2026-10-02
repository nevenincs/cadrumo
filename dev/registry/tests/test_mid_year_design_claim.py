"""A revision covering part of a year claims only the design it cites for it.

AEAT splits an ejercicio mid-course by publishing two designs that share a
coverage year. The span detector claims designs BY YEAR, so both halves of such
a split received both designs and each reported a boundary inside its own year
-- modelo 303's 2024 halves as ``(2024, 2024)`` and modelo 490's 2022 halves as
``(2022, 2022)`` -- although each half was already scoped to exactly one design.

The same-year key is not the defect. The detector documents it as a mid-course
split and keys on the design FILE precisely so that boundary stays visible when
a revision really does span it. What was wrong is which designs a half-year
revision claims.

Each half states its answer twice: its id names its months and its source refs
name one design, and the design filenames agree -- ``hasta-periodos-08-y-2t``
beside ``a-partir-de-periodos-09-y-3t``.

The same claim is made at the edge of a multi-year span. A revision whose last
year ends mid-course -- an ejercicio's first month still filed on the outgoing
design -- shares that year with its successor exactly as a half does, and in
that year it claims only the design it cites.

CITATIONS ARE RESOLVED BY FINGERPRINT, not by file name, and that is what makes
the match work at all. The corpus bundles some designs twice under names
differing only by a truncated extension; the publication walk collapses those
twins and keeps whichever sorts first, which need not be the one the catalogue
cites. Modelo 303's late 2024 design is exactly that case -- the catalogue names
``...-381-kb-xls.xlsx``, the walk keeps the byte-identical ``...-381-kb-x.xlsx``.
"""

from __future__ import annotations

from datetime import date

import pytest

from ._revision_span_boundary_support import _boundaries_for, _mid_year_span
from ._revision_span_design_support import _declared_revisions, _filing_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Revisions scoped to part of one year, each citing a single design.
_MID_YEAR_HALVES = {
    ("303", "2024-hasta-08-y-2t"),
    ("303", "2024-desde-09-y-3t"),
    ("490", "2022-1t"),
    ("490", "2022-2t-4t"),
}
#: Revisions that genuinely cross a design re-layout between YEARS.
#:
#: Modelo 200's 2024 revision is the case this control was written for and is
#: absent from the set on purpose: a span needs design boundaries to be reported
#: at all, and that revision currently ships no export fragments while its tree
#: awaits regeneration. Pinning it here turned a corpus state into a detector
#: failure -- the control went red while the detector was working perfectly --
#: so the cross-year reporter is now derived and this name stays as the account
#: of what the control is for.
_CROSS_YEAR_SPANS: set[tuple[str, str]] = set()


def _by_subject() -> dict[tuple[str, str], dict[tuple[int, int], list[str]]]:
    return {(modelo.id, rid): _boundaries_for(modelo.id, revision) for modelo, rid, revision in _filing_revisions()}


def test_a_half_year_revision_reports_no_boundary_inside_its_own_year() -> None:
    reported = {subject for subject in _MID_YEAR_HALVES if _by_subject().get(subject)}

    assert not reported, sorted(reported)


def test_a_genuine_cross_year_span_still_reports() -> None:
    """The anti-vacuity control: narrowing the half-year claims did not silence the detector.

    The sibling above asserts that four revisions report NOTHING, which a
    detector that reported nothing at all would satisfy perfectly. This is the
    other side, and it asks the detector rather than a pinned modelo: some
    declared revision must still report a boundary between two DIFFERENT years,
    and it must not be one of the half-year revisions the narrowing silenced.

    Derived because the population moves with the corpus. A revision whose
    export tree is absent reports nothing through no fault of the detector, and
    a control naming one reads that absence as a regression.
    """
    all_subjects = {
        (modelo.id, rid): _boundaries_for(modelo.id, revision) for modelo, rid, revision in _declared_revisions()
    }

    cross_year = {
        subject for subject, boundaries in all_subjects.items() if any(start != end for start, end in boundaries)
    }

    assert cross_year, (
        "no declared revision reports a boundary between two different years, so the half-year "
        "narrowing above is proven by a detector that reports nothing"
    )
    assert not cross_year & _MID_YEAR_HALVES, sorted(cross_year & _MID_YEAR_HALVES)


def test_only_a_partial_span_inside_one_year_is_narrowed() -> None:
    """Full-year, multi-year and open-ended revisions are untouched by construction."""
    spans = {(modelo.id, rid): _mid_year_span(revision) for modelo, rid, revision in _filing_revisions()}

    # This is a filing-support gate.  Historical/inspection-only halves remain
    # useful registry data, but are intentionally outside this cohort.
    for subject in _MID_YEAR_HALVES & spans.keys():
        assert spans[subject] is not None, subject
    for subject in _CROSS_YEAR_SPANS & spans.keys():
        assert spans[subject] is None, subject


def test_a_multi_year_span_ending_mid_course_claims_only_its_cited_design_at_that_edge() -> None:
    """A partial edge year narrows; the same span widened to whole years still reports.

    Derived rather than pinned: every declared multi-year revision whose edge
    falls inside a year is compared with a copy stretched to cover those years
    whole. Where the two verdicts differ, the narrowing is what differs, and the
    stretched copy -- a span that really would write the edge year on the wrong
    layout -- must report every boundary the real one does plus the ones at its
    edge. Anti-vacuity: at least one revision must exercise the difference.
    """
    differing: list[tuple[str, str]] = []
    for modelo, revision_id, revision in _declared_revisions():
        valid_from, valid_to = revision.valid_from, revision.valid_to
        if valid_to is None or valid_from.year == valid_to.year:
            continue
        stretched = revision.model_copy(
            update={"valid_from": date(valid_from.year, 1, 1), "valid_to": date(valid_to.year, 12, 31)}
        )
        if stretched == revision:
            continue
        narrowed = _boundaries_for(modelo.id, revision)
        widened = _boundaries_for(modelo.id, stretched)
        if narrowed == widened:
            continue
        differing.append((modelo.id, revision_id))
        edge_years = {valid_from.year, valid_to.year}
        assert set(narrowed) < set(widened), (modelo.id, revision_id, sorted(narrowed), sorted(widened))
        assert all(set(pair) & edge_years for pair in set(widened) - set(narrowed)), (modelo.id, revision_id)

    assert differing, (
        "no multi-year revision ends inside a year on a design boundary, so the edge narrowing is proven by nothing"
    )
