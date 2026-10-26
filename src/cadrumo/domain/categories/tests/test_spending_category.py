"""Unit tests for the registry-backed :class:`~cadrumo.domain.categories.SpendingCategory` surface.

Locks two structural properties on the taxonomy:

* The governed catalogue is large enough (at least the project's mandated
  count of distinct deductible categories).
* Every projected :class:`~cadrumo.domain.categories.SpendingCategory` token is
  assigned to exactly one
  :class:`~cadrumo.domain.categories.SpendingCategoryFamily` through the
  public catalogue projection.
"""

from __future__ import annotations

import pytest

from ..spending_category import SpendingCategory, SpendingCategoryFamily, family_for
from ..spending_category_catalogue import resolve_spending_category_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def test_spending_category_catalogue_is_large_enough() -> None:
    """The taxonomy must expose at least the mandated category count."""

    catalogue = resolve_spending_category_catalogue()
    assert len(catalogue.categories) >= 25


def test_every_category_belongs_to_exactly_one_family() -> None:
    """Each category must be assigned to one and only one coarse family."""

    catalogue = resolve_spending_category_catalogue()
    memberships: dict[SpendingCategory, int] = dict.fromkeys(catalogue.categories, 0)
    for family in SpendingCategoryFamily:
        for category in catalogue.categories_for_family(family):
            memberships[category] += 1
            assert family_for(category) is family
    offenders = {category.value: count for category, count in memberships.items() if count != 1}
    assert offenders == {}
