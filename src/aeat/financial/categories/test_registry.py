"""Unit tests for the 2025 category registry."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ...casillas import ModeloCode, load_casillas
from . import CATEGORY_PROFILES_2025, SpendingCategory, load_category_profiles_from_manual


@pytest.mark.unit
def test_registry_covers_every_spending_category() -> None:
    """Every enum member must have a concrete profile in the 2025 registry."""

    assert set(CATEGORY_PROFILES_2025) == set(SpendingCategory)


@pytest.mark.unit
def test_every_profile_has_at_least_one_citation() -> None:
    """Explainable category profiles must carry at least one citation."""

    assert all(profile.proportionality.citations for profile in CATEGORY_PROFILES_2025.values())


@pytest.mark.unit
def test_every_mapping_points_to_real_public_casillas() -> None:
    """Every referenced casilla code must exist in the committed public corpus."""

    valid_codes = {
        ModeloCode.MODELO_130: {record.casilla_id for record in load_casillas("MODELO_130", "2025Q4").records},
        ModeloCode.MODELO_303: {record.casilla_id for record in load_casillas("MODELO_303", "2025Q4").records},
    }
    for profile in CATEGORY_PROFILES_2025.values():
        for mapping in profile.casilla_mappings:
            assert mapping.casilla_code in valid_codes[mapping.modelo]


@pytest.mark.unit
def test_load_category_profiles_from_manual_returns_2025_registry() -> None:
    """The manual loader must resolve to the curated 2025 registry surface."""

    loaded = load_category_profiles_from_manual(2025)
    assert loaded.keys() == CATEGORY_PROFILES_2025.keys()


@pytest.mark.unit
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


@pytest.mark.unit
def test_load_category_profiles_from_manual_rejects_unknown_year() -> None:
    """Unsupported handbook years must fail loud."""

    with pytest.raises(ValueError):
        load_category_profiles_from_manual(2024)
