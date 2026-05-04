"""Unit tests for :data:`~aeat.domain.categories.CATEGORY_PROFILES_2025`.

Verifies the curated 2025 registry covers every
:class:`~aeat.domain.categories.SpendingCategory`, that every profile
carries at least one citation, and that the manual-loader entry point returns
the curated registry surface.

Locks the conservative encodings for known edge categories
(hardware as full-deductible, vehicle fuel without a default ratio,
health insurance as a statutory annual cap) so a future cleanup pass
cannot silently relax them.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from . import CATEGORY_PROFILES_2025, SpendingCategory, load_category_profiles_from_manual
from ._proportionality import ProportionalityKind

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_registry_covers_every_spending_category() -> None:
    """Every enum member must have a concrete profile in the 2025 registry."""

    assert set(CATEGORY_PROFILES_2025) == set(SpendingCategory)


def test_every_profile_has_at_least_one_citation() -> None:
    """Explainable category profiles must carry at least one citation."""

    assert all(profile.proportionality.citations for profile in CATEGORY_PROFILES_2025.values())


def test_fixed_percentage_profiles_use_fixed_percentage_field() -> None:
    fixed_percentage_rules = [
        profile.proportionality
        for profile in CATEGORY_PROFILES_2025.values()
        if profile.proportionality.kind is ProportionalityKind.FIXED_PERCENTAGE
    ]

    assert fixed_percentage_rules
    assert all(rule.fixed_pct == Decimal("0.30") for rule in fixed_percentage_rules)
    assert all(rule.default_ratio is None for rule in fixed_percentage_rules)


def test_diet_profiles_preserve_condition_specific_daily_caps() -> None:
    national = CATEGORY_PROFILES_2025[SpendingCategory.MANUTENCION_DIETAS_NACIONAL].proportionality
    foreign = CATEGORY_PROFILES_2025[SpendingCategory.MANUTENCION_DIETAS_EXTRANJERO].proportionality

    assert {variant.id: variant.statutory_cap_eur_per_day for variant in national.statutory_cap_variants} == {
        "sin-pernocta": Decimal("26.67"),
        "con-pernocta": Decimal("53.34"),
    }
    assert {variant.id: variant.statutory_cap_eur_per_day for variant in foreign.statutory_cap_variants} == {
        "sin-pernocta": Decimal("48.08"),
        "con-pernocta": Decimal("91.35"),
    }


def test_load_category_profiles_from_manual_returns_2025_registry() -> None:
    """The manual loader must resolve to the curated 2025 registry surface."""

    loaded = load_category_profiles_from_manual(2025)
    assert loaded.keys() == CATEGORY_PROFILES_2025.keys()


def test_registry_preserves_conservative_semantics_for_special_categories() -> None:
    """Known edge categories must keep the intended non-numeric rule encoding."""

    hardware = CATEGORY_PROFILES_2025[SpendingCategory.HARDWARE_AMORTIZABLE]
    vehicle = CATEGORY_PROFILES_2025[SpendingCategory.VEHICULO_COMBUSTIBLE]
    health = CATEGORY_PROFILES_2025[SpendingCategory.SEGUROS_SALUD_AUTONOMO]

    assert hardware.proportionality.kind.value == "full_deductible"
    assert vehicle.proportionality.default_ratio is None
    assert health.proportionality.kind.value == "statutory_cap"
    assert health.proportionality.statutory_cap_eur_per_day is None
    assert health.proportionality.statutory_cap_eur == Decimal("500")
    assert health.proportionality.statutory_cap_period is not None
    assert health.proportionality.statutory_cap_period.value == "year_per_person"


def test_load_category_profiles_from_manual_rejects_unknown_year() -> None:
    """Unsupported handbook years must fail loud."""

    with pytest.raises(ValueError):
        load_category_profiles_from_manual(2024)
