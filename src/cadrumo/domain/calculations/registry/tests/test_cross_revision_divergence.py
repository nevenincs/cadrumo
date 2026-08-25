"""Cross-revision period-overlap detection.

``_revisions_overlap`` decides whether two :class:`ModeloRevision` period
windows could both be live at once -- the answer every strict-continuity
consumer (divergence failures, the continuity-evolution requirement, and the
contiguity gap detector) keys its own check on. No dedicated test file
existed for this module before this one.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

from ..cross_revision_divergence import revisions_overlap
from ._referential_integrity_support import (
    REFERENCE_LEGAL_ID,
    REFERENCE_SOURCE_ID,
    minimal_application_link,
    minimal_casilla,
    minimal_workbook_ref,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _revision(*, revision_id: str, valid_from: date, period_selector: PeriodSelector) -> ModeloRevision:
    return ModeloRevision(
        id=revision_id,
        localization_key=f"test.schema.revision.{revision_id}.label",
        valid_from=valid_from,
        period_selector=period_selector,
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
        orden_aplicabilidad=(REFERENCE_LEGAL_ID,),
        casillas=(minimal_casilla(),),
        workbook_parity_refs=(minimal_workbook_ref(),),
        application_links=(minimal_application_link("filing"),),
    )


def test_revisions_with_disjoint_years_do_not_overlap() -> None:
    """The legitimate path: two revisions with non-overlapping year windows."""
    left = _revision(
        revision_id="test-2023",
        valid_from=date(2023, 1, 1),
        period_selector=PeriodSelector(years=(2023,), periods=("0A",)),
    )
    right = _revision(
        revision_id="test-2024",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(years=(2024,), periods=("0A",)),
    )
    assert not revisions_overlap(left, right)


def test_revisions_with_shared_years_and_periods_overlap() -> None:
    """The legitimate path: two revisions with the same year and period do overlap."""
    left = _revision(
        revision_id="test-2024-a",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(years=(2024,), periods=("0A",)),
    )
    right = _revision(
        revision_id="test-2024-b",
        valid_from=date(2024, 6, 1),
        period_selector=PeriodSelector(years=(2024,), periods=("0A",)),
    )
    assert revisions_overlap(left, right)


def test_a_dropped_period_selector_is_refused_not_silently_treated_as_overlapping() -> None:
    """The bite proof: a revision that has genuinely lost its ``period_selector``
    must fail loud, never silently make every pair register as "overlapping".

    ``ModeloRevision.period_selector`` is a REQUIRED field on every real,
    validly-constructed revision (confirmed: no production code ever builds a
    ``ModeloRevision`` via ``model_construct``), so before the fix the
    ``getattr(left, "period_selector", None)`` read followed by an
    ``isinstance`` check existed purely to survive a hypothetical drift --
    and its fallback on drift was ``return True`` (every pair "overlaps").
    That is NOT a safe default: three of this module's four downstream
    consumers only run their own check when a pair does NOT overlap (the
    strict continuity-evolution requirement, the continuity-coverage
    advisory, and the contiguity-gap detector this package's own docstring
    says exists to catch "a chain which is present, absent, then present
    again"), so a permanent ``True`` silently disables all three with
    nothing downstream to catch the loss. This drops the field straight off
    a real, otherwise-valid instance's own ``__dict__`` (not a look-alike
    stand-in -- the fixed direct-attribute read only ever sees a genuine
    ``ModeloRevision``) and proves the fixed read fails loud instead.
    """
    left = _revision(
        revision_id="test-drift",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(years=(2024,), periods=("0A",)),
    )
    right = _revision(
        revision_id="test-drift-2",
        valid_from=date(2025, 1, 1),
        period_selector=PeriodSelector(years=(2025,), periods=("0A",)),
    )
    del left.__dict__["period_selector"]

    with pytest.raises(AttributeError, match="period_selector"):
        revisions_overlap(left, right)
