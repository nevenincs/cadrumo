"""CategoryProfileRepository: int-year-keyed spending-category profiles."""

from __future__ import annotations

from collections.abc import Mapping

from .._repository import ResourceCacheRepository


class CategoryProfileRepository(ResourceCacheRepository[Mapping[object, object], int]):
    """Year-keyed repository for spending-category profile registries.

    Wraps :func:`aeat.domain.categories.resolve_category_profiles`.
    """

    def _load(self, key: int) -> Mapping[object, object]:
        from ....domain.categories import resolve_category_profiles

        return resolve_category_profiles(key)
