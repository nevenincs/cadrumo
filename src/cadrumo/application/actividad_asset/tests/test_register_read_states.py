"""The register serves the year to open on, whether pending still applies, one count per year and the record kinds.

Figures use 2,000.00 at 26% linear from 1 January 2025: 520.00 a full year.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetTimelineEventKind
from cadrumo.application.actividad_asset.register_reads import default_register_year
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    ActivityAssetRevision,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)

from .test_baja_correction import _ASSET, _disposed, _sale, _without_baja
from .test_register import _NAME, _full_year, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _restated(base: ActivityAssetRevision, **changes: object) -> ActivityAssetRevision:
    facts = {name: getattr(base, name) for name in type(base).model_fields}
    facts.update(changes)
    return ActivityAssetRevision(**facts)


def test_the_claim_form_opens_on_the_latest_elapsed_year_with_something_to_claim() -> None:
    operations, _ = _operations(today=date(2027, 6, 30))
    operations.create(_revision(), _NAME)

    (row,) = operations.list_elements()

    assert row.default_claim_year == 2027


def test_the_claim_form_opens_on_the_earliest_later_year_when_every_elapsed_year_is_claimed() -> None:
    operations, _ = _operations(today=date(2026, 6, 30))
    operations.create(_revision(), _NAME)
    for year in (2025, 2026):
        operations.record_claim(_full_year(operations, year), creating_operation=f"test.{year}")

    (row,) = operations.list_elements()

    assert row.default_claim_year == 2027


def test_the_register_opens_on_the_latest_listed_year_up_to_the_current_one_else_the_earliest() -> None:
    assert default_register_year([2023, 2025, 2027], today=date(2026, 3, 1)) == 2025
    assert default_register_year([2027, 2028], today=date(2026, 3, 1)) == 2027
    assert default_register_year([], today=date(2026, 3, 1)) is None


def test_the_list_serves_the_default_year_the_register_opens_on() -> None:
    operations, _ = _operations(today=date(2026, 6, 30))
    operations.create(_revision(), _NAME)

    years = tuple(sorted({year for row in operations.list_elements() for year in row.years}))

    assert operations.default_register_year(years) == 2026


def test_pending_no_longer_applies_once_a_baja_is_recorded_but_keeps_its_formula_value() -> None:
    operations, _, baja = _disposed()
    with_baja = operations.list_elements()[0]
    operations.correct(_without_baja(baja))
    without_baja = operations.list_elements()[0]

    assert with_baja.pending_applies is False
    assert without_baja.pending_applies is True
    assert with_baja.pending is not None
    assert with_baja.accumulated is not None
    assert float(with_baja.pending.decimal) == pytest.approx(2000 - float(with_baja.accumulated.decimal))


def test_each_year_is_counted_once_and_a_missing_opening_is_incomplete_not_also_missing() -> None:
    operations, _ = _operations(today=date(2027, 6, 30))
    missing_opening = OpeningAmortizationHistory(status=OpeningHistoryStatus.MISSING)
    operations.create(_restated(_revision(), opening_history=missing_opening), _NAME)

    (row,) = operations.list_elements()
    plan = operations.plan(_ASSET)

    counts = row.findings
    states = (counts.missing, counts.incomplete, counts.conflict, counts.unsupported, counts.without_tables)
    assert counts.incomplete > 0
    assert counts.missing == 0
    assert sum(states) <= len(plan)
    assert counts.incomplete == sum(item.absence is not None and item.absence.value == "incomplete" for item in plan)


def test_a_year_that_is_merely_unclaimed_counts_as_missing_only() -> None:
    operations, _ = _operations(today=date(2026, 6, 30))
    operations.create(_revision(), _NAME)

    (row,) = operations.list_elements()

    assert row.findings.missing >= 1
    assert (row.findings.incomplete, row.findings.conflict, row.findings.unsupported) == (0, 0, 0)


def test_the_timeline_words_a_correction_a_baja_change_and_a_baja_removal_apart() -> None:
    operations, _, baja = _disposed()
    operations.correct(baja.with_disposal(_sale(date(2026, 3, 31))).model_copy(update={"revision_number": 3}))
    removed = operations.inspect(_ASSET)[-1]
    operations.correct(_without_baja(removed))

    events = operations.timeline(_ASSET)
    revisions = [event for event in events if event.event_kind is not None and "claim" not in event.event_kind.value]

    kinds = [event.event_kind for event in revisions]
    assert kinds[0] is ActivityAssetTimelineEventKind.CREATED
    assert ActivityAssetTimelineEventKind.BAJA_RECORDED in kinds
    assert kinds[-1] is ActivityAssetTimelineEventKind.BAJA_REMOVED
    removal = revisions[-1]
    assert removal.effect_date == date(2026, 3, 31)


def test_a_claim_event_states_its_year_and_last_day_and_only_a_claim_in_effect_can_mismatch() -> None:
    operations, repository = _operations()
    operations.create(_revision(), _NAME)
    first = operations.record_claim(_full_year(operations, 2025), creating_operation="test.claim").claim
    repository.record_claim(
        first.model_copy(update={"amount": first.amount - 10, "supersedes_claim_id": first.claim_id})
    )

    claims = [event.claim for event in operations.timeline(_ASSET) if event.claim is not None]

    assert [(use.tax_year, use.covered_through, use.in_effect) for use in claims] == [
        (2025, date(2025, 12, 31), False),
        (2025, date(2025, 12, 31), True),
    ]
    assert claims[0].matches_current_schedule is True
    assert claims[0].stale_reason is None
