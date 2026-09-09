"""Parity tests for global legal-parameter fact projections."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.legal_parameters import (
    LEGAL_PARAMETER_FACT_IDS,
    LEGAL_PARAMETER_PROVIDER_DIRECTORY,
    LEGAL_PARAMETER_PROVIDER_ID,
    compile_legal_parameter_facts,
    legal_parameter_entity_set_query,
    legal_parameter_scalar_query,
)
from cadrumo.domain.calculations.registry.facts.providers import FACT_PROVIDER_REGISTRATIONS
from cadrumo.domain.calculations.registry.facts.resolution import (
    ResolvedEntitySetFact,
    ResolvedScalarFact,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.loader import load_legal_parameters_only

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _catalogue() -> GovernedFactCatalogue:
    facts = compile_legal_parameter_facts(bundled_path("registry", "aeat"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})


def test_provider_projects_exactly_the_21_ledgered_parameter_ids() -> None:
    facts = compile_legal_parameter_facts(bundled_path("registry", "aeat"))

    assert len(LEGAL_PARAMETER_FACT_IDS) == 21
    assert {fact.fact_id for fact in facts} == LEGAL_PARAMETER_FACT_IDS


def test_legal_parameter_provider_owns_the_existing_legal_catalogue() -> None:
    registration = next(
        item for item in FACT_PROVIDER_REGISTRATIONS if item.provider_id == LEGAL_PARAMETER_PROVIDER_ID
    )

    assert registration.owned_directories == (LEGAL_PARAMETER_PROVIDER_DIRECTORY,)
    assert registration.collect_fingerprints(bundled_path("registry", "aeat"))


def test_scalar_projection_preserves_value_unit_review_and_legal_provenance() -> None:
    parameter_id = "lirpf-art-101:retencion-administrador-incn-umbral-eur"
    legacy = load_legal_parameters_only(bundled_path("registry", "aeat"))[parameter_id]
    resolved = resolve_governed_fact(
        _catalogue(),
        legal_parameter_scalar_query(parameter_id, date(2025, 12, 31)),
        authority_digest="e" * 64,
    )

    assert isinstance(resolved, ResolvedScalarFact)
    assert resolved.payload.value == Decimal(legacy.value)
    assert resolved.payload.unit == legacy.unit
    assert resolved.legal_refs == legacy.legal_refs
    assert resolved.review_status is legacy.review_status
    assert resolved.authority_digest == "e" * 64


def test_classification_projection_preserves_nonempty_and_explicit_empty_sets() -> None:
    catalogue = _catalogue()
    populated = resolve_governed_fact(
        catalogue,
        legal_parameter_entity_set_query(
            "rirpf-art-95:selector-m036-actividades-profesionales",
            date(2025, 12, 31),
        ),
        authority_digest="f" * 64,
    )
    empty = resolve_governed_fact(
        catalogue,
        legal_parameter_entity_set_query(
            "rirpf-art-95:selector-m036-actividades-ganaderas-engorde-porcino-avicultura",
            date(2025, 12, 31),
        ),
        authority_digest="f" * 64,
    )

    assert isinstance(populated, ResolvedEntitySetFact)
    assert populated.payload.entities == frozenset({"A04", "A05"})
    assert isinstance(empty, ResolvedEntitySetFact)
    assert empty.payload.entities == frozenset()


def test_query_helpers_refuse_wrong_family_ids() -> None:
    with pytest.raises(RegistryValidationError, match="is not an enrolled scalar"):
        legal_parameter_scalar_query(
            "rirpf-art-95:selector-m036-actividades-profesionales",
            date(2025, 1, 1),
        )
    with pytest.raises(RegistryValidationError, match="is not an enrolled entity set"):
        legal_parameter_entity_set_query(
            "lirpf-art-101:retencion-administrador-general",
            date(2025, 1, 1),
        )
