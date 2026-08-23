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

CITATIONS ARE RESOLVED BY FINGERPRINT, not by file name, and that is what makes
the match work at all. The corpus bundles some designs twice under names
differing only by a truncated extension; the publication walk collapses those
twins and keeps whichever sorts first, which need not be the one the catalogue
cites. Modelo 303's late 2024 design is exactly that case -- the catalogue names
``...-381-kb-xls.xlsx``, the walk keeps the byte-identical ``...-381-kb-x.xlsx``.
"""

from __future__ import annotations

import pytest

from .test_revision_span_matches_published_designs import (
    _boundaries_for,
    _exporting_revisions,
    _mid_year_span,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Revisions scoped to part of one year, each citing a single design.
_MID_YEAR_HALVES = {
    ("303", "2024-hasta-08-y-2t"),
    ("303", "2024-desde-09-y-3t"),
    ("490", "2022-1t"),
    ("490", "2022-2t-4t"),
}
#: Revisions that genuinely cross a design re-layout between YEARS.
_CROSS_YEAR_SPANS = {("200", "2024-y-siguientes"), ("347", "2008-2024")}


def _by_subject() -> dict[tuple[str, str], dict]:
    return {(modelo.id, rid): _boundaries_for(modelo.id, revision) for modelo, rid, revision in _exporting_revisions()}


def test_a_half_year_revision_reports_no_boundary_inside_its_own_year() -> None:
    reported = {subject for subject in _MID_YEAR_HALVES if _by_subject().get(subject)}

    assert not reported, sorted(reported)


def test_the_genuine_cross_year_spans_still_report() -> None:
    """The control. A narrowing that silenced these would be hiding the gate's whole purpose."""
    silent = {subject for subject in _CROSS_YEAR_SPANS if not _by_subject().get(subject)}

    assert not silent, sorted(silent)


def test_only_a_partial_span_inside_one_year_is_narrowed() -> None:
    """Full-year, multi-year and open-ended revisions are untouched by construction."""
    spans = {(modelo.id, rid): _mid_year_span(revision) for modelo, rid, revision in _exporting_revisions()}

    for subject in _MID_YEAR_HALVES:
        assert spans[subject] is not None, subject
    for subject in _CROSS_YEAR_SPANS:
        assert spans[subject] is None, subject
