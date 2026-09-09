"""Parity and resolution tests for the transitional IVA rate provider."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.providers import FACT_PROVIDER_REGISTRATIONS
from cadrumo.domain.calculations.registry.facts.resolution import ResolvedMappingFact, resolve_governed_fact
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue, GovernedFactVariant
from cadrumo.domain.iva.rates import (
    IVA_RATE_FACT_ID,
    IVA_RATE_PROVIDER_ID,
    compile_iva_rate_facts,
    iva_rate_fact_query,
    iva_rate_record_from_fact,
    load_iva_rate_table,
)
from cadrumo.domain.iva.schema import EUMemberState, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _catalogue() -> GovernedFactCatalogue:
    root = bundled_path("registry", "aeat")
    fact, = compile_iva_rate_facts(root)
    return GovernedFactCatalogue(facts={fact.fact_id: fact})


def test_iva_provider_is_enrolled_with_exact_identity_and_legacy_ownership() -> None:
    registration = next(item for item in FACT_PROVIDER_REGISTRATIONS if item.provider_id == IVA_RATE_PROVIDER_ID)

    assert registration.owned_directories == ("iva",)
    assert IVA_RATE_FACT_ID == "iva-rate-schedule"


def test_iva_provider_projects_every_legacy_row_without_semantic_loss() -> None:
    root = bundled_path("registry", "aeat")
    legacy = {
        (row.member_state, row.kind, row.effective_from, row.pct, row.supersedes_tier_default)
        for rows in load_iva_rate_table().values()
        for row in rows
    }
    fact, = compile_iva_rate_facts(root)
    projected = {
        (
            EUMemberState(str({item.name: item.value for item in variant.selectors}["member_state"])),
            IvaRateKind(str({item.name: item.value for item in variant.selectors}["kind"])),
            variant.valid_from,
            Decimal(str({str(item.key): item.value for item in variant.payload.entries}["pct"])),
            bool({str(item.key): item.value for item in variant.payload.entries}["supersedes_tier_default"]),
        )
        for variant in fact.variants
    }

    assert projected == legacy


def test_iva_query_resolves_exact_date_selectors_and_provenance() -> None:
    resolved = resolve_governed_fact(
        _catalogue(),
        iva_rate_fact_query(EUMemberState.ES, IvaRateKind.GENERAL, date(2025, 6, 1)),
        authority_digest="a" * 64,
    )

    assert isinstance(resolved, ResolvedMappingFact)
    assert iva_rate_record_from_fact(resolved).pct == Decimal("21")
    assert resolved.legal_refs == ("ley-37-1992:art-90",)
    assert resolved.authority_digest == "a" * 64

    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        resolve_governed_fact(
            _catalogue(),
            iva_rate_fact_query(EUMemberState.ES, IvaRateKind.GENERAL, date(2012, 8, 31)),
            authority_digest="a" * 64,
        )


def test_iva_query_keeps_coexisting_rate_separate_from_ordinary_tier() -> None:
    catalogue = _catalogue()
    ordinary = resolve_governed_fact(
        catalogue,
        iva_rate_fact_query(EUMemberState.ES, IvaRateKind.SUPER_REDUCED, date(2024, 11, 1)),
        authority_digest="b" * 64,
    )
    coexisting = resolve_governed_fact(
        catalogue,
        iva_rate_fact_query(
            EUMemberState.ES,
            IvaRateKind.SUPER_REDUCED,
            date(2024, 11, 1),
            superseding_percentage=Decimal("2"),
        ),
        authority_digest="b" * 64,
    )

    assert isinstance(ordinary, ResolvedMappingFact)
    assert isinstance(coexisting, ResolvedMappingFact)
    assert iva_rate_record_from_fact(ordinary).pct == Decimal("4")
    assert iva_rate_record_from_fact(coexisting).pct == Decimal("2")
    assert iva_rate_record_from_fact(coexisting).supersedes_tier_default is True


def test_iva_provider_preserves_complete_legal_or_source_evidence_lanes() -> None:
    fact, = compile_iva_rate_facts(bundled_path("registry", "aeat"))
    spanish = next(
        variant
        for variant in fact.variants
        if {item.name: item.value for item in variant.selectors}["member_state"] == "es"
    )
    foreign = next(
        variant
        for variant in fact.variants
        if {item.name: item.value for item in variant.selectors}["member_state"] == "de"
    )

    assert spanish.legal_refs and not spanish.source_refs and not spanish.source_citations
    assert foreign.source_refs and not foreign.legal_refs
    assert {citation.source_ref for citation in foreign.source_citations} == set(foreign.source_refs)

    with pytest.raises(ValidationError, match="must declare legal or source evidence"):
        GovernedFactVariant.model_validate(
            spanish.model_dump() | {"legal_refs": (), "source_refs": (), "source_citations": ()}
        )
