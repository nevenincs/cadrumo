"""Unit tests for the usage-ratio family-alias mapping (#259)."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from ..categories import SpendingCategory
from . import ELIGIBLE_USAGE_RATIO_CATEGORIES, FAMILY_ALIASES

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


def test_home_office_area_covers_six_categories() -> None:
    """``home_office_area`` expands to every USAGE_RATIO_HOME_AREA category."""
    expected = (
        SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_GAS,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
        SpendingCategory.TELEFONIA_FIJA,
    )
    assert FAMILY_ALIASES["home_office_area"] == expected


def test_mileage_business_covers_five_vehicle_categories() -> None:
    """``mileage_business`` expands to every vehicle USAGE_RATIO_PERSONAL category."""
    assert FAMILY_ALIASES["mileage_business"] == (
        SpendingCategory.VEHICULO_COMBUSTIBLE,
        SpendingCategory.VEHICULO_MANTENIMIENTO,
        SpendingCategory.VEHICULO_SEGURO,
        SpendingCategory.VEHICULO_PEAJE,
        SpendingCategory.VEHICULO_PARKING,
    )


def test_phone_fixed_business_is_singleton() -> None:
    assert FAMILY_ALIASES["phone_fixed_business"] == (SpendingCategory.TELEFONIA_FIJA,)


def test_every_aliased_category_is_eligible() -> None:
    """Every category exposed via an alias must be persistable."""
    for members in FAMILY_ALIASES.values():
        for category in members:
            assert category in ELIGIBLE_USAGE_RATIO_CATEGORIES


def test_aliases_reject_mutation_at_runtime() -> None:
    """Attempting to add an alias at runtime raises, regardless of backing type.

    The behavioural guarantee survives any refactor away from ``MappingProxyType``
    (e.g. to ``frozendict``) as long as the new type is also immutable.
    """
    with pytest.raises(TypeError):
        # Route through the runtime setitem path without tripping the static
        # type checker — the point is that the runtime itself rejects mutation.
        operator_setitem = getattr(type(FAMILY_ALIASES), "__setitem__", None)
        if operator_setitem is None:
            raise TypeError("MappingProxyType has no __setitem__")
        operator_setitem(FAMILY_ALIASES, "new_alias", (SpendingCategory.TELEFONIA_MOVIL,))


def test_aliases_are_mapping_proxy() -> None:
    """``FAMILY_ALIASES`` is wrapped in a ``MappingProxyType`` so its
    mutability is a language-level guarantee, not a type-hint-only promise."""
    assert isinstance(FAMILY_ALIASES, MappingProxyType)
