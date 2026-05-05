"""Category profile access through committed registry data."""

from __future__ import annotations

from collections.abc import Mapping

from ._profile import CategoryProfile
from ._registry import resolve_category_profiles
from ._spending_category import SpendingCategory


def load_category_profiles_from_manual(year: int) -> Mapping[SpendingCategory, CategoryProfile]:
    """Load reviewed spending-category profiles for ``year``."""

    return resolve_category_profiles(year)


__all__ = ["load_category_profiles_from_manual"]
