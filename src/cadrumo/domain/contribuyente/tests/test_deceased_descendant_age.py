"""A descendant who died in the period is aged at their death, not at year-end.

Art. 61 norma 4ª exists BECAUSE the deceased is absent at the devengo: it grants
a flat cuantía for a descendant who cannot be present on 31 December. Aging that
descendant to 31 December anyway returns an age they never reached, and defeats
the provision's own premise.

The failure is invisible for most of the year. It only appears when the birthday
falls BETWEEN the death and 31 December, so the straddling fixtures below are the
whole test -- a child who died after their birthday ages identically either way.
That is why the existing norma 4ª suite could not catch this: every one of its
fixtures uses a 1 January birth date, which puts the birthday before any death in
the period and makes the straddle unreachable by construction. Not a test
blessing the defect; a fixture set that could not express it.

Both consequences run the same direction -- **under-granting a bereaved filer**,
which is the error direction nothing else in this codebase watches, because every
other gate here is built against under-declaration.
"""

from __future__ import annotations

from datetime import date

import pytest

from ..descendant import DescendantInfo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _descendant(*, birth: date, death: date | None) -> DescendantInfo:
    return DescendantInfo(birth_date=birth, death_date=death, convive_con_contribuyente=True)


def test_a_descendant_who_died_before_their_birthday_is_aged_at_death() -> None:
    """The Art. 58.1 age limb must see the age they actually reached.

    Born 1999-05-10, died 2024-03-01 at twenty-four. Aged to year-end they read
    twenty-five, fail the age limb, and the flat cuantía is never reached --
    the whole mínimo is lost for the bereaved filer.
    """
    died = _descendant(birth=date(1999, 5, 10), death=date(2024, 3, 1))

    assert died.age_at_year_end(2024) == 24


def test_a_toddler_who_died_before_turning_three_is_aged_at_death() -> None:
    """The menor-tres increment turns on this age, so the same slip costs it.

    Born 2021-09-10, died 2024-02-01 at two. Aged to year-end they read three
    and lose the increment the aggregate's own docstring cites the AEAT manual
    as granting to a descendant who died during the period.
    """
    died = _descendant(birth=date(2021, 9, 10), death=date(2024, 2, 1))

    assert died.age_at_year_end(2024) == 2


def test_a_death_after_the_birthday_ages_identically_to_year_end() -> None:
    """Positive control: the mechanism is the straddle, not death handling.

    Without this, both assertions above are equally consistent with "any death
    lowers the age by one", which would be a different and wrong rule.
    """
    died = _descendant(birth=date(2000, 1, 10), death=date(2024, 3, 1))

    assert died.age_at_year_end(2024) == 24


def test_a_living_descendant_is_still_aged_at_year_end() -> None:
    """Control: the ordinary path is untouched.

    Same birth date as the first case. A living descendant reaches their
    birthday, so 31 December remains the correct reference.
    """
    alive = _descendant(birth=date(1999, 5, 10), death=None)

    assert alive.age_at_year_end(2024) == 25


def test_a_death_in_a_prior_year_does_not_move_the_reference() -> None:
    """A prior-year death is excluded upstream, so this must not silently age them.

    ``meets_non_income_conditions`` fails ``death_date.year < filing_year``
    before any age question is asked. Aging to the death date here as well would
    reach back into a closed period and answer a question the caller never asks
    -- and would read as intentional to the next reader.
    """
    long_dead = _descendant(birth=date(1999, 5, 10), death=date(2020, 3, 1))

    assert long_dead.age_at_year_end(2024) == 25
