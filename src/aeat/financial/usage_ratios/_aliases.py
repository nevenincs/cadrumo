"""Family-alias mapping for the usage-ratio CLI (issue #259).

Aliases expand a single user-facing key (e.g. ``home_office_area``) into a
tuple of concrete :class:`SpendingCategory` values at CLI parse time. They are
never stored — :class:`UsageRatioProfile` only persists category-keyed entries.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ..categories import CATEGORY_PROFILES_2025, ProportionalityKind, SpendingCategory

__all__ = ["FAMILY_ALIASES"]


def _home_office_area_members() -> tuple[SpendingCategory, ...]:
    return tuple(
        sorted(
            (
                category
                for category, profile in CATEGORY_PROFILES_2025.items()
                if profile.proportionality.kind is ProportionalityKind.USAGE_RATIO_HOME_AREA
            ),
            key=lambda c: c.value,
        )
    )


def _mileage_business_members() -> tuple[SpendingCategory, ...]:
    return (
        SpendingCategory.VEHICULO_COMBUSTIBLE,
        SpendingCategory.VEHICULO_MANTENIMIENTO,
        SpendingCategory.VEHICULO_SEGURO,
        SpendingCategory.VEHICULO_PEAJE,
        SpendingCategory.VEHICULO_PARKING,
    )


FAMILY_ALIASES: Mapping[str, tuple[SpendingCategory, ...]] = MappingProxyType(
    {
        "home_office_area": _home_office_area_members(),
        "mileage_business": _mileage_business_members(),
        "phone_fixed_business": (SpendingCategory.TELEFONIA_FIJA,),
    }
)
