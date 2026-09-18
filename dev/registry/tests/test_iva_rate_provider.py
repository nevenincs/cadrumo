"""Parity and resolution tests for the transitional IVA rate provider."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

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
    rate_record_from_fact,
)
from cadrumo.domain.iva.schema import EUMemberState, IvaRateKind, require_eu_member_state

from ..compiler.authority import compiled_bundled_authority
from ..compiler.fact_loader import load_governed_facts
from ..compiler.fact_providers import FACT_PROVIDER_REGISTRATIONS
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]


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
    assert not any(item.provider_id == IVA_RATE_FACT_ID for item in FACT_PROVIDER_REGISTRATIONS)


def test_iva_rate_schedule_is_a_complete_authored_fact() -> None:
    fact = _authored_fact()
    projected: set[tuple[EUMemberState, IvaRateKind, date, Decimal, bool]] = set()
    for variant in fact.variants:
        assert isinstance(variant.payload, MappingFactPayload)
        assert variant.valid_from is not None
        selectors = {item.name: item.value for item in variant.selectors}
        if "member_state" not in selectors:
            # The schedule also carries a vocabulary variant -- the rate-role
            # catalogue, selected by ``scope`` -- which declares no member state
            # and is not a rate row.
            continue
        projected.add(
            (
                # Projected, never constructed: an EU member-state token comes
                # from the facts registry, and the type refuses a bare string so
                # a schedule cannot name a state the registry does not carry.
                require_eu_member_state(str(selectors["member_state"])),
                IvaRateKind(str(selectors["kind"])),
                variant.valid_from,
                Decimal(str({str(item.key): item.value for item in variant.payload.entries}["pct"])),
                bool({str(item.key): item.value for item in variant.payload.entries}["supersedes_tier_default"]),
            )
        )

    assert projected
    assert (
        require_eu_member_state("ES"),
        IvaRateKind("general"),
        date(2012, 9, 1),
        Decimal("21"),
        False,
    ) in projected
    assert (
        require_eu_member_state("ES"),
        IvaRateKind("reduced"),
        date(2024, 7, 1),
        Decimal("5"),
        True,
    ) in projected
    assert (
        require_eu_member_state("DE"),
        IvaRateKind("general"),
        date(2025, 7, 1),
        Decimal("19"),
        False,
    ) in projected


def test_retired_iva_schedule_lane_cannot_reappear() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    retired_paths = (
        repository_root / "dev/registry/compiler/iva.py",
        repository_root / "src/cadrumo/_data/registry/aeat/iva/rates.toml",
        repository_root / "src/cadrumo/_data/registry/aeat/iva/recargo-rates.toml",
    )

    assert not any(path.exists() for path in retired_paths)
    forbidden = (
        "dev.registry.compiler.iva",
        "registry/aeat/iva/rates.toml",
        "registry/aeat/iva/recargo-rates.toml",
        '"iva" / "rates.toml"',
        '"iva" / "recargo-rates.toml"',
        '"iva", "rates.toml"',
        '"iva", "recargo-rates.toml"',
    )
    production_sources = (
        *(repository_root / "src/cadrumo").rglob("*.py"),
        *(repository_root / "dev/registry/compiler").rglob("*.py"),
    )
    violations = {
        source.relative_to(repository_root).as_posix(): token
        for source in production_sources
        for token in forbidden
        if token in source.read_text(encoding="utf-8")
    }
    assert violations == {}


def test_iva_query_resolves_exact_date_selectors_and_provenance() -> None:
    authority = compiled_bundled_authority()
    resolved = resolve_governed_fact(
        _catalogue(),
        iva_rate_fact_query(require_eu_member_state("ES"), IvaRateKind("general"), date(2025, 6, 1)),
        authority_digest="a" * 64,
        support=committed_supported_filing_years(),
    )

    assert isinstance(resolved, ResolvedMappingFact)
    assert rate_record_from_fact(resolved, authority=authority).pct == Decimal("21")
    assert resolved.legal_refs == ("ley-37-1992:art-90",)
    assert resolved.authority_digest == "a" * 64

    # A coordinate INSIDE the supported span that the schedule does not author:
    # Germany declares only ``general`` and ``reduced``. The old probe asked for
    # the day before Spain's 2012 general rate opened, which now refuses for
    # lying below the floor -- a different refusal, and not this one.
    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        resolve_governed_fact(
            _catalogue(),
            iva_rate_fact_query(require_eu_member_state("DE"), IvaRateKind("super_reduced"), date(2025, 6, 1)),
            authority_digest="a" * 64,
            support=committed_supported_filing_years(),
        )


def test_iva_query_keeps_coexisting_rate_separate_from_ordinary_tier() -> None:
    authority = compiled_bundled_authority()
    catalogue = _catalogue()
    ordinary = resolve_governed_fact(
        catalogue,
        iva_rate_fact_query(require_eu_member_state("ES"), IvaRateKind("super_reduced"), date(2024, 11, 1)),
        authority_digest="b" * 64,
        support=committed_supported_filing_years(),
    )
    coexisting = resolve_governed_fact(
        catalogue,
        iva_rate_fact_query(
            require_eu_member_state("ES"),
            IvaRateKind("super_reduced"),
            date(2024, 11, 1),
            superseding_percentage=Decimal("2"),
        ),
        authority_digest="b" * 64,
        support=committed_supported_filing_years(),
    )

    assert isinstance(ordinary, ResolvedMappingFact)
    assert isinstance(coexisting, ResolvedMappingFact)
    assert rate_record_from_fact(ordinary, authority=authority).pct == Decimal("4")
    assert rate_record_from_fact(coexisting, authority=authority).pct == Decimal("2")
    assert rate_record_from_fact(coexisting, authority=authority).supersedes_tier_default is True


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
