"""Whether the profile's stated income categories exclude a family of income, as the art. 20 other-income gate reads it.

The rule is the category rule of the suffered-withholding classes: a stated, non-empty list that lacks
every category of the family excludes it; an unstated or empty list excludes nothing, because a missing
statement is unknown rather than a statement of no income.
"""

from __future__ import annotations

import pytest

from ..profile_derived_facts import ProfileBindingResolutionError, profile_excludes_income_family

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CATEGORIES = "taxpayer_type.irpf_income_categories"


@pytest.mark.parametrize(
    ("stated", "family", "excluded"),
    [
        ("trabajo", "capital-mobiliario", True),
        ("trabajo", "capital-inmobiliario", True),
        ("trabajo", "ganancias-patrimoniales", True),
        ("trabajo, pension", "capital-mobiliario", True),
        ("trabajo,capital_mobiliario", "capital-mobiliario", False),
        ("trabajo,capital_mobiliario", "capital-inmobiliario", True),
        ("capital_inmobiliario", "capital-inmobiliario", False),
        ("ganancias_patrimoniales", "ganancias-patrimoniales", False),
        ("", "capital-mobiliario", False),
        ("  ", "ganancias-patrimoniales", False),
    ],
)
def test_a_stated_list_excludes_the_families_it_lacks(stated: str, family: str, excluded: bool) -> None:
    assert profile_excludes_income_family({_CATEGORIES: stated}, family) is excluded


def test_an_unstated_list_excludes_nothing() -> None:
    assert profile_excludes_income_family({}, "capital-mobiliario") is False


def test_an_unknown_family_is_refused() -> None:
    with pytest.raises(ProfileBindingResolutionError):
        profile_excludes_income_family({_CATEGORIES: "trabajo"}, "actividad")
