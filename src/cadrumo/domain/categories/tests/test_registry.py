"""Unit tests for :func:`~cadrumo.domain.categories.registry.resolve_category_profiles`.

Verifies the curated 2025 registry covers every
:class:`~cadrumo.domain.categories.SpendingCategory`, that every profile
carries at least one citation, and that the registry-backed entry point returns
the curated registry surface.

Locks the conservative encodings for known edge categories
(hardware as full-deductible, vehicle fuel without a default ratio,
health insurance as a statutory annual cap) so a future cleanup pass
cannot silently relax them.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.errors import RegistryValidationError
from ..profile import CategoryProfile
from ..proportionality_catalogue import require_proportionality_kind
from ..registry import resolve_category_profiles
from ..spending_category import SpendingCategory
from ..spending_category_catalogue import spending_category_tokens

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture
def profiles_2025(operation: PinnedAuthorityOperation) -> Mapping[SpendingCategory, CategoryProfile]:
    """Resolve the 2025 projection through the test operation lease."""
    return resolve_category_profiles(2025, operation=operation)


def test_registry_covers_every_spending_category(
    profiles_2025: Mapping[SpendingCategory, CategoryProfile],
    operation: PinnedAuthorityOperation,
) -> None:
    """Every authority-declared category must have a concrete 2025 profile."""

    expected_categories = spending_category_tokens(effective_date=date(2025, 12, 31), authority=operation)
    assert set(profiles_2025) == set(expected_categories)


def test_every_profile_has_at_least_one_citation(
    profiles_2025: Mapping[SpendingCategory, CategoryProfile],
) -> None:
    """Explainable category profiles must carry at least one citation."""

    assert all(profile.proportionality.citations for profile in profiles_2025.values())


def test_proportionality_kinds_carry_kind_specific_fields(
    profiles_2025: Mapping[SpendingCategory, CategoryProfile],
) -> None:
    """Cross-field invariants: each kind populates only its own metadata fields.

    `fixed_percentage` rules carry no `usage_ratio_*` metadata and
    vice versa; the assertions below pin both directions for every
    profile in the registry.
    """
    fixed_percentage_rules = [
        profile.proportionality
        for profile in profiles_2025.values()
        if profile.proportionality.kind == require_proportionality_kind("fixed_percentage")
    ]
    usage_ratio_rules = [
        profile.proportionality
        for profile in profiles_2025.values()
        if profile.proportionality.kind
        in {
            require_proportionality_kind("usage_ratio_home_area"),
            require_proportionality_kind("usage_ratio_personal"),
        }
    ]

    assert all(rule.fixed_pct is not None and rule.default_ratio is None for rule in fixed_percentage_rules)
    assert usage_ratio_rules, (
        "registry must keep at least one usage-ratio category — operator-defined "
        "proportionality cannot be replaced by fixed-percentage rules alone"
    )
    assert all(rule.fixed_pct is None for rule in usage_ratio_rules)


def test_diet_profiles_preserve_condition_specific_daily_caps(
    profiles_2025: Mapping[SpendingCategory, CategoryProfile],
) -> None:
    national = profiles_2025[SpendingCategory.from_registry("manutencion_dietas_nacional")].proportionality
    foreign = profiles_2025[SpendingCategory.from_registry("manutencion_dietas_extranjero")].proportionality

    assert {variant.id: variant.statutory_cap_eur_per_day for variant in national.statutory_cap_variants} == {
        "sin-pernocta": Decimal("26.67"),
        "con-pernocta": Decimal("53.34"),
    }
    assert {variant.id: variant.statutory_cap_eur_per_day for variant in foreign.statutory_cap_variants} == {
        "sin-pernocta": Decimal("48.08"),
        "con-pernocta": Decimal("91.35"),
    }


def test_registry_preserves_conservative_semantics_for_special_categories(
    profiles_2025: Mapping[SpendingCategory, CategoryProfile],
) -> None:
    """Known edge categories must keep the intended non-numeric rule encoding."""

    hardware = profiles_2025[SpendingCategory.from_registry("hardware_amortizable")]
    vehicle = profiles_2025[SpendingCategory.from_registry("vehiculo_combustible")]
    health = profiles_2025[SpendingCategory.from_registry("seguros_salud_autonomo")]

    assert hardware.proportionality.kind.value == "full_deductible"
    assert vehicle.proportionality.default_ratio is None
    assert health.proportionality.kind.value == "statutory_cap"
    assert health.proportionality.statutory_cap_eur_per_day is None
    # LIRPF art. 30.2.5.a states TWO limits -- 500 per person, 1.500 for a person with
    # discapacidad -- so the rule carries both as variants rather than one flat amount.
    # A lone statutory_cap_eur here is the shape that lost the higher limb.
    assert health.proportionality.statutory_cap_eur is None
    assert {v.id: v.statutory_cap_eur for v in health.proportionality.statutory_cap_variants} == {
        "general": Decimal("500"),
        "discapacidad": Decimal("1500"),
    }
    assert health.proportionality.statutory_cap_period is not None
    assert health.proportionality.statutory_cap_period.value == "year_per_person"


def test_resolve_category_profiles_rejects_a_year_below_the_supported_floor(
    operation: PinnedAuthorityOperation,
) -> None:
    """A year below the supported floor must fail loud."""
    below_floor = operation.supported_filing_years().floor - 1

    with pytest.raises(RegistryValidationError, match="outside the supported filing years"):
        resolve_category_profiles(below_floor, operation=operation)


def test_resolve_category_profiles_carries_the_horizon_forward(operation: PinnedAuthorityOperation) -> None:
    """With no hard ceiling, a year above the horizon resolves the newest authored profiles."""
    support = operation.supported_filing_years()
    assert support.hard_ceiling is None, "a declared ceiling changes what this test may assert"

    carried = resolve_category_profiles(support.horizon + 1, operation=operation)

    assert carried == resolve_category_profiles(support.horizon, operation=operation)
