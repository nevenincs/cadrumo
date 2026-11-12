"""A filing year no edition authors reaches calculation grade, never filing grade.

The registry carries the nearest authored edition across a year nobody authored, so a
projected year calculates and previews. The two human gates of a filing snapshot were
given to the edition, not to the year, so the year cannot carry a filing claim. Every
year below derives from the published authority: the newest authored exercise, the
authored exercises inside the support span, and the first exercise past the newest.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from ..authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..errors import RegistryFailureCondition, RegistryValidationError
from ..schema import ModeloRevision
from ..schema_references import TemporalProjectionDirection, reachable_authority_grade
from .authored_editions import (
    authored_revisions_where,
    newest_authored_edition,
    projected_exercise,
    revision_first_exercise,
    supported_exercises_with_projection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "100"
_PERIOD = "0A"
_AUTHORED_EXERCISES = supported_exercises_with_projection(_MODELO)[:-1]
_PROJECTED_EXERCISES = (projected_exercise(_MODELO), projected_exercise(_MODELO) + 3)


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


@pytest.mark.parametrize("year", _PROJECTED_EXERCISES)
def test_a_projected_year_refuses_a_filing_snapshot_naming_the_edition_it_is_carried_from(
    operation: PinnedAuthorityOperation, year: int
) -> None:
    with pytest.raises(RegistryValidationError) as refused:
        operation.snapshot(_MODELO, filing_year=year, period=_PERIOD, grade=RegistryAuthorityGrade.FILING)

    assert refused.value.translated_message == "errors.snapshot.filing_year_projected"
    failure = refused.value.registry_failure
    assert failure is not None
    assert failure.condition is RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT
    assert dict(failure.facts) == {
        "modelo": _MODELO,
        "revision_id": str(newest_authored_edition(_MODELO)),
        "requested_authority_grade": "filing",
        "declared_authority_grade": "calculation",
        "authority_grade_declared": True,
        "filing_year": year,
        "authored_filing_year": newest_authored_edition(_MODELO),
        "projection_direction": TemporalProjectionDirection.FORWARD.value,
    }


@pytest.mark.parametrize("year", _PROJECTED_EXERCISES)
@pytest.mark.parametrize("grade", [RegistryAuthorityGrade.APPLICABILITY, RegistryAuthorityGrade.CALCULATION])
def test_a_projected_year_still_builds_a_snapshot_below_filing_grade(
    operation: PinnedAuthorityOperation, year: int, grade: RegistryAuthorityGrade
) -> None:
    snapshot = operation.snapshot(_MODELO, filing_year=year, period=_PERIOD, grade=grade)

    assert snapshot.filing_year == year
    assert snapshot.authored_filing_year == newest_authored_edition(_MODELO)
    assert snapshot.revision_projection_direction is TemporalProjectionDirection.FORWARD
    assert snapshot.revision.id == str(newest_authored_edition(_MODELO))
    assert snapshot.effective_authority_grade is RegistryAuthorityGrade.CALCULATION


def test_the_projected_year_is_the_first_one_the_authored_exercises_do_not_cover() -> None:
    assert projected_exercise(_MODELO) == _AUTHORED_EXERCISES[-1] + 1 == newest_authored_edition(_MODELO) + 1


@pytest.mark.parametrize("year", _AUTHORED_EXERCISES)
def test_an_authored_year_keeps_its_filing_snapshot(operation: PinnedAuthorityOperation, year: int) -> None:
    snapshot = operation.snapshot(_MODELO, filing_year=year, period=_PERIOD, grade=RegistryAuthorityGrade.FILING)

    assert snapshot.authored_filing_year == year
    assert snapshot.revision_projection_direction is TemporalProjectionDirection.AUTHORED
    assert snapshot.effective_authority_grade is RegistryAuthorityGrade.FILING


@pytest.mark.parametrize("year", [*_AUTHORED_EXERCISES, *_PROJECTED_EXERCISES])
def test_the_reachable_grade_is_what_a_snapshot_of_that_year_can_be_built_at(
    operation: PinnedAuthorityOperation, year: int
) -> None:
    reachable = operation.reachable_authority_grade(_MODELO, filing_year=year, period=_PERIOD)

    snapshot = operation.snapshot(_MODELO, filing_year=year, period=_PERIOD, grade=reachable)
    assert snapshot.effective_authority_grade is reachable
    expected = RegistryAuthorityGrade.CALCULATION if year in _PROJECTED_EXERCISES else RegistryAuthorityGrade.FILING
    assert reachable is expected


@pytest.mark.parametrize("direction", list(TemporalProjectionDirection))
@pytest.mark.parametrize("declared", list(RegistryAuthorityGrade))
def test_a_projection_caps_a_declared_grade_at_calculation_and_keeps_a_lower_one(
    declared: RegistryAuthorityGrade, direction: TemporalProjectionDirection
) -> None:
    ladder = tuple(RegistryAuthorityGrade)
    reached = reachable_authority_grade(declared, direction)

    if direction is TemporalProjectionDirection.AUTHORED:
        assert reached is declared
    else:
        assert reached is min(declared, RegistryAuthorityGrade.CALCULATION, key=ladder.index)
        assert ladder.index(reached) <= ladder.index(RegistryAuthorityGrade.CALCULATION)


_HELD_BELOW_FILING = tuple(
    (modelo, revision)
    for modelo in ("100", "200")
    for revision in authored_revisions_where(
        modelo, lambda revision: revision.effective_authority_grade is not RegistryAuthorityGrade.FILING
    )
)


def test_an_edition_is_held_below_filing_grade_so_the_reading_check_has_teeth() -> None:
    assert _HELD_BELOW_FILING, (
        "no authored edition declares less than filing grade, so the reading check proves nothing"
    )


@pytest.mark.parametrize(("modelo", "revision"), _HELD_BELOW_FILING, ids=lambda item: str(getattr(item, "id", item)))
def test_an_authored_year_of_an_edition_held_below_filing_is_read_at_its_declared_grade(
    operation: PinnedAuthorityOperation, modelo: str, revision: ModeloRevision
) -> None:
    year = revision_first_exercise(modelo, str(revision.id))

    snapshot = operation.reading_snapshot(modelo, filing_year=year, period=_PERIOD)

    assert snapshot.revision.id == revision.id
    assert snapshot.revision_projection_direction is TemporalProjectionDirection.AUTHORED
    assert snapshot.effective_authority_grade is revision.effective_authority_grade
    assert snapshot.effective_authority_grade is operation.reachable_authority_grade(
        modelo, filing_year=year, period=_PERIOD
    )
