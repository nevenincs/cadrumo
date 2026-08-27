"""Real-behaviour contract for the closed validity window primitive.

The refusal proofs are the point of this module. A window whose bounds are
optional degrades silently -- an absent start sorts as ``date.min`` and an
absent end reads as "until further notice" -- so the tests that matter here are
the ones proving the model refuses those shapes rather than defaulting them.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from cadrumo.core.validity_window import (
    ValidityWindow,
    years_covered_by_any,
    years_covered_by_every_group,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _window(start: str, end: str) -> ValidityWindow:
    return ValidityWindow(valid_from=date.fromisoformat(start), valid_to=date.fromisoformat(end))


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"valid_to": date(2025, 12, 31)}, id="start-omitted"),
        pytest.param({"valid_from": date(2025, 1, 1)}, id="end-omitted"),
        pytest.param({}, id="both-omitted"),
    ],
)
def test_an_omitted_bound_is_refused_rather_than_defaulted(payload: dict[str, date]) -> None:
    """Neither bound may be defaulted; a missing one is a refusal at construction.

    This is the anti-silent-partial-adoption proof. If either field ever gains a
    default, this test reds before any corpus can acquire an undated row that
    resolves as effective from the beginning of time.
    """
    with pytest.raises(ValidationError):
        ValidityWindow.model_validate(payload)


def test_an_inverted_span_is_refused_where_it_is_written() -> None:
    with pytest.raises(ValidationError, match="ends before it starts"):
        _window("2025-12-31", "2025-01-01")


def test_a_single_day_span_is_legal() -> None:
    window = _window("2025-06-01", "2025-06-01")

    assert window.covers(date(2025, 6, 1))
    assert window.years() == (2025,)


def test_the_window_is_frozen_and_forbids_extra_fields() -> None:
    window = _window("2025-01-01", "2025-12-31")

    with pytest.raises(ValidationError):
        window.valid_from = date(2024, 1, 1)  # ty: ignore[invalid-assignment]

    with pytest.raises(ValidationError):
        ValidityWindow.model_validate(
            {"valid_from": date(2025, 1, 1), "valid_to": date(2025, 12, 31), "note": "x"},
        )


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        pytest.param("2024-12-31", False, id="day-before"),
        pytest.param("2025-01-01", True, id="first-day-inclusive"),
        pytest.param("2025-12-31", True, id="last-day-inclusive"),
        pytest.param("2026-01-01", False, id="day-after"),
    ],
)
def test_coverage_is_closed_at_both_ends(moment: str, expected: bool) -> None:
    assert _window("2025-01-01", "2025-12-31").covers(date.fromisoformat(moment)) is expected


def test_a_year_is_covered_when_the_span_touches_any_part_of_it() -> None:
    """A provision effective mid-year is in force for that whole filing year.

    Containment would be the wrong test: it would report 2021 uncovered for a
    provision that took effect on 1 July 2021 and is still in force, which is a
    statement about the calendar rather than about the law.
    """
    mid_year_start = _window("2021-07-01", "2026-12-31")

    assert mid_year_start.covers_year(2021)
    assert mid_year_start.covers_year(2026)
    assert not mid_year_start.covers_year(2020)
    assert not mid_year_start.covers_year(2027)


def test_years_enumerates_every_touched_year_ascending() -> None:
    assert _window("2022-03-04", "2025-02-01").years() == (2022, 2023, 2024, 2025)


def test_union_over_windows_collects_every_touched_year() -> None:
    covered = years_covered_by_any([_window("2022-01-01", "2022-12-31"), _window("2025-01-01", "2026-12-31")])

    assert covered == frozenset({2022, 2025, 2026})


def test_union_over_no_windows_is_empty() -> None:
    assert years_covered_by_any([]) == frozenset()


def test_a_corpus_year_needs_every_record_to_carry_evidence() -> None:
    """One record whose evidence stops early stops the corpus for that year."""
    wide = [_window("2022-01-01", "2026-12-31")]
    narrow = [_window("2025-01-01", "2025-12-31")]

    assert years_covered_by_every_group([wide, wide]) == frozenset({2022, 2023, 2024, 2025, 2026})
    assert years_covered_by_every_group([wide, narrow]) == frozenset({2025})


def test_a_record_carrying_no_window_is_grounded_nowhere() -> None:
    assert years_covered_by_every_group([[_window("2022-01-01", "2026-12-31")], []]) == frozenset()


def test_no_groups_yields_nothing_rather_than_everything() -> None:
    """An empty corpus must not read as covering every year by vacuous truth."""
    assert years_covered_by_every_group([]) == frozenset()


def test_a_record_may_carry_several_windows_and_their_union_counts() -> None:
    """Two disjoint evidence spans on one record cover both, and not the gap."""
    split = [_window("2022-01-01", "2022-12-31"), _window("2025-01-01", "2025-12-31")]

    assert years_covered_by_every_group([split]) == frozenset({2022, 2025})
