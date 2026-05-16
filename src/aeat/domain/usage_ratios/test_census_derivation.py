"""Real-behavior tests for census-derived home-office usage ratios.

Locks the contract that
:func:`aeat.domain.usage_ratios.derive_home_office_ratios_from_census`
turns the operator's vivienda afectación ratio into a
:class:`UsageRatioProfile` carrying one entry per HOME_OFFICE_SUMINISTROS
and HOME_OFFICE_OWNERSHIP category, with each entry equal to the raw
ratio multiplied by the registry rule's ``statutory_multiplier`` (per
LIRPF Art. 30.2 rule 5, Ley 6/2017, BOE-A-2017-12544).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..categories import (
    SpendingCategoryFamily,
    categories_for_family,
    resolve_category_profiles,
)
from ._errors import UsageRatioValidationError
from ._service import derive_home_office_ratios_from_census


pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_derivation_covers_every_home_office_category() -> None:
    profile = derive_home_office_ratios_from_census(Decimal("0.20"), year=2025)

    expected = set(categories_for_family(SpendingCategoryFamily.HOME_OFFICE_SUMINISTROS)) | set(
        categories_for_family(SpendingCategoryFamily.HOME_OFFICE_OWNERSHIP)
    )
    assert set(profile.ratios) == expected


def test_each_ratio_equals_raw_times_statutory_multiplier() -> None:
    raw = Decimal("0.25")
    profile = derive_home_office_ratios_from_census(raw, year=2025)
    registry = resolve_category_profiles(2025)

    for category, derived in profile.ratios.items():
        rule = registry[category].proportionality
        multiplier = rule.statutory_multiplier if rule.statutory_multiplier is not None else Decimal("1")
        assert derived == raw * multiplier


def test_zero_ratio_is_accepted() -> None:
    profile = derive_home_office_ratios_from_census(Decimal("0"), year=2025)

    assert all(value == Decimal("0") for value in profile.ratios.values())


def test_ratio_above_one_is_rejected() -> None:
    with pytest.raises(UsageRatioValidationError):
        derive_home_office_ratios_from_census(Decimal("1.01"), year=2025)


def test_negative_ratio_is_rejected() -> None:
    with pytest.raises(UsageRatioValidationError):
        derive_home_office_ratios_from_census(Decimal("-0.01"), year=2025)
