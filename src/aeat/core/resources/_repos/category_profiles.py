"""Year-keyed spending-category profile repository.

:class:`CategoryProfileRepository` adapts category-profile lookups to the
:class:`ResourceCacheRepository` interface aggregated by :class:`ResourceRegistry`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from .._repository import ResourceCacheRepository

if TYPE_CHECKING:
    from ....domain.categories import CategoryProfile, SpendingCategory


class CategoryProfileRepository(ResourceCacheRepository[Mapping["SpendingCategory", "CategoryProfile"], int]):
    """Year-keyed repository for spending-category profile registries.

    Wraps :func:`aeat.domain.categories.resolve_category_profiles`
    and returns mappings from :class:`SpendingCategory` to
    :class:`CategoryProfile`.
    """

    @override
    def _load(self, key: int) -> Mapping[SpendingCategory, CategoryProfile]:
        from ....domain.categories import resolve_category_profiles

        return resolve_category_profiles(key)
