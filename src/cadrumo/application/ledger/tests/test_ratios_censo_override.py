"""Real-behavior tests for the censo-override warning helper.

Locks the contract that
:func:`cadrumo.application.ledger.ratios.censo_override_warning` returns
a typed warning when an operator's per-category override for a
HOME_OFFICE category deviates from the legally-binding censo-derived
value, and stays silent for non-HOME_OFFICE categories.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.categories.spending_category import SpendingCategory
from ....domain.categories.spending_category_catalogue import require_spending_category
from ..ratios import (
    RatiosCensoOverrideWarning,
    censo_business_pct_for,
    censo_override_warning,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _category(value: str, operation: PinnedAuthorityOperation) -> SpendingCategory:
    return require_spending_category(value, effective_date=date(2025, 12, 31), authority=operation)


def test_no_warning_for_non_home_office_category(operation: PinnedAuthorityOperation) -> None:
    result = censo_override_warning(
        category=_category("telefonia_movil", operation),
        override_ratio=Decimal("0.50"),
        raw_afectacion_ratio=Decimal("0.20"),
        year=2025,
        operation=operation,
    )

    assert result is None


def test_warning_emitted_when_home_office_override_diverges(operation: PinnedAuthorityOperation) -> None:
    result = censo_override_warning(
        category=_category("suministros_home_office_luz", operation),
        override_ratio=Decimal("0.50"),
        raw_afectacion_ratio=Decimal("0.20"),
        year=2025,
        operation=operation,
    )

    assert isinstance(result, RatiosCensoOverrideWarning)
    assert result.category == _category("suministros_home_office_luz", operation)
    assert result.override_ratio == Decimal("0.50")
    assert result.raw_afectacion_ratio == Decimal("0.20")


def test_no_warning_when_suministros_override_matches_30pct_of_raw(
    operation: PinnedAuthorityOperation,
) -> None:
    """When the operator-set ratio equals raw * 0.30 (LIRPF Art. 30.2 rule 5),
    no warning fires for suministros categories."""

    raw = Decimal("0.20")

    result = censo_override_warning(
        category=_category("suministros_home_office_luz", operation),
        override_ratio=Decimal("0.060"),
        raw_afectacion_ratio=raw,
        year=2025,
        operation=operation,
    )

    assert result is None


def test_no_warning_when_ownership_override_matches_raw_afectacion(operation: PinnedAuthorityOperation) -> None:
    """When the operator-set ratio equals the raw afectación ratio, no warning
    fires for titularidad categories (no statutory multiplier)."""

    raw = Decimal("0.20")

    result = censo_override_warning(
        category=_category("amortizacion_vivienda_afecto", operation),
        override_ratio=raw,
        raw_afectacion_ratio=raw,
        year=2025,
        operation=operation,
    )

    assert result is None


def test_business_pct_is_none_when_censo_unset(operation: PinnedAuthorityOperation) -> None:
    assert (
        censo_business_pct_for(
            _category("suministros_home_office_luz", operation),
            None,
            year=2025,
            operation=operation,
        )
        is None
    )


def test_business_pct_is_none_for_non_home_office_category(operation: PinnedAuthorityOperation) -> None:
    assert (
        censo_business_pct_for(
            _category("telefonia_movil", operation),
            Decimal("0.20"),
            year=2025,
            operation=operation,
        )
        is None
    )


def test_business_pct_for_suministros_applies_lirpf_30_2_rule_5_factor(
    operation: PinnedAuthorityOperation,
) -> None:
    """Suministros home-office categories deduct at raw * 0.30 (LIRPF Art. 30.2 rule 5)."""

    raw = Decimal("0.20")

    suministros = censo_business_pct_for(
        _category("suministros_home_office_agua", operation),
        raw,
        year=2025,
        operation=operation,
    )

    assert suministros == Decimal("0.060")


def test_business_pct_for_ownership_uses_raw_afectacion(operation: PinnedAuthorityOperation) -> None:
    """Ownership home-office categories deduct at the raw afectación ratio."""

    raw = Decimal("0.20")

    ownership = censo_business_pct_for(
        _category("comunidad_vivienda_afecto", operation),
        raw,
        year=2025,
        operation=operation,
    )

    assert ownership == raw


def test_warning_carries_censo_derived_ratio(operation: PinnedAuthorityOperation) -> None:
    result = censo_override_warning(
        category=_category("ibi_vivienda_afecto", operation),
        override_ratio=Decimal("0.40"),
        raw_afectacion_ratio=Decimal("0.20"),
        year=2025,
        operation=operation,
    )

    assert result is not None
    assert result.censo_derived_ratio == Decimal("0.20")
