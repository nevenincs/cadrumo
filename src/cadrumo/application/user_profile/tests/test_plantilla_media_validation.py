"""The profile boundary refuses every malformed average-workforce instance.

Each rule fails closed and names the path it refuses: the year is a whole
calendar year from 2000 to 2100, the workforce is zero or more with at most two
decimal places and is never rounded, the state is observed or committed, every
instance states all three subfields, and a year is declared by one instance.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.calculations.registry.tests.published_authority import published_profile_schema
from ....domain.user_profile.plantilla_media import (
    PlantillaMediaState,
    PlantillaMediaYear,
    plantilla_media_years,
)
from ....domain.user_profile.values import UserProfileFact
from ..validation import (
    ENUM_VALUE_ISSUE_CODE,
    INDEXED_INSTANCE_INVALID_CODE,
    NUMERIC_VALUE_ISSUE_CODE,
    UNKNOWN_FIELD_ISSUE_CODE,
    ProfileValidationService,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_ROOT = "irpf.plantilla_media"


def _instance(
    index: int, *, year: object = 2024, workforce: object = Decimal("12.50"), state: object = "observed"
) -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path=f"{_ROOT}.{index}.year", value=year),
        UserProfileFact(path=f"{_ROOT}.{index}.average_workforce", value=workforce),
        UserProfileFact(path=f"{_ROOT}.{index}.state", value=state),
    )


def _issues(*facts: UserProfileFact) -> set[tuple[str, str]]:
    report = ProfileValidationService(schema=published_profile_schema()).validate_facts(
        "3f8b1d42-6c07-4e59-9a13-2b7e5c04d8af", facts
    )
    return {(issue.path or "", issue.code) for issue in report.issues if (issue.path or "").startswith(_ROOT)}


def test_well_formed_instances_are_admitted() -> None:
    assert _issues(*_instance(0), *_instance(1, year=2025, workforce=7, state="committed")) == set()


@pytest.mark.parametrize("year", (1999, 2101, Decimal("2024.5"), True), ids=str)
def test_a_year_outside_the_calendar_range_or_not_whole_is_refused(year: object) -> None:
    assert _issues(*_instance(0, year=year)) == {(f"{_ROOT}.0.year", NUMERIC_VALUE_ISSUE_CODE)}


@pytest.mark.parametrize("workforce", (Decimal("-0.01"), "doce", False), ids=str)
def test_a_negative_or_non_numeric_workforce_is_refused(workforce: object) -> None:
    assert _issues(*_instance(0, workforce=workforce)) == {(f"{_ROOT}.0.average_workforce", NUMERIC_VALUE_ISSUE_CODE)}


def test_a_workforce_with_three_decimal_places_is_refused_not_rounded() -> None:
    report = ProfileValidationService(schema=published_profile_schema()).validate_facts(
        "3f8b1d42-6c07-4e59-9a13-2b7e5c04d8af",
        _instance(0, workforce=Decimal("12.345")),
    )

    (issue,) = [issue for issue in report.issues if issue.path == f"{_ROOT}.0.average_workforce"]
    assert issue.code == NUMERIC_VALUE_ISSUE_CODE
    assert "never rounded" in issue.message


def test_a_state_outside_observed_or_committed_is_refused() -> None:
    assert _issues(*_instance(0, state="estimated")) == {(f"{_ROOT}.0.state", ENUM_VALUE_ISSUE_CODE)}


@pytest.mark.parametrize("dropped", ("year", "average_workforce", "state"))
def test_an_instance_missing_a_subfield_is_refused(dropped: str) -> None:
    facts = tuple(fact for fact in _instance(0) if not fact.path.endswith(f".{dropped}"))

    assert _issues(*facts) == {(f"{_ROOT}.0", INDEXED_INSTANCE_INVALID_CODE)}


def test_a_duplicate_year_is_refused_rather_than_the_last_one_winning() -> None:
    issues = _issues(*_instance(0), *_instance(1, workforce=Decimal("30.00")))

    assert issues == {(f"{_ROOT}.1.year", INDEXED_INSTANCE_INVALID_CODE)}


@pytest.mark.parametrize("path", (f"{_ROOT}.0.headcount", _ROOT, f"{_ROOT}.first.year"))
def test_a_path_that_is_not_an_instance_subfield_is_refused(path: str) -> None:
    assert (path, UNKNOWN_FIELD_ISSUE_CODE) in _issues(UserProfileFact(path=path, value=3))


def test_the_typed_projection_keeps_the_year_the_exact_decimal_and_the_state() -> None:
    values = {
        fact.path: fact.value
        for fact in (*_instance(0, year=2025, state="committed"), *_instance(1, workforce=Decimal("3.10")))
    }

    assert plantilla_media_years(values) == (
        PlantillaMediaYear(year=2024, average_workforce=Decimal("3.10"), state=PlantillaMediaState.OBSERVED),
        PlantillaMediaYear(year=2025, average_workforce=Decimal("12.50"), state=PlantillaMediaState.COMMITTED),
    )
