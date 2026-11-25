"""Whether the profile's stated income categories exclude a family of income, as the art. 20 other-income gate reads it.

The rule is the category rule of the suffered-withholding classes: a stated, non-empty list that lacks
every category of the family excludes it; an unstated or empty list excludes nothing, because a missing
statement is unknown rather than a statement of no income.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.tests.registry_tree import bundled_registry_tree
from ..profile_derived_facts import INCOME_FAMILY_EXCLUDED_BINDING_PREFIX, profile_excludes_income_family

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


def test_every_family_the_registry_names_is_read() -> None:
    families = {
        binding.id.removeprefix(INCOME_FAMILY_EXCLUDED_BINDING_PREFIX)
        for modelo in bundled_registry_tree()[0]
        for revision in modelo.revisions.values()
        for binding in revision.bindings
        if binding.id.startswith(INCOME_FAMILY_EXCLUDED_BINDING_PREFIX)
    }
    assert families, "no revision declares an income-family exclusion binding"
    for family in sorted(families):
        assert profile_excludes_income_family({}, family) is False
