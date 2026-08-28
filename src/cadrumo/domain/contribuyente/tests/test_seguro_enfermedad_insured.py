"""Who LIRPF art. 30.2.5.a insures, and which limit each of them carries.

The article insures the contribuyente, the conyuge, and hijos menores de
veinticinco anos que convivan con el, and caps the deduction at 500 euros per such
person or 1.500 for each with discapacidad. Membership and limb are separate
questions and this module keeps them apart: discapacidad chooses the limit, it does
not widen who is covered.

The population is deliberately narrower than the Art. 58.1 minimo one, which admits
a descendant on cohabitation OR assimilated economic dependency and on age under 25
OR any discapacidad. Borrowing that set would extend this cap to a non-cohabiting
dependent child and to an over-25 child with discapacidad, neither of whom this
article names.
"""

from __future__ import annotations

from datetime import date

import pytest

from .._descendant import DescendantInfo
from ..seguro_enfermedad_insured import (
    DISCAPACIDAD_MINIMUM_GRADE,
    count_seguro_enfermedad_insured,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _child(
    *,
    born: date,
    grado: int | None = None,
    convive: bool = True,
    died: date | None = None,
) -> DescendantInfo:
    return DescendantInfo.model_validate(
        {
            "birth_date": born,
            "discapacidad_grado": grado,
            "convive_con_contribuyente": convive,
            "death_date": died,
        },
    )


def _counts(*children: DescendantInfo, **kwargs: object):
    return count_seguro_enfermedad_insured(children, filing_year=2025, **kwargs)  # ty: ignore[invalid-argument-type]


def test_the_contribuyente_is_always_insured() -> None:
    """The article insures "su propia cobertura" with no further condition."""
    assert _counts().model_dump() == {"general": 1, "discapacidad": 0}


def test_the_taxpayers_own_grade_chooses_their_limb() -> None:
    assert _counts(taxpayer_discapacidad_grado=65).model_dump() == {"general": 0, "discapacidad": 1}
    assert _counts(taxpayer_discapacidad_grado=0).model_dump() == {"general": 1, "discapacidad": 0}


def test_the_conyuge_counts_only_when_one_is_declared() -> None:
    """A grado on an undeclared spouse must not conjure a person into the count."""
    assert _counts(spouse_discapacidad_grado=65).total == 1
    assert _counts(has_spouse=True, spouse_discapacidad_grado=65).model_dump() == {
        "general": 1,
        "discapacidad": 1,
    }


@pytest.mark.parametrize(
    ("grado", "expected"),
    [
        # One child plus the contribuyente, so the ordinary cases carry two.
        pytest.param(None, {"general": 2, "discapacidad": 0}, id="undeclared-takes-the-ordinary-limit"),
        pytest.param(0, {"general": 2, "discapacidad": 0}, id="declared-zero"),
        pytest.param(33, {"general": 1, "discapacidad": 1}, id="at-the-art-72-threshold"),
        pytest.param(65, {"general": 1, "discapacidad": 1}, id="above-it"),
    ],
)
def test_the_art_72_threshold_partitions_the_limbs(grado: int | None, expected: dict[str, int]) -> None:
    """RIRPF art. 72 qualifies a grado "igual o superior al 33 por ciento".

    An UNDECLARED grado takes the ordinary limit rather than dropping the person.
    Membership is already settled; only the limb is unknown, and the article grants
    the ordinary limit absent the condition the higher one requires. Dropping them
    would cost the filer 500 euros of allowance for a person the article covers.
    """
    counts = _counts(_child(born=date(2010, 1, 1), grado=grado))

    assert counts.model_dump() == expected


def test_the_threshold_is_the_one_art_72_states() -> None:
    assert DISCAPACIDAD_MINIMUM_GRADE == 33


def test_a_child_who_does_not_cohabit_is_outside_the_article() -> None:
    """ "Que convivan con el" is a condition of membership, not a preference.

    Art. 58.1 would still admit this child on assimilated economic dependency;
    this article does not, and borrowing that limb would over-grant.
    """
    assert _counts(_child(born=date(2010, 1, 1), convive=False)).total == 1


def test_a_child_of_twenty_five_or_more_is_outside_the_article() -> None:
    """ "Hijos menores de veinticinco anos", measured at year-end."""
    assert _counts(_child(born=date(2000, 1, 1))).total == 1
    assert _counts(_child(born=date(2001, 6, 1))).total == 2


def test_discapacidad_does_not_widen_membership_only_the_limit() -> None:
    """The trap this article shares with Art. 58.1, and where the two part company.

    Art. 58.1 admits a descendant on "under 25 OR any discapacidad", so an over-25
    child with discapacidad is in its minimo population. This article names only
    hijos menores de veinticinco anos, so the same child is outside it entirely --
    and would otherwise raise the cap by 1.500 euros for a person it does not cover.
    """
    over_25_with_discapacidad = _child(born=date(1995, 1, 1), grado=65)

    assert _counts(over_25_with_discapacidad).total == 1


def test_a_child_who_died_before_the_filing_year_is_not_counted() -> None:
    """Birth date alone goes on satisfying the age limb indefinitely."""
    assert _counts(_child(born=date(2010, 1, 1), died=date(2023, 5, 1))).total == 1


def test_a_child_who_died_during_the_filing_year_is_still_counted() -> None:
    """The premium was paid on cover the article allowed while they lived."""
    assert _counts(_child(born=date(2010, 1, 1), died=date(2025, 5, 1))).total == 2


def test_a_household_sums_both_limbs_across_every_insured_person() -> None:
    """The whole shape: the cap is a sum over two populations, not one times a count."""
    counts = _counts(
        _child(born=date(2010, 1, 1)),
        _child(born=date(2015, 1, 1), grado=65),
        has_spouse=True,
    )

    assert counts.model_dump() == {"general": 3, "discapacidad": 1}
    assert counts.total == 4
