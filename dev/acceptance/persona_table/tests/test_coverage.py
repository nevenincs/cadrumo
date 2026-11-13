"""The coverage audit sorts each return into covered, gap, table-only, undecided or not-ended, per persona."""

from __future__ import annotations

import json
from datetime import date
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tests.persona_materialisation import year_envelope
from cadrumo.tests.personas import YearEnvelope

from ..coverage import (
    ABSENT,
    APPLICABLE,
    CalendarObservation,
    CalendarRefusal,
    compare,
    projection,
    read_observations,
    render_markdown,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@cache
def _envelope() -> YearEnvelope:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


def _year() -> int:
    """A year whose returns have all ended by the first day of the year after the horizon."""
    return _envelope().horizon


def _late() -> date:
    return date(_envelope().horizon + 1, 6, 1)


def _window(persona: str, modelo: str, period: str, year: int | None = None) -> CalendarObservation:
    return CalendarObservation(persona, modelo, _year() if year is None else year, period, APPLICABLE)


def test_a_window_the_table_runs_is_covered_and_one_it_does_not_is_a_gap() -> None:
    year = _year()
    report = compare(
        year,
        {"ana": [("130", year, "1T")]},
        [_window("ana", "130", "1T"), _window("ana", "303", "1T")],
        {"ana": _late()},
    )
    assert report.covered == [("ana", "130", year, "1T")]
    assert report.gaps == [
        {"persona": "ana", "modelo": "303", "year": year, "period": "1T", "source": "calendar_applicable"}
    ]
    assert report.table_only == []
    assert report.undecided == []


def test_a_row_the_calendar_suppresses_or_omits_is_table_only_with_what_the_calendar_says() -> None:
    year = _year()
    suppressed = CalendarObservation("ana", "130", year, "1T", "not_applicable", "landlord only")
    report = compare(
        year,
        {"ana": [("130", year, "1T"), ("100", year, "0A")]},
        [suppressed],
        {"ana": _late()},
    )
    assert report.covered == []
    assert report.gaps == []
    assert report.table_only == [
        {"persona": "ana", "modelo": "100", "year": year, "period": "0A", "app_verdict": ABSENT},
        {"persona": "ana", "modelo": "130", "year": year, "period": "1T", "app_verdict": "not_applicable"},
    ]
    assert report.undecided == []


def test_an_incomplete_verdict_is_undecided_whether_or_not_the_table_runs_it() -> None:
    year = _year()
    observations = [
        CalendarObservation("ana", "390", year, "0A", "incomplete", "taxpayer type undeclared"),
        CalendarObservation("ana", "347", year, "0A", "incomplete", "payer facts unknown"),
    ]
    report = compare(year, {"ana": [("390", year, "0A")]}, observations, {"ana": _late()})
    assert report.undecided == [
        {
            "persona": "ana",
            "modelo": "347",
            "year": year,
            "period": "0A",
            "reason": "incomplete: payer facts unknown",
            "in_table": False,
        },
        {
            "persona": "ana",
            "modelo": "390",
            "year": year,
            "period": "0A",
            "reason": "incomplete: taxpayer type undeclared",
            "in_table": True,
        },
    ]
    assert report.table_only == [
        {"persona": "ana", "modelo": "390", "year": year, "period": "0A", "app_verdict": "incomplete"}
    ]
    assert report.gaps == []


def test_a_window_whose_period_has_not_ended_by_the_scenario_day_is_not_a_gap() -> None:
    year = _year()
    scenario_day = date(year, 5, 1)
    report = compare(
        year,
        {"ana": []},
        [_window("ana", "303", "1T"), _window("ana", "303", "2T")],
        {"ana": scenario_day},
    )
    assert [item["period"] for item in report.gaps] == ["1T"]
    assert [item["period"] for item in report.not_ended] == ["2T"]


def test_a_window_row_wins_over_a_suppressed_row_of_the_same_return() -> None:
    year = _year()
    suppressed = CalendarObservation("ana", "303", year, "1T", "incomplete", "undeclared")
    held = projection([suppressed, _window("ana", "303", "1T")])
    assert held[("303", year, "1T")].verdict == APPLICABLE
    assert projection([_window("ana", "303", "1T"), suppressed])[("303", year, "1T")].verdict == APPLICABLE


def test_a_refused_calendar_leaves_its_persona_out_of_the_comparison() -> None:
    year = _year()
    report = compare(
        year,
        {"ana": [("130", year, "1T")], "bea": [("303", year, "1T")]},
        [_window("bea", "303", "1T")],
        {"ana": _late(), "bea": _late()},
        [CalendarRefusal("ana", "PersonaMaterialisationError: refused")],
    )
    assert report.refused == [{"persona": "ana", "reason": "PersonaMaterialisationError: refused"}]
    assert report.table_only == []
    assert report.covered == [("bea", "303", year, "1T")]


def test_observations_round_trip_and_the_report_serialises_to_the_stated_schema(tmp_path: Path) -> None:
    year = _year()
    observations = [
        _window("ana", "303", "1T"),
        CalendarObservation("ana", "130", year, "1T", "not_applicable", "landlord"),
    ]
    refusal = CalendarRefusal("bea", "refused")
    path = tmp_path / "calendar.jsonl"
    path.write_text("".join(line + "\n" for line in [*(o.to_json() for o in observations), refusal.to_json()]))
    assert read_observations(path) == (observations, [refusal])

    report = compare(year, {"ana": [("130", year, "1T")]}, observations, {"ana": _late()})
    data = json.loads(report.to_json())
    assert data["horizon"] == year
    assert data["personas"] == ["ana"]
    assert data["covered"] == []
    assert data["gaps"] == [
        {"persona": "ana", "modelo": "303", "year": year, "period": "1T", "source": "calendar_applicable"}
    ]
    assert data["table_only"] == [
        {"persona": "ana", "modelo": "130", "year": year, "period": "1T", "app_verdict": "not_applicable"}
    ]
    text = render_markdown(report)
    assert f"horizon {year} only" in text
    assert "## ana" in text
    assert f"303 {year} 1T" in text
