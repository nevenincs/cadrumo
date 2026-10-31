"""Regression tests for candidate-scoped applicability seed rules."""

from __future__ import annotations

import pytest

from cadrumo.core.modelo import Modelo
from cadrumo.domain.calculations.registry.applicability import hydrate_applicability_rule
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.payloads import MappingFactPayload
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from cadrumo.domain.calculations.registry.schema_revision_members import ApplicabilityRuleDefinition

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


def _declared_rule(modelo: str) -> ApplicabilityRuleDefinition:
    definition = next(item for item in compiled_bundled_authority().modelos if item.id == modelo)
    return next(rule for revision in definition.revisions.values() for rule in revision.applicability)


@pytest.mark.parametrize("modelo", ["303", "390"])
def test_a_declared_iva_rule_is_read_under_the_vocabulary_of_each_candidate(modelo: str) -> None:
    """Two validations in one process must each see their own governed facts."""
    declared = _declared_rule(modelo)
    accepting = _candidate_with_mapping_value(
        "iva-statutory-schema-vocabulary", "iva_regime.self_assessment_order", "SIMPLIFICADO"
    )
    narrowed = _candidate_with_mapping_value(
        "taxpayer-entity-vocabulary", "entity_type.order", "natural_person,legal_entity"
    )

    with validating_governed_facts(accepting):
        rule = hydrate_applicability_rule(Modelo(modelo), declared)
    assert {str(token) for token in rule.applicable_iva_regimes} == {"GENERAL", "SIMPLIFICADO"}
    assert {str(token) for token in rule.required_income_categories} == {"actividad_economica"}

    with validating_governed_facts(narrowed), pytest.raises(RegistryValidationError):
        hydrate_applicability_rule(Modelo(modelo), declared)
