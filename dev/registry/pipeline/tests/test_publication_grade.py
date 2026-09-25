"""The static-publication grade floor is one rung of the canonical authority ladder."""

from __future__ import annotations

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade

from ..publication_grade import reaches_static_publication_grade, static_publication_authority_grade

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_floor_is_calculation_grade() -> None:
    assert static_publication_authority_grade() is RegistryAuthorityGrade.CALCULATION


@pytest.mark.parametrize(
    ("grade", "reaches"),
    [
        (RegistryAuthorityGrade.APPLICABILITY, False),
        (RegistryAuthorityGrade.CALCULATION, True),
        (RegistryAuthorityGrade.FILING, True),
    ],
)
def test_every_rung_at_or_above_the_floor_reaches_it(grade: RegistryAuthorityGrade, reaches: bool) -> None:
    assert reaches_static_publication_grade(grade) is reaches


def test_every_declared_rung_is_classified() -> None:
    """A rung added to the ladder is placed relative to the floor by its position alone."""
    ladder = tuple(RegistryAuthorityGrade)
    floor = ladder.index(static_publication_authority_grade())
    assert [reaches_static_publication_grade(grade) for grade in ladder] == [
        index >= floor for index in range(len(ladder))
    ]
