"""Unit tests for :class:`UsageRatioProfile` and the resolver (#259)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..categories import CATEGORY_PROFILES_2025, SpendingCategory
from . import (
    ELIGIBLE_USAGE_RATIO_CATEGORIES,
    UsageRatioProfile,
    resolve_user_ratio,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


_EXPECTED_ELIGIBLE: frozenset[SpendingCategory] = frozenset(
    {
        SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_GAS,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET,
        SpendingCategory.TELEFONIA_FIJA,
        SpendingCategory.TELEFONIA_MOVIL,
        SpendingCategory.VEHICULO_COMBUSTIBLE,
        SpendingCategory.VEHICULO_MANTENIMIENTO,
        SpendingCategory.VEHICULO_SEGURO,
        SpendingCategory.VEHICULO_PEAJE,
        SpendingCategory.VEHICULO_PARKING,
    }
)


def test_empty_profile_round_trips_json() -> None:
    """An empty profile serialises to ``{"ratios": {}}`` and reloads equal."""
    profile = UsageRatioProfile()
    payload = profile.model_dump_json()
    reloaded = UsageRatioProfile.model_validate_json(payload)
    assert payload == '{"ratios":{}}'
    assert reloaded == profile


def test_single_ratio_round_trips() -> None:
    """A profile with one ratio survives JSON round-trip byte-for-byte."""
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    reloaded = UsageRatioProfile.model_validate_json(profile.model_dump_json())
    assert reloaded == profile
    assert reloaded.ratios[SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ] == Decimal("0.21")


def test_negative_ratio_rejected() -> None:
    with pytest.raises(ValidationError):
        UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("-0.1")})


def test_above_one_rejected() -> None:
    with pytest.raises(ValidationError):
        UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("1.5")})


def test_nan_rejected() -> None:
    with pytest.raises(ValidationError):
        UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("NaN")})


def test_positive_infinity_rejected() -> None:
    with pytest.raises(ValidationError):
        UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("Infinity")})


def test_negative_infinity_rejected() -> None:
    with pytest.raises(ValidationError):
        UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("-Infinity")})


def test_unknown_category_key_rejected_from_json() -> None:
    """JSON payloads naming a non-enum category fail validation."""
    with pytest.raises(ValidationError):
        UsageRatioProfile.model_validate_json('{"ratios": {"telefonia_turbo": "0.5"}}')


def test_ineligible_category_rejected() -> None:
    """Categories without a USAGE_RATIO_* kind cannot be persisted."""
    with pytest.raises(ValidationError) as excinfo:
        UsageRatioProfile(ratios={SpendingCategory.MATERIAL_OFICINA: Decimal("0.5")})
    assert "material_oficina" in str(excinfo.value)


def test_frozen_attribute_reassignment_rejected() -> None:
    """``frozen=True`` blocks attribute rebinding on the profile."""
    profile = UsageRatioProfile()
    with pytest.raises(ValidationError):
        profile.ratios = {SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.5")}  # type: ignore[misc]


def test_with_ratio_returns_new_profile() -> None:
    """``with_ratio`` is non-mutating."""
    original = UsageRatioProfile()
    updated = original.with_ratio(SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ, Decimal("0.21"))
    assert original.ratios == {}
    assert updated.ratios == {SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")}
    assert updated is not original


def test_without_ratio_is_noop_on_unset() -> None:
    """Removing an unset category is a no-op."""
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    result = profile.without_ratio(SpendingCategory.TELEFONIA_MOVIL)
    assert result == profile


def test_resolve_user_ratio_returns_set_or_none() -> None:
    """``resolve_user_ratio`` returns a ``Decimal`` for set keys, ``None`` otherwise."""
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    assert resolve_user_ratio(profile, SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ) == Decimal("0.21")
    assert resolve_user_ratio(profile, SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA) is None


def test_eligible_categories_match_twelve_expected() -> None:
    """The eligibility set is exactly the twelve USAGE_RATIO_* rows."""
    assert ELIGIBLE_USAGE_RATIO_CATEGORIES == _EXPECTED_ELIGIBLE
    assert len(ELIGIBLE_USAGE_RATIO_CATEGORIES) == 12


def test_consumer_fallback_contract() -> None:
    """Document the intended #257 fallback: user ratio → statutory default."""
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})

    def resolve_for_compute(category: SpendingCategory) -> Decimal | None:
        user_value = resolve_user_ratio(profile, category)
        if user_value is not None:
            return user_value
        return CATEGORY_PROFILES_2025[category].proportionality.default_ratio

    assert resolve_for_compute(SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ) == Decimal("0.21")
    assert resolve_for_compute(SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA) == Decimal("0.30")
    assert resolve_for_compute(SpendingCategory.TELEFONIA_MOVIL) is None
