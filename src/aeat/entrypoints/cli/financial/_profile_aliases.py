"""Family-alias mapping for the ``aeat financial profile`` CLI.

Aliases expand a single user-facing key (e.g. ``home_office_area``) into
a tuple of concrete :class:`aeat.domain.categories.SpendingCategory`
values at CLI parse time. They are **CLI-only sugar**:
:class:`aeat.domain.categories.UsageRatioProfile` only persists
category-keyed entries, and the library never stores alias names.

This module is intentionally private to the CLI layer so that non-CLI
consumers (the setup wizard, the deductibility compute) cannot
cargo-cult the alias taxonomy into onboarding prompts or compute paths.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ....domain.categories import (
    CATEGORY_PROFILES_2025,
    ProportionalityKind,
    SpendingCategory,
)

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
    }
)
"""Read-only mapping from CLI alias names to concrete spending categories.

``phone_fixed_business`` is deliberately absent: ``TELEFONIA_FIJA``
already belongs to ``home_office_area`` (it is a
``USAGE_RATIO_HOME_AREA`` category), so the two aliases would overlap
and a sequential ``set-ratio home_office_area`` followed by
``set-ratio phone_fixed_business`` would silently clobber the earlier
value. The operator can type ``telefonia_fija`` directly for
single-category edits.
"""
