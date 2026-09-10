"""Parity tests for global legal-parameter fact projections."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.legal_parameters import (
    LEGAL_PARAMETER_FACT_IDS,
    LEGAL_PARAMETER_PROVIDER_DIRECTORY,
    LEGAL_PARAMETER_PROVIDER_ID,
    compile_legal_parameter_facts,
)
from cadrumo.domain.calculations.registry.facts.providers import FACT_PROVIDER_REGISTRATIONS
from cadrumo.domain.calculations.registry.facts.resolution import (
    ResolvedScalarFact,
    ScalarFactQuery,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue
from cadrumo.domain.calculations.registry.facts.validation import governed_fact_catalogue_failures
from cadrumo.domain.calculations.registry.loader import load_legal_parameters_only, load_shared_catalogues
from cadrumo.domain.calculations.registry.schema_base import DateAxis

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _catalogue() -> GovernedFactCatalogue:
    facts = compile_legal_parameter_facts(bundled_path("registry", "aeat"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})


def _grounding_failures(catalogue: GovernedFactCatalogue) -> tuple[str, ...]:
    source_root = bundled_path()
    shared = load_shared_catalogues(source_root / "registry" / "aeat")
    return governed_fact_catalogue_failures(
        catalogue,
        legal_ref_ids=shared.legal,
        source_ref_ids=shared.sources,
        legal_refs=shared.legal,
        source_refs=shared.sources,
        source_root=source_root,
    )


def test_provider_projects_exactly_the_4_remaining_adapter_parameter_ids() -> None:
    facts = compile_legal_parameter_facts(bundled_path("registry", "aeat"))

    assert len(LEGAL_PARAMETER_FACT_IDS) == 4
    assert {fact.fact_id for fact in facts} == LEGAL_PARAMETER_FACT_IDS


def test_legal_parameter_provider_owns_the_existing_legal_catalogue() -> None:
    registration = next(item for item in FACT_PROVIDER_REGISTRATIONS if item.provider_id == LEGAL_PARAMETER_PROVIDER_ID)

    assert registration.owned_directories == (LEGAL_PARAMETER_PROVIDER_DIRECTORY,)
    assert registration.collect_fingerprints(bundled_path("registry", "aeat"))


def test_scalar_projection_preserves_value_unit_review_and_legal_provenance() -> None:
    parameter_id = "lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur"
    legacy = load_legal_parameters_only(bundled_path("registry", "aeat"))[parameter_id]
    resolved = resolve_governed_fact(
        _catalogue(),
        ScalarFactQuery(
            fact_id=parameter_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(2025, 12, 31),
        ),
        authority_digest="e" * 64,
    )

    assert isinstance(resolved, ResolvedScalarFact)
    assert resolved.payload.value == Decimal(legacy.value)
    assert resolved.payload.unit == legacy.unit
    assert resolved.legal_refs == legacy.legal_refs
    assert resolved.review_status is legacy.review_status
    assert resolved.authority_digest == "e" * 64


def test_all_legal_parameter_resolutions_retain_anchored_bundled_legal_evidence() -> None:
    catalogue = _catalogue()

    assert _grounding_failures(catalogue) == ()
    assert all(variant.legal_refs for fact in catalogue.facts.values() for variant in fact.variants)


def test_production_validation_rejects_a_variant_with_both_evidence_lanes_erased() -> None:
    catalogue = _catalogue()
    fact = next(iter(catalogue.facts.values()))
    erased = fact.variants[0].model_copy(
        update={"legal_refs": (), "source_refs": (), "source_citations": ()},
    )
    with pytest.raises(ValidationError, match="must declare legal or source evidence"):
        GovernedFact(
            fact_id=fact.fact_id,
            family=fact.family,
            variants=(erased,),
        )
def test_fact_families_define_the_canonical_query_contract() -> None:
    facts = _catalogue().facts

    assert facts["lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur"].family.value == "scalar"
