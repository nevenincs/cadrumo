"""Real-behavior tests for the censo-override warning helper.

Locks the contract that
:func:`cadrumo.application.ledger.ratios.censo_override_warning` returns
a typed warning when an operator's per-category override for a
HOME_OFFICE category deviates from the legally-binding censo-derived
value, and stays silent for non-HOME_OFFICE categories.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.categories.spending_category import SpendingCategory
from ..ratios import (
    RatiosCensoOverrideWarning,
    censo_business_pct_for,
    censo_override_warning,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_no_warning_for_non_home_office_category() -> None:
    result = censo_override_warning(
        category=SpendingCategory.TELEFONIA_MOVIL,
        override_ratio=Decimal("0.50"),
        raw_afectacion_ratio=Decimal("0.20"),
        year=2025,
    )

    assert result is None


def test_warning_emitted_when_home_office_override_diverges() -> None:
    result = censo_override_warning(
        category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
        override_ratio=Decimal("0.50"),
        raw_afectacion_ratio=Decimal("0.20"),
        year=2025,
    )

    assert isinstance(result, RatiosCensoOverrideWarning)
    assert result.category is SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ
    assert result.override_ratio == Decimal("0.50")
    assert result.raw_afectacion_ratio == Decimal("0.20")


def test_no_warning_when_suministros_override_matches_30pct_of_raw() -> None:
    """When the operator-set ratio equals raw * 0.30 (LIRPF Art. 30.2 rule 5),
    no warning fires for suministros categories."""

    raw = Decimal("0.20")

    result = censo_override_warning(
        category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
        override_ratio=Decimal("0.060"),
        raw_afectacion_ratio=raw,
        year=2025,
    )

    assert result is None


def test_no_warning_when_ownership_override_matches_raw_afectacion() -> None:
    """When the operator-set ratio equals the raw afectación ratio, no warning
    fires for titularidad categories (no statutory multiplier)."""

    raw = Decimal("0.20")

    result = censo_override_warning(
        category=SpendingCategory.AMORTIZACION_VIVIENDA_AFECTO,
        override_ratio=raw,
        raw_afectacion_ratio=raw,
        year=2025,
    )

    assert result is None


def test_business_pct_is_none_when_censo_unset() -> None:
    assert (
        censo_business_pct_for(
            SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
            None,
            year=2025,
        )
        is None
    )


def test_business_pct_is_none_for_non_home_office_category() -> None:
    assert (
        censo_business_pct_for(
            SpendingCategory.TELEFONIA_MOVIL,
            Decimal("0.20"),
            year=2025,
        )
        is None
    )


def test_business_pct_for_suministros_applies_lirpf_30_2_rule_5_factor() -> None:
    """Suministros home-office categories deduct at raw * 0.30 (LIRPF Art. 30.2 rule 5)."""

    raw = Decimal("0.20")

    suministros = censo_business_pct_for(
        SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA,
        raw,
        year=2025,
    )

    assert suministros == Decimal("0.060")


def test_business_pct_for_ownership_uses_raw_afectacion() -> None:
    """Ownership home-office categories deduct at the raw afectación ratio."""

    raw = Decimal("0.20")

    ownership = censo_business_pct_for(
        SpendingCategory.COMUNIDAD_VIVIENDA_AFECTO,
        raw,
        year=2025,
    )

    assert ownership == raw


def test_warning_carries_censo_derived_ratio() -> None:
    result = censo_override_warning(
        category=SpendingCategory.IBI_VIVIENDA_AFECTO,
        override_ratio=Decimal("0.40"),
        raw_afectacion_ratio=Decimal("0.20"),
        year=2025,
    )

    assert result is not None
    assert result.censo_derived_ratio == Decimal("0.20")
