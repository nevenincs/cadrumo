"""CategoryProfileRepository: int-year-keyed spending-category profiles."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from .._repository import ResourceCacheRepository

if TYPE_CHECKING:
    from ....domain.categories import CategoryProfile, SpendingCategory


class CategoryProfileRepository(
    ResourceCacheRepository[Mapping["SpendingCategory", "CategoryProfile"], int]
):
    """Year-keyed repository for spending-category profile registries.

    Wraps :func:`aeat.domain.categories.resolve_category_profiles`.
    """

    def _load(self, key: int) -> Mapping[SpendingCategory, CategoryProfile]:
        from ....domain.categories import resolve_category_profiles

        return resolve_category_profiles(key)
