"""Real-behavior tests for the census-override warning helper.

Locks the contract that
:func:`aeat.application.ledger._ratios.census_override_warning` returns
a typed warning when an operator's per-category override for a
HOME_OFFICE category deviates from the legally-binding census-derived
value, and stays silent for non-HOME_OFFICE categories.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ...domain.categories import SpendingCategory
from ._ratios import RatiosCensusOverrideWarning, census_override_warning


pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_no_warning_for_non_home_office_category() -> None:
    result = census_override_warning(
        category=SpendingCategory.TELEFONIA_MOVIL,
        override_ratio=Decimal("0.50"),
        raw_afectacion_ratio=Decimal("0.20"),
    )

    assert result is None


def test_warning_emitted_when_home_office_override_diverges() -> None:
    result = census_override_warning(
        category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
        override_ratio=Decimal("0.50"),
        raw_afectacion_ratio=Decimal("0.20"),
    )

    assert isinstance(result, RatiosCensusOverrideWarning)
    assert result.category is SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ
    assert result.override_ratio == Decimal("0.50")
    assert result.raw_afectacion_ratio == Decimal("0.20")


def test_no_warning_when_override_matches_census_derived_value() -> None:
    raw = Decimal("0.20")
    result_suministros = census_override_warning(
        category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
        override_ratio=raw,
        raw_afectacion_ratio=raw,
    )
    result_ownership = census_override_warning(
        category=SpendingCategory.AMORTIZACION_VIVIENDA_AFECTO,
        override_ratio=raw,
        raw_afectacion_ratio=raw,
    )

    assert result_suministros is None
    assert result_ownership is None


def test_warning_carries_census_derived_ratio() -> None:
    result = census_override_warning(
        category=SpendingCategory.IBI_VIVIENDA_AFECTO,
        override_ratio=Decimal("0.40"),
        raw_afectacion_ratio=Decimal("0.20"),
    )

    assert result is not None
    assert result.census_derived_ratio == Decimal("0.20")
