"""The M303 rectificativa motive answer belongs to the revision asked about, not to today's calendar year."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta

import pytest

from ....core.time.clock import MADRID_TZ, frozen_clock
from ...calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...calculations.registry.governed_fact_scope import validating_governed_facts
from ...calculations.registry.schema_references import SourceReference
from ...calculations.registry.temporal import RevisionSelectionMetadata
from ..calculation_revision_amendment import m303_rectificativa_record_design_from_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned, validating_governed_facts(pinned):
        yield pinned


def _overlaps(revisions: tuple[RevisionSelectionMetadata, ...]) -> list[tuple[date, date]]:
    """Each day two Modelo 303 revisions are in force at once, with the first day after that overlap."""
    found: list[tuple[date, date]] = []
    for earlier in revisions:
        for later in revisions:
            if earlier.id == later.id or earlier.valid_to is None or later.valid_from <= earlier.valid_from:
                continue
            if later.valid_from <= earlier.valid_to:
                found.append((later.valid_from, earlier.valid_to + timedelta(days=1)))
    return found


def _at_madrid_noon(day: date) -> datetime:
    return datetime.combine(day, time(12), tzinfo=MADRID_TZ).astimezone(UTC)


def _record_design(operation: PinnedAuthorityOperation, revision: RevisionSelectionMetadata) -> SourceReference | None:
    year = revision.valid_from.year
    period = revision.period_selector.periods_for_year(year)[0]
    snapshot = operation.snapshot("303", filing_year=year, period=period, revision_id=revision.id)
    return m303_rectificativa_record_design_from_snapshot(snapshot, operation=operation)


def test_the_motive_design_resolves_on_a_day_two_revisions_are_in_force(operation: PinnedAuthorityOperation) -> None:
    revisions = tuple(operation.modelo_directory("303").revisions)
    overlaps = _overlaps(revisions)
    assert overlaps, "the registry declares no mid-year Modelo 303 design boundary to exercise"
    for overlap_day, day_after in overlaps:
        in_force = [revision for revision in revisions if revision.contains_date(overlap_day)]
        assert len(in_force) > 1
        for revision in in_force:
            with frozen_clock(_at_madrid_noon(overlap_day)):
                during = _record_design(operation, revision)
            with frozen_clock(_at_madrid_noon(day_after)):
                after = _record_design(operation, revision)
            assert during == after
