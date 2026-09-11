"""Direct-fact coverage and retirement census for spending-category profiles."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from shutil import copy2

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import (
    MappingFactQuery,
    ScalarFactQuery,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import FactOwnership, FactSelector, GovernedFactCatalogue
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.categories.registry import CATEGORY_PROFILE_FACT_ID, CATEGORY_STATUTORY_CAP_FACT_ID
from cadrumo.domain.categories.spending_category import SpendingCategory
from dev.registry.compiler.fact_loader import load_governed_facts
from dev.registry.compiler.fact_providers import FACT_PROVIDER_REGISTRATIONS
from dev.registry.compiler.loader import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _category_facts() -> GovernedFactCatalogue:
    facts = load_governed_facts(bundled_path("registry", "aeat", "facts"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})


def _master_supported_filing_years() -> frozenset[int]:
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    declaration = catalogues.supported_filing_years
    assert declaration is not None, "the registry declares no supported filing years"
    return frozenset(declaration.years)


def _assert_category_profile_exact_coverage(facts_dir: Path, years: frozenset[int]) -> None:
    facts = {fact.fact_id: fact for fact in load_governed_facts(facts_dir)}
    profile_fact = facts[CATEGORY_PROFILE_FACT_ID]
    failures: list[str] = []
    for category in SpendingCategory:
        for year in years:
            matching = [
                variant
                for variant in profile_fact.variants
                if any(
                    selector.name == "category" and selector.value == category.value for selector in variant.selectors
                )
                and variant.valid_from <= date(year, 12, 31) <= (variant.valid_to or date.max)
            ]
            if len(matching) != 1:
                failures.append(f"{category.value}/{year} ({len(matching)} variants)")
    assert not failures, "missing exact category profile variants: " + ", ".join(failures)


def test_authored_category_profile_fact_covers_every_category_with_evidence() -> None:
    catalogue = _category_facts()
    profile_fact = catalogue.facts[CATEGORY_PROFILE_FACT_ID]

    assert profile_fact.variants
    declared_categories = {
        selector.value
        for variant in profile_fact.variants
        for selector in variant.selectors
        if selector.name == "category"
    }
    assert declared_categories == {category.value for category in SpendingCategory}
    assert all(variant.ownership is FactOwnership.AUTHORED for variant in profile_fact.variants)
    assert all(variant.source_citations for variant in profile_fact.variants)

    for category in SpendingCategory:
        resolved = resolve_governed_fact(
            catalogue,
            MappingFactQuery(
                fact_id=CATEGORY_PROFILE_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=date(2025, 12, 31),
                selectors=(FactSelector(name="category", value=category.value),),
            ),
            authority_digest="a" * 64,
        )
        assert resolved.payload.entries

    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        resolve_governed_fact(
            catalogue,
            MappingFactQuery(
                fact_id=CATEGORY_PROFILE_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=date(2099, 12, 31),
                selectors=(FactSelector(name="category", value=SpendingCategory.MUTUALIDAD_ALTERNATIVA.value),),
            ),
            authority_digest="a" * 64,
        )


def test_authored_category_profile_fact_covers_every_master_supported_year() -> None:
    years = _master_supported_filing_years()

    assert years, "the master supported filing-year declaration is empty"
    _assert_category_profile_exact_coverage(bundled_path("registry", "aeat", "facts"), years)


def test_category_profile_coverage_gate_bites_when_one_historical_variant_is_removed(tmp_path: Path) -> None:
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    source = bundled_path("registry", "aeat", "facts", "0064-categories-profile.toml")
    candidate = facts_dir / source.name
    copy2(source, candidate)

    marker = '[[fact.variants]]\nvariant_id = "categories.profile:mutualidad_alternativa:2024"\n'
    content = candidate.read_text(encoding="utf-8")
    start = content.index(marker)
    end = content.index("[[fact.variants]]", start + len(marker))
    candidate.write_text(content[:start] + content[end:], encoding="utf-8")

    with pytest.raises(AssertionError, match=r"missing exact category profile variants: .*mutualidad_alternativa/2024"):
        _assert_category_profile_exact_coverage(facts_dir, _master_supported_filing_years())


def test_authored_category_profile_fact_preserves_citation_identity_window_and_grounding() -> None:
    resolved = resolve_governed_fact(
        _category_facts(),
        MappingFactQuery(
            fact_id=CATEGORY_PROFILE_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(2025, 12, 31),
            selectors=(FactSelector(name="category", value=SpendingCategory.MUTUALIDAD_ALTERNATIVA.value),),
        ),
        authority_digest="a" * 64,
    )
    values = {entry.key: entry.value for entry in resolved.payload.entries}

    assert values["citation.0.source"] == "aeat_help"
    assert values["citation.0.grounding"] == "source_not_bundled"
    assert values["citation.0.valid_from"] == date(2025, 1, 1)
    assert values["citation.0.valid_to"] == date(2025, 12, 31)
    assert values["citation.2.legal_ref"] == "ley-35-2006:art-30"
    assert values["citation.2.quote"]


def test_authored_category_cap_fact_preserves_the_dated_mutualidad_amount() -> None:
    resolved = resolve_governed_fact(
        _category_facts(),
        ScalarFactQuery(
            fact_id=CATEGORY_STATUTORY_CAP_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(2025, 12, 31),
            selectors=(FactSelector(name="category", value=SpendingCategory.MUTUALIDAD_ALTERNATIVA.value),),
        ),
        authority_digest="b" * 64,
    )

    assert resolved.payload.value == Decimal("16672.66")
    assert resolved.ownership is FactOwnership.AUTHORED
    assert resolved.source_citations


def test_category_adapter_and_raw_profile_corpus_are_absent() -> None:
    root = Path(__file__).resolve().parents[3]
    assert not (root / "dev" / "registry" / "compiler" / "categories.py").exists()
    assert not (root / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "categories" / "profiles.toml").exists()
    assert all(registration.provider_id != "category-profiles" for registration in FACT_PROVIDER_REGISTRATIONS)
