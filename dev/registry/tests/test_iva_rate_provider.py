"""Parity and resolution tests for the transitional IVA rate provider."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedMappingFact,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import (
    FactSelector,
    GovernedFact,
    GovernedFactCatalogue,
    GovernedFactVariant,
    MappingFactPayload,
)
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.iva.rates import (
    IVA_RATE_FACT_ID,
    IVA_RATE_PROVIDER_ID,
    iva_rate_record_from_fact,
)
from cadrumo.domain.iva.schema import EUMemberState, IvaRateKind
from dev.registry.compiler.fact_loader import load_governed_facts
from dev.registry.compiler.fact_providers import FACT_PROVIDER_REGISTRATIONS
from dev.registry.compiler.iva import load_iva_rate_table_for_publication

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def iva_rate_fact_query(
    member_state: EUMemberState, kind: IvaRateKind, on_date: date, *, superseding_percentage: Decimal | None = None
) -> MappingFactQuery:
    role = "ordinary" if superseding_percentage is None else f"coexisting-{superseding_percentage}"
    return MappingFactQuery(
        fact_id=IVA_RATE_FACT_ID,
        date_axis=DateAxis.DEVENGO_DATE,
        effective_date=on_date,
        selectors=(
            FactSelector(name="member_state", value=member_state.value),
            FactSelector(name="kind", value=kind.value),
            FactSelector(name="rate_role", value=role),
        ),
    )


def _catalogue() -> GovernedFactCatalogue:
    fact = _authored_fact()
    return GovernedFactCatalogue(facts={fact.fact_id: fact})


def _authored_fact() -> GovernedFact:
    return next(
        fact
        for fact in load_governed_facts(bundled_path("registry", "aeat", "facts"))
        if fact.fact_id == IVA_RATE_FACT_ID
    )


def test_iva_rate_fact_is_directly_authored_without_legacy_provider_registration() -> None:
    facts = {fact.fact_id: fact for fact in load_governed_facts(bundled_path("registry", "aeat", "facts"))}

    assert IVA_RATE_FACT_ID == "iva-rate-schedule"
    assert facts[IVA_RATE_FACT_ID].family.value == "mapping"
    assert not any(item.provider_id == IVA_RATE_PROVIDER_ID for item in FACT_PROVIDER_REGISTRATIONS)


def test_iva_provider_projects_every_legacy_row_without_semantic_loss() -> None:
    root = bundled_path("registry", "aeat")
    legacy = {
        (row.member_state, row.kind, row.effective_from, row.pct, row.supersedes_tier_default)
        for rows in load_iva_rate_table_for_publication(root).values()
        for row in rows
    }
    fact = _authored_fact()
    projected: set[tuple[EUMemberState, IvaRateKind, date, Decimal, bool]] = set()
    for variant in fact.variants:
        assert isinstance(variant.payload, MappingFactPayload)
        projected.add(
            (
                EUMemberState(str({item.name: item.value for item in variant.selectors}["member_state"])),
                IvaRateKind(str({item.name: item.value for item in variant.selectors}["kind"])),
                variant.valid_from,
                Decimal(str({str(item.key): item.value for item in variant.payload.entries}["pct"])),
                bool({str(item.key): item.value for item in variant.payload.entries}["supersedes_tier_default"]),
            )
        )

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
    fact = _authored_fact()
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
            {
                "variant_id": spanish.variant_id,
                "selectors": spanish.selectors,
                "date_axis": spanish.date_axis,
                "valid_from": spanish.valid_from,
                "valid_to": spanish.valid_to,
                "payload": spanish.payload,
                "legal_refs": (),
                "source_refs": (),
                "source_citations": (),
                "review_status": spanish.review_status,
                "ownership": spanish.ownership,
                "precedence_over": spanish.precedence_over,
            }
        )
