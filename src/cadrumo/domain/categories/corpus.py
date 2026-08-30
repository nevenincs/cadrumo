"""Category profile access through committed registry data.

:func:`load_category_profiles_from_manual` is the registry-backed facade over
:func:`resolve_category_profiles`, returning year-keyed mappings from
:class:`SpendingCategory` to :class:`CategoryProfile`.
"""

from __future__ import annotations

from collections.abc import Mapping

from .profile import CategoryProfile
from .registry import resolve_category_profiles
from .spending_category import SpendingCategory


def load_category_profiles_from_manual(year: int) -> Mapping[SpendingCategory, CategoryProfile]:
    """Load reviewed spending-category profiles for ``year``.

    Returns:
        Mapping from :class:`SpendingCategory` to :class:`CategoryProfile` for the given year.
    """
    return resolve_category_profiles(year)


__all__ = ["load_category_profiles_from_manual"]
