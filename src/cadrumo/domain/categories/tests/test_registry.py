"""Unit tests for :data:`~cadrumo.domain.categories._PROFILES_2025`.

Verifies the curated 2025 registry covers every
:class:`~cadrumo.domain.categories.SpendingCategory`, that every profile
carries at least one citation, and that the manual-loader entry point returns
the curated registry surface.

Locks the conservative encodings for known edge categories
(hardware as full-deductible, vehicle fuel without a default ratio,
health insurance as a statutory annual cap) so a future cleanup pass
cannot silently relax them.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from .. import SpendingCategory, load_category_profiles_from_manual, resolve_category_profiles
from .._proportionality import ProportionalityKind
from .._registry import load_category_profiles
from ..errors import CategoryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROFILES_2025 = resolve_category_profiles(2025)


def test_registry_covers_every_spending_category() -> None:
    """Every enum member must have a concrete profile in the 2025 registry."""

    assert set(_PROFILES_2025) == set(SpendingCategory)


def test_every_profile_has_at_least_one_citation() -> None:
    """Explainable category profiles must carry at least one citation."""

    assert all(profile.proportionality.citations for profile in _PROFILES_2025.values())


def test_proportionality_kinds_carry_kind_specific_fields() -> None:
    """Cross-field invariants: each kind populates only its own metadata fields.

    `fixed_percentage` rules carry no `usage_ratio_*` metadata and
    vice versa; the assertions below pin both directions for every
    profile in the registry.
    """
    fixed_percentage_rules = [
        profile.proportionality
        for profile in _PROFILES_2025.values()
        if profile.proportionality.kind is ProportionalityKind.FIXED_PERCENTAGE
    ]
    usage_ratio_rules = [
        profile.proportionality
        for profile in _PROFILES_2025.values()
        if profile.proportionality.kind
        in {ProportionalityKind.USAGE_RATIO_HOME_AREA, ProportionalityKind.USAGE_RATIO_PERSONAL}
    ]

    assert all(rule.fixed_pct is not None and rule.default_ratio is None for rule in fixed_percentage_rules)
    assert usage_ratio_rules, (
        "registry must keep at least one usage-ratio category — operator-defined "
        "proportionality cannot be replaced by fixed-percentage rules alone"
    )
    assert all(rule.fixed_pct is None for rule in usage_ratio_rules)


def test_diet_profiles_preserve_condition_specific_daily_caps() -> None:
    national = _PROFILES_2025[SpendingCategory.MANUTENCION_DIETAS_NACIONAL].proportionality
    foreign = _PROFILES_2025[SpendingCategory.MANUTENCION_DIETAS_EXTRANJERO].proportionality

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
    assert loaded.keys() == _PROFILES_2025.keys()


def test_registry_preserves_conservative_semantics_for_special_categories() -> None:
    """Known edge categories must keep the intended non-numeric rule encoding."""

    hardware = _PROFILES_2025[SpendingCategory.HARDWARE_AMORTIZABLE]
    vehicle = _PROFILES_2025[SpendingCategory.VEHICULO_COMBUSTIBLE]
    health = _PROFILES_2025[SpendingCategory.SEGUROS_SALUD_AUTONOMO]

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


def test_load_category_profiles_from_manual_rejects_unknown_year() -> None:
    """Unsupported handbook years must fail loud."""

    with pytest.raises(ValueError, match=r"2099|year|unsupported|unknown"):
        load_category_profiles_from_manual(2099)


def test_load_category_profiles_wraps_missing_path_as_domain_error(tmp_path: Path) -> None:
    """Registry file access failures stay inside the Cadrumo exception hierarchy."""

    missing = tmp_path / "missing-category-profile.toml"

    with pytest.raises(CategoryValidationError, match=r"cannot stat category profile registry"):
        load_category_profiles(missing)
