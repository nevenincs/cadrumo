"""Unit tests for :class:`aeat.domain.usage_ratios.UsageRatioProfile` and the
:func:`aeat.domain.usage_ratios.resolve_user_ratio` helper.

Covers strict bound checks, eligibility enforcement, frozen-attribute
semantics, the non-mutating builder methods, and the canonical key ordering
that keeps the persisted envelope diff-free across re-saves.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

import pytest
from pydantic import ValidationError

from ...categories import ProportionalityKind, SpendingCategory, resolve_category_profiles
from .. import (
    ELIGIBLE_USAGE_RATIO_CATEGORIES,
    UsageRatioProfile,
    UsageRatioReference,
    UsageRatioValidationError,
    resolve_user_ratio,
    validate_usage_ratio_reference,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_empty_profile_round_trips_json() -> None:
    """An empty profile survives JSON round-trip unchanged."""
    profile = UsageRatioProfile()
    reloaded = UsageRatioProfile.model_validate_json(profile.model_dump_json())
    assert reloaded == profile
    assert reloaded.ratios == {}


def test_single_ratio_round_trips() -> None:
    """A profile with one ratio survives JSON round-trip byte-for-byte."""
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    reloaded = UsageRatioProfile.model_validate_json(profile.model_dump_json())
    assert reloaded == profile
    assert reloaded.ratios[SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ] == Decimal("0.21")


def test_negative_ratio_rejected() -> None:
    with pytest.raises(ValidationError, match=r"must be in \[0, 1\]"):
        UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("-0.1")})


def test_above_one_rejected() -> None:
    with pytest.raises(ValidationError, match=r"must be in \[0, 1\]"):
        UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("1.5")})


def test_nan_rejected() -> None:
    # NaN is rejected by pydantic's strict-Decimal finite-number gate
    # BEFORE the [0, 1] bound check runs — a distinct dispatch path.
    with pytest.raises(ValidationError, match=r"finite number"):
        UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("NaN")})


def test_positive_infinity_rejected() -> None:
    with pytest.raises(ValidationError, match=r"finite number"):
        UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("Infinity")})


def test_negative_infinity_rejected() -> None:
    with pytest.raises(ValidationError, match=r"finite number"):
        UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("-Infinity")})


def test_unknown_category_key_rejected_from_json() -> None:
    """JSON payloads naming a non-enum category fail validation."""
    with pytest.raises(ValidationError, match=r"Input should be"):
        UsageRatioProfile.model_validate_json('{"ratios": {"telefonia_turbo": "0.5"}}')


def test_ineligible_category_rejected() -> None:
    """Categories without a USAGE_RATIO_* kind cannot be persisted."""
    with pytest.raises(ValidationError, match=r"material_oficina|ineligible|USAGE_RATIO") as excinfo:
        UsageRatioProfile(ratios={SpendingCategory.MATERIAL_OFICINA: Decimal("0.5")})
    assert "material_oficina" in str(excinfo.value)


def test_frozen_attribute_reassignment_rejected() -> None:
    """``frozen=True`` blocks attribute rebinding on the profile."""
    profile = UsageRatioProfile()
    with pytest.raises(ValidationError, match=r"frozen"):
        profile.ratios = {SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.5")}


def test_ratios_mapping_item_assignment_rejected() -> None:
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    ratios = cast(Any, profile.ratios)
    with pytest.raises(TypeError):
        ratios[SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ] = Decimal("0.50")


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


def test_eligible_categories_are_exactly_the_usage_ratio_rows() -> None:
    """``ELIGIBLE_USAGE_RATIO_CATEGORIES`` must track the registry verbatim.

    The eligibility set is derived from ``resolve_category_profiles(2025)`` at import
    time. This test re-derives it from the registry using the same predicate
    and asserts equality, so a kind-table edit in the registry (adding or
    removing a ``USAGE_RATIO_*`` category) cannot silently drift from what the
    usage-ratio feature accepts. The count pin (twelve) is a secondary
    guardrail that makes accidental additions visible in diffs.
    """
    derived_from_registry = frozenset(
        category
        for category, profile in resolve_category_profiles(2025).items()
        if profile.proportionality.kind
        in {ProportionalityKind.USAGE_RATIO_HOME_AREA, ProportionalityKind.USAGE_RATIO_PERSONAL}
    )
    assert derived_from_registry == ELIGIBLE_USAGE_RATIO_CATEGORIES
    assert len(ELIGIBLE_USAGE_RATIO_CATEGORIES) == 15


def test_consumer_fallback_pattern_documentation() -> None:
    """Reference example of the deductibility-compute consumer pattern.

    This is a documentation test, not a regression guard for shipped code.
    It pins the pattern the deductibility-compute service in
    :mod:`aeat.domain.deductibility` is expected to use: prefer
    :func:`resolve_user_ratio` and fall back to the statutory
    :attr:`aeat.domain.categories.ProportionalityRule.default_ratio` when the
    profile carries no override. When that service ships, its own tests
    become authoritative and this one can be retired.
    """
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})

    def resolve_for_compute(category: SpendingCategory) -> Decimal | None:
        user_value = resolve_user_ratio(profile, category)
        if user_value is not None:
            return user_value
        return resolve_category_profiles(2025)[category].proportionality.default_ratio

    assert resolve_for_compute(SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ) == Decimal("0.21")
    assert resolve_for_compute(SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA) == Decimal("0.30")
    assert resolve_for_compute(SpendingCategory.TELEFONIA_MOVIL) is None


def test_resolve_user_ratio_on_ineligible_category_returns_none() -> None:
    """Compute may look up any category; ineligible ones return ``None``
    gracefully rather than raise — the caller then falls back to the
    statutory default or non-``USAGE_RATIO`` semantics without special-casing.
    """
    profile = UsageRatioProfile()
    assert resolve_user_ratio(profile, SpendingCategory.MATERIAL_OFICINA) is None


def test_saved_profile_has_canonical_key_order() -> None:
    """Two equal profiles serialise to identical bytes regardless of the
    order in which ratios were added — preventing spurious diffs when operator's
    persisted usage-ratio envelope is git-tracked."""
    forward = UsageRatioProfile(
        ratios={
            SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21"),
            SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA: Decimal("0.21"),
            SpendingCategory.TELEFONIA_MOVIL: Decimal("0.6"),
        },
    )
    reverse = UsageRatioProfile(
        ratios={
            SpendingCategory.TELEFONIA_MOVIL: Decimal("0.6"),
            SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA: Decimal("0.21"),
            SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21"),
        },
    )
    assert forward.model_dump_json() == reverse.model_dump_json()
    # And the canonical order is lexicographic by category value:
    keys_in_payload = list(forward.ratios)
    assert keys_in_payload == sorted(keys_in_payload, key=lambda c: c.value)


def test_validate_usage_ratio_reference_accepts_configured_category_key() -> None:
    profile = UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.60")})

    reference = validate_usage_ratio_reference(
        profile,
        category_id=SpendingCategory.TELEFONIA_MOVIL.value,
        usage_ratio_id=SpendingCategory.TELEFONIA_MOVIL.value,
        business_pct=Decimal("0.60"),
    )

    assert isinstance(reference, UsageRatioReference)
    assert reference.category is SpendingCategory.TELEFONIA_MOVIL
    assert reference.ratio == Decimal("0.60")


def test_validate_usage_ratio_reference_rejects_alias_or_unknown_key() -> None:
    profile = UsageRatioProfile()

    with pytest.raises(UsageRatioValidationError, match="concrete eligible spending category"):
        validate_usage_ratio_reference(
            profile,
            category_id=SpendingCategory.TELEFONIA_MOVIL.value,
            usage_ratio_id="home_office_area",
        )


def test_validate_usage_ratio_reference_rejects_category_mismatch() -> None:
    profile = UsageRatioProfile(
        ratios={
            SpendingCategory.TELEFONIA_MOVIL: Decimal("0.60"),
            SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.30"),
        },
    )

    with pytest.raises(UsageRatioValidationError, match="must match"):
        validate_usage_ratio_reference(
            profile,
            category_id=SpendingCategory.TELEFONIA_MOVIL.value,
            usage_ratio_id=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ.value,
        )


def test_validate_usage_ratio_reference_rejects_unconfigured_active_bucket_entry() -> None:
    profile = UsageRatioProfile()

    with pytest.raises(UsageRatioValidationError, match="not configured"):
        validate_usage_ratio_reference(
            profile,
            category_id=SpendingCategory.TELEFONIA_MOVIL.value,
            usage_ratio_id=SpendingCategory.TELEFONIA_MOVIL.value,
        )


def test_validate_usage_ratio_reference_rejects_business_pct_drift() -> None:
    profile = UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.60")})

    with pytest.raises(UsageRatioValidationError, match="does not match"):
        validate_usage_ratio_reference(
            profile,
            category_id=SpendingCategory.TELEFONIA_MOVIL.value,
            usage_ratio_id=SpendingCategory.TELEFONIA_MOVIL.value,
            business_pct=Decimal("0.50"),
        )
