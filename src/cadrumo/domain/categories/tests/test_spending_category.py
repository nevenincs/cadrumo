"""Unit tests for the :class:`~cadrumo.domain.categories.SpendingCategory` enum surface.

Locks two structural properties on the taxonomy:

* The catalogue is large enough (at least the project's mandated
  count of distinct deductible categories).
* Every :class:`~cadrumo.domain.categories.SpendingCategory` member is
  assigned to exactly one
  :class:`~cadrumo.domain.categories.SpendingCategoryFamily` via the
  :data:`~cadrumo.domain.categories.CATEGORY_FAMILY_MEMBERS` table.
"""

from __future__ import annotations

import pytest

from ..spending_category import CATEGORY_FAMILY_MEMBERS, SpendingCategory, SpendingCategoryFamily, family_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_spending_category_catalogue_is_large_enough() -> None:
    """The taxonomy must expose at least the mandated category count."""

    assert len(SpendingCategory) >= 25


def test_every_category_belongs_to_exactly_one_family() -> None:
    """Each category must be assigned to one and only one coarse family."""

    memberships = dict.fromkeys(SpendingCategory, 0)
    for family in SpendingCategoryFamily:
        for category in CATEGORY_FAMILY_MEMBERS[family]:
            memberships[category] += 1
            assert family_for(category) is family
    offenders = {category.value: count for category, count in memberships.items() if count != 1}
    assert offenders == {}
