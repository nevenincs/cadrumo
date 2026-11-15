"""The CLI calendar states the served filing-year support, and a range outside it never reads as empty."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from ....application.overview.calendar_envelope import OverviewCalendarSupport, OverviewCalendarSupportState
from ....application.overview.calendar_models import OverviewCalendar, OverviewCalendarRange
from ....application.overview.coverage import ObligationCoverageReport
from ....core.json_contract import NoticeSeverity
from ....domain.calculations.registry.schema_references import TemporalSupportEnvelope
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..overview_calendar_support import calendar_support_line, calendar_support_notices
from ..overview_rendering import overview_calendar_output, overview_calendar_profile_output
from ..overview_results import OverviewCalendarResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = "44450001-0000-4000-8000-000000000002"
_SUPPORT_CODE = "overview.calendar.support"


def _years(first: int, last: int) -> OverviewCalendarRange:
    return OverviewCalendarRange(from_date=date(first, 1, 1), to_date=date(last, 12, 31))


def _envelope() -> TemporalSupportEnvelope:
    published = filing_year_envelope()
    return TemporalSupportEnvelope(
        floor=published.floor, horizon=published.horizon, hard_ceiling=published.hard_ceiling
    )


def _ceilinged() -> TemporalSupportEnvelope:
    published = _envelope()
    return TemporalSupportEnvelope(floor=published.floor, horizon=published.horizon, hard_ceiling=published.horizon)


def _empty_calendar(calendar_range: OverviewCalendarRange) -> OverviewCalendar:
    return OverviewCalendar(
        range=calendar_range,
        evaluated_on=calendar_range.from_date,
        entries=(),
        generated_at=datetime.combine(calendar_range.from_date, datetime.min.time(), tzinfo=UTC),
        coverage=ObligationCoverageReport(),
    )


def _support_notices(support: OverviewCalendarSupport) -> list[tuple[NoticeSeverity, str]]:
    return [(notice.severity, notice.code) for notice in calendar_support_notices(support)]


def test_a_supported_range_prints_its_envelope_and_carries_no_support_notice() -> None:
    envelope = _envelope()
    support = OverviewCalendarSupport.for_range(_years(envelope.horizon, envelope.horizon), envelope)

    assert support.state is OverviewCalendarSupportState.SUPPORTED
    ceiling = "-" if envelope.hard_ceiling is None else str(envelope.hard_ceiling)
    assert calendar_support_line(support) == f"support\tsupported\t{envelope.floor}\t{envelope.horizon}\t{ceiling}"
    assert _support_notices(support) == []


def test_a_projected_range_is_explained_as_estimated_not_refused() -> None:
    envelope = _envelope()
    assert envelope.admits_coordinate(envelope.horizon + 1)
    support = OverviewCalendarSupport.for_range(_years(envelope.horizon + 1, envelope.horizon + 1), envelope)

    assert support.state is OverviewCalendarSupportState.PROJECTED
    assert _support_notices(support) == [(NoticeSeverity.INFO, f"{_SUPPORT_CODE}.projected")]
    assert str(envelope.horizon) in calendar_support_notices(support)[0].message


@pytest.mark.parametrize(
    ("bounds", "state"),
    [
        ("below", OverviewCalendarSupportState.BELOW_FLOOR),
        ("above", OverviewCalendarSupportState.ABOVE_CEILING),
        ("straddle", OverviewCalendarSupportState.PARTIAL),
    ],
)
def test_an_unserved_range_warns_and_names_the_bound_it_crosses(
    bounds: str, state: OverviewCalendarSupportState
) -> None:
    envelope = _ceilinged()
    ceiling = envelope.hard_ceiling
    assert ceiling is not None
    ranges = {
        "below": _years(envelope.floor - 2, envelope.floor - 2),
        "above": _years(ceiling + 2, ceiling + 2),
        "straddle": _years(envelope.floor - 2, envelope.floor),
    }
    support = OverviewCalendarSupport.for_range(ranges[bounds], envelope)

    assert support.state is state
    assert _support_notices(support) == [(NoticeSeverity.WARNING, f"{_SUPPORT_CODE}.{state.value}")]
    message = calendar_support_notices(support)[0].message
    assert "cli.overview" not in message
    assert "%{" not in message
    if bounds == "below":
        assert str(envelope.floor) in message
    if bounds == "above":
        assert str(ceiling) in message


def test_the_single_profile_result_and_text_carry_an_unsupported_state_instead_of_an_empty_calendar() -> None:
    envelope = _envelope()
    calendar_range = _years(envelope.floor - 2, envelope.floor - 2)
    support = OverviewCalendarSupport.for_range(calendar_range, envelope)

    result, lines, notices = overview_calendar_output(
        _empty_calendar(calendar_range), calendar_range, support=support, evidence_notices=()
    )

    assert result.support == support
    assert result.model_dump(mode="json")["support"]["state"] == "below_floor"
    assert calendar_support_line(support) in lines
    assert [notice.code for notice in notices if notice.code.startswith(_SUPPORT_CODE)] == [
        f"{_SUPPORT_CODE}.below_floor"
    ]


def test_the_all_profiles_block_carries_the_support_state() -> None:
    envelope = _envelope()
    calendar_range = _years(envelope.floor - 2, envelope.floor - 2)
    support = OverviewCalendarSupport.for_range(calendar_range, envelope)

    payload, lines, notices = overview_calendar_profile_output(
        bucket_id=_PROFILE_ID, label="Operator", cal=_empty_calendar(calendar_range), support=support
    )

    assert payload["support_state"] is OverviewCalendarSupportState.BELOW_FLOOR
    assert calendar_support_line(support) in lines
    assert any(notice.code == f"{_SUPPORT_CODE}.below_floor" for notice in notices)
    OverviewCalendarResult.model_validate({"profiles": [payload]})


def test_a_single_profile_result_without_its_support_is_refused() -> None:
    envelope = _envelope()
    calendar_range = _years(envelope.horizon, envelope.horizon)
    support = OverviewCalendarSupport.for_range(calendar_range, envelope)
    result, _, _ = overview_calendar_output(
        _empty_calendar(calendar_range), calendar_range, support=support, evidence_notices=()
    )
    payload = result.model_dump(mode="json")
    del payload["support"]

    with pytest.raises(ValidationError, match="filing-year support"):
        OverviewCalendarResult.model_validate(payload)
