"""A calendar range outside the filing-year envelope reads as unsupported, never as a calendar with nothing due."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_references import TemporalSupportEnvelope
from ..calendar import build_overview_calendar
from ..calendar_envelope import OverviewCalendarSupportState, calendar_support_state
from ..calendar_models import OverviewCalendarEntrySource, OverviewCalendarRange
from ..read_calendar_projection import OverviewCalendarSnapshot
from .calendar_test_support import profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _year(year: int) -> OverviewCalendarRange:
    return OverviewCalendarRange(from_date=date(year, 1, 1), to_date=date(year, 12, 31))


def _snapshot(operation: PinnedAuthorityOperation, year: int) -> OverviewCalendarSnapshot:
    envelope = operation.supported_filing_years()
    calendar = build_overview_calendar(
        profile(), _year(year), operation=operation, today=date(envelope.horizon, 6, 1), raw_values={}
    )
    snapshot = OverviewCalendarSnapshot.from_calendar(calendar, envelope=envelope)
    assert snapshot.to_calendar() == calendar
    return snapshot


def _registry_rows(snapshot: OverviewCalendarSnapshot) -> int:
    return sum(row.source is OverviewCalendarEntrySource.REGISTRY_DEADLINE for row in snapshot.entries)


def test_the_served_envelope_is_the_pinned_catalogue(authority_operation: PinnedAuthorityOperation) -> None:
    envelope = authority_operation.supported_filing_years()
    support = _snapshot(authority_operation, envelope.horizon).support

    assert (support.floor, support.horizon, support.hard_ceiling) == (
        envelope.floor,
        envelope.horizon,
        envelope.hard_ceiling,
    )


def test_the_floor_and_the_horizon_are_supported_years_with_deadlines(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    envelope = authority_operation.supported_filing_years()
    for year in (envelope.floor, envelope.horizon):
        snapshot = _snapshot(authority_operation, year)

        assert snapshot.support.state is OverviewCalendarSupportState.SUPPORTED, year
        assert _registry_rows(snapshot), year


def test_a_year_below_the_floor_is_unsupported_rather_than_empty(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    envelope = authority_operation.supported_filing_years()
    snapshot = _snapshot(authority_operation, envelope.floor - 1)

    assert snapshot.support.state is OverviewCalendarSupportState.BELOW_FLOOR
    assert snapshot.support.unsupported
    assert _registry_rows(snapshot) == 0


def test_a_year_past_an_open_horizon_is_projected_with_its_deadlines(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    envelope = authority_operation.supported_filing_years()
    snapshot = _snapshot(authority_operation, envelope.horizon + 1)

    expected = (
        OverviewCalendarSupportState.PROJECTED
        if envelope.hard_ceiling is None or envelope.hard_ceiling > envelope.horizon
        else OverviewCalendarSupportState.SUPPORTED
    )
    assert snapshot.support.state is expected
    assert _registry_rows(snapshot)


def test_a_range_across_the_floor_is_partial(authority_operation: PinnedAuthorityOperation) -> None:
    envelope = authority_operation.supported_filing_years()
    across = OverviewCalendarRange(from_date=date(envelope.floor - 1, 1, 1), to_date=date(envelope.floor, 12, 31))

    assert calendar_support_state(across, envelope) is OverviewCalendarSupportState.PARTIAL


def test_a_range_past_a_declared_ceiling_is_unsupported(authority_operation: PinnedAuthorityOperation) -> None:
    catalogue = authority_operation.supported_filing_years()
    ceiling = TemporalSupportEnvelope(floor=catalogue.floor, horizon=catalogue.horizon, hard_ceiling=catalogue.horizon)

    assert calendar_support_state(_year(catalogue.horizon + 1), ceiling) is OverviewCalendarSupportState.SUPPORTED
    assert calendar_support_state(_year(catalogue.horizon + 2), ceiling) is OverviewCalendarSupportState.ABOVE_CEILING


def test_a_snapshot_refuses_registry_deadlines_in_an_unsupported_range(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    catalogue = authority_operation.supported_filing_years()
    ceiling = TemporalSupportEnvelope(floor=catalogue.floor, horizon=catalogue.horizon, hard_ceiling=catalogue.horizon)
    beyond = _year(catalogue.horizon + 2)
    calendar = build_overview_calendar(
        profile(), beyond, operation=authority_operation, today=date(catalogue.horizon, 6, 1), raw_values={}
    )
    assert calendar.entries

    with pytest.raises(ValidationError, match="registry deadlines"):
        OverviewCalendarSnapshot.from_calendar(calendar, envelope=ceiling)


def test_a_support_state_that_disagrees_with_its_range_is_refused(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    envelope = authority_operation.supported_filing_years()
    data = _snapshot(authority_operation, envelope.horizon).model_dump(mode="python")
    data["support"]["state"] = OverviewCalendarSupportState.BELOW_FLOOR

    with pytest.raises(ValidationError, match="support state"):
        OverviewCalendarSnapshot.model_validate(data)
