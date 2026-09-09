"""Focused parity tests for the governed category-profile provider."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.resources.bundled_data import bundled_path
from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.facts.resolution import resolve_governed_fact
from ...calculations.registry.facts.schema import GovernedFactCatalogue
from ...calculations.registry.schema_base import DateAxis
from ..registry import (
    CATEGORY_PROFILE_FACT_ID,
    CATEGORY_STATUTORY_CAP_FACT_ID,
    category_profile_fact_query,
    category_statutory_cap_fact_query,
    compile_category_profile_facts,
    resolve_category_profiles,
)
from ..spending_category import SpendingCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _catalogue() -> GovernedFactCatalogue:
    facts = compile_category_profile_facts(bundled_path("registry", "aeat"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})


def test_provider_registers_exact_profile_and_dated_cap_identities() -> None:
    catalogue = _catalogue()

    assert set(catalogue.facts) == {CATEGORY_PROFILE_FACT_ID, CATEGORY_STATUTORY_CAP_FACT_ID}
    assert all(
        variant.date_axis is DateAxis.FILING_PERIOD
        for fact in catalogue.facts.values()
        for variant in fact.variants
    )


def test_profile_query_preserves_legacy_profile_values_and_provenance() -> None:
    category = SpendingCategory.SEGUROS_SALUD_AUTONOMO
    legacy = resolve_category_profiles(2025)[category]
    resolved = resolve_governed_fact(
        _catalogue(),
        category_profile_fact_query(category, 2025),
        authority_digest="a" * 64,
    )
    entries = {entry.key: entry.value for entry in resolved.payload.entries}

    assert entries["proportionality_kind"] == legacy.proportionality.kind.value
    assert entries["statutory_cap_variant.general.eur"] == Decimal("500")
    assert entries["statutory_cap_variant.discapacidad.eur"] == Decimal("1500")
    assert resolved.matched_selectors[0].value == category.value
    assert resolved.legal_refs
    assert resolved.source_refs
    assert resolved.source_citations


def test_dated_cap_query_matches_legacy_exact_year_without_fallback() -> None:
    category = SpendingCategory.MUTUALIDAD_ALTERNATIVA
    legacy = resolve_category_profiles(2025)[category]
    resolved = resolve_governed_fact(
        _catalogue(),
        category_statutory_cap_fact_query(category, date(2025, 6, 30)),
        authority_digest="b" * 64,
    )

    assert resolved.payload.value == legacy.proportionality.statutory_cap_eur
    assert resolved.payload.unit == "eur"
    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        resolve_governed_fact(
            _catalogue(),
            category_statutory_cap_fact_query(category, date(2099, 1, 1)),
            authority_digest="b" * 64,
        )
