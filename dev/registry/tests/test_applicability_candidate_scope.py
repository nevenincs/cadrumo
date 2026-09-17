"""Regression tests for candidate-scoped applicability seed rules."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.applicability import MODELO_APPLICABILITY_RULES
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue, MappingFactPayload
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _candidate_with_mapping_value(fact_id: str, key: str, value: str) -> CandidateFactAuthority:
    catalogues = compiled_bundled_authority().catalogues
    catalogue = catalogues.facts
    fact = catalogue.facts[fact_id]
    variant = fact.variants[0]
    payload = variant.payload
    if not isinstance(payload, MappingFactPayload):
        raise TypeError(f"candidate fact {fact_id!r} must use a mapping payload")
    entries = tuple(
        entry.model_copy(update={"value": value}) if entry.key == key else entry for entry in payload.entries
    )
    changed_fact = fact.model_copy(
        update={"variants": (variant.model_copy(update={"payload": payload.model_copy(update={"entries": entries})}),)},
    )
    facts = dict(catalogue.facts)
    facts[fact_id] = changed_fact
    return CandidateFactAuthority(GovernedFactCatalogue(facts=facts), catalogues.require_supported_filing_years())


def test_iva_seed_rules_do_not_capture_the_first_candidate_vocabulary() -> None:
    """Two validations in one process must each see their own governed facts."""
    first_candidate = _candidate_with_mapping_value(
        "taxpayer-entity-vocabulary",
        "entity_type.order",
        "natural_person,legal_entity",
    )
    second_candidate = _candidate_with_mapping_value(
        "iva-statutory-schema-vocabulary",
        "iva_regime.self_assessment_order",
        "SIMPLIFICADO",
    )

    with validating_governed_facts(first_candidate):
        first = MODELO_APPLICABILITY_RULES["303"]
    with validating_governed_facts(second_candidate):
        second = MODELO_APPLICABILITY_RULES["303"]

    assert {str(token) for token in first.applicable_entity_types} == {"natural_person", "legal_entity"}
    assert {str(token) for token in first.applicable_iva_regimes} == {"GENERAL", "SIMPLIFICADO"}
    assert {str(token) for token in second.applicable_entity_types} == {
        "natural_person",
        "legal_entity",
        "attribution_entity",
    }
    assert {str(token) for token in second.applicable_iva_regimes} == {"SIMPLIFICADO"}
