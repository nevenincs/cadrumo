"""Unit tests for the spending-category enum surface."""

from __future__ import annotations

import pytest

from aeat.financial.categories import CATEGORY_FAMILY_MEMBERS, SpendingCategory, SpendingCategoryFamily, family_for

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


def test_spending_category_catalogue_is_large_enough() -> None:
    """The taxonomy must expose at least the mandated category count."""

    assert len(SpendingCategory) >= 25


def test_every_category_belongs_to_exactly_one_family() -> None:
    """Each category must be assigned to one and only one coarse family."""

    memberships = {category: 0 for category in SpendingCategory}
    for family in SpendingCategoryFamily:
        for category in CATEGORY_FAMILY_MEMBERS[family]:
            memberships[category] += 1
            assert family_for(category) is family
    assert all(count == 1 for count in memberships.values())
