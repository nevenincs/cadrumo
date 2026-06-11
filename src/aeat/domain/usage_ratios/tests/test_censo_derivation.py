"""Real-behavior tests for censo-derived home-office usage ratios.

Locks the contract that
:func:`aeat.domain.usage_ratios.derive_home_office_ratios_from_censo`
turns the operator's vivienda afectación ratio into a
:class:`UsageRatioProfile` carrying one entry per HOME_OFFICE_SUMINISTROS
and HOME_OFFICE_OWNERSHIP category, with each entry equal to the raw
ratio multiplied by the registry rule's ``statutory_multiplier`` (per
LIRPF Art. 30.2 rule 5, Ley 6/2017, BOE-A-2017-12544).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ...categories import (
    SpendingCategory,
    SpendingCategoryFamily,
    categories_for_family,
)
from .._errors import UsageRatioValidationError
from .._service import derive_home_office_ratios_from_censo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# Hard-coded BOE constants — DO NOT derive from the registry.
# LIRPF Art. 30.2 rule 5 (Ley 6/2017, BOE-A-2017-12544): suministros of
# the habitual vivienda parcialmente afecta deduct at 30% of the raw
# afectación ratio. Titularidad costs (amortización / IBI / comunidad)
# deduct at the raw ratio — no statutory multiplier applies. Asserting
# against these literals (rather than re-reading registry.statutory_multiplier)
# is the only way the test catches a registry mis-edit.
_SUMINISTROS_STATUTORY_FACTOR = Decimal("0.30")
_OWNERSHIP_STATUTORY_FACTOR = Decimal("1")


def test_derivation_covers_every_home_office_category() -> None:
    profile = derive_home_office_ratios_from_censo(Decimal("0.20"), year=2025)

    expected = set(categories_for_family(SpendingCategoryFamily.HOME_OFFICE_SUMINISTROS)) | set(
        categories_for_family(SpendingCategoryFamily.HOME_OFFICE_OWNERSHIP),
    )
    assert set(profile.ratios) == expected


def test_suministros_apply_lirpf_art_30_2_rule_5_30pct_multiplier() -> None:
    """Each suministros category yields raw * 0.30 (LIRPF Art. 30.2 rule 5)."""

    raw = Decimal("0.25")
    profile = derive_home_office_ratios_from_censo(raw, year=2025)

    expected = raw * _SUMINISTROS_STATUTORY_FACTOR
    for category in categories_for_family(SpendingCategoryFamily.HOME_OFFICE_SUMINISTROS):
        assert profile.ratios[category] == expected, (
            f"suministros {category.value} must apply the 30% LIRPF Art. 30.2 rule 5 multiplier"
        )


def test_ownership_categories_apply_raw_afectacion_with_no_multiplier() -> None:
    """Titularidad costs deduct at the raw ratio (no statutory factor)."""

    raw = Decimal("0.25")
    profile = derive_home_office_ratios_from_censo(raw, year=2025)

    expected = raw * _OWNERSHIP_STATUTORY_FACTOR
    for category in categories_for_family(SpendingCategoryFamily.HOME_OFFICE_OWNERSHIP):
        assert profile.ratios[category] == expected, (
            f"ownership {category.value} must deduct at the raw afectación ratio, without any statutory multiplier"
        )


def test_suministros_luz_concrete_value_at_20_percent_afectacion() -> None:
    """Anti-tautology pin: 20% afectación, suministros_luz must be exactly 0.06."""

    profile = derive_home_office_ratios_from_censo(Decimal("0.20"), year=2025)

    assert profile.ratios[SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ] == Decimal("0.060")


def test_zero_ratio_is_accepted() -> None:
    profile = derive_home_office_ratios_from_censo(Decimal("0"), year=2025)

    assert all(value == Decimal("0") for value in profile.ratios.values())


def test_ratio_above_one_is_rejected() -> None:
    with pytest.raises(UsageRatioValidationError):
        derive_home_office_ratios_from_censo(Decimal("1.01"), year=2025)


def test_negative_ratio_is_rejected() -> None:
    with pytest.raises(UsageRatioValidationError):
        derive_home_office_ratios_from_censo(Decimal("-0.01"), year=2025)
