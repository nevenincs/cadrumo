"""Evidence detector teeth for authority-managed IVA provider facts."""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue
from dev.registry.compiler.fact_validation import governed_fact_catalogue_failures
from cadrumo.domain.calculations.registry.schema_references import LegalReference
from dev.registry.compiler.iva import compile_iva_rate_facts, compile_iva_recargo_facts
from dev.registry.compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _grounding_failures(
    catalogue: GovernedFactCatalogue,
    *,
    legal_override: dict[str, LegalReference] | None = None,
) -> tuple[str, ...]:
    source_root = bundled_path()
    registry_root = source_root / "registry" / "aeat"
    shared = load_shared_catalogues(registry_root)
    legal = shared.legal if legal_override is None else legal_override
    return governed_fact_catalogue_failures(
        catalogue,
        legal_ref_ids=legal,
        source_ref_ids=shared.sources,
        legal_refs=legal,
        source_refs=shared.sources,
        source_root=source_root,
    )


def test_iva_and_recargo_provider_facts_are_grounded_by_registry_evidence() -> None:
    root = bundled_path("registry", "aeat")
    facts = (*compile_iva_rate_facts(root), *compile_iva_recargo_facts(root))

    assert _grounding_failures(GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})) == ()


def test_iva_provider_validation_rejects_source_citation_text_not_in_evidence() -> None:
    (fact,) = compile_iva_rate_facts(bundled_path("registry", "aeat"))
    foreign_index = next(index for index, variant in enumerate(fact.variants) if variant.source_citations)
    foreign = fact.variants[foreign_index]
    broken_citations = tuple(
        citation.model_copy(update={"required_text": ("invented IVA rate evidence anchor",)})
        for citation in foreign.source_citations
    )
    variants = list(fact.variants)
    variants[foreign_index] = foreign.model_copy(update={"source_citations": broken_citations})
    broken = GovernedFactCatalogue(
        facts={fact.fact_id: GovernedFact(fact_id=fact.fact_id, family=fact.family, variants=tuple(variants))}
    )

    assert any("missing text 'invented IVA rate evidence anchor'" in failure for failure in _grounding_failures(broken))


def test_recargo_provider_validation_rejects_legal_text_not_in_anchored_corpus() -> None:
    (fact,) = compile_iva_recargo_facts(bundled_path("registry", "aeat"))
    catalogue = GovernedFactCatalogue(facts={fact.fact_id: fact})
    shared = load_shared_catalogues(bundled_path("registry", "aeat"))
    ref_id = "ley-37-1992:art-161"
    legal = dict(shared.legal)
    legal[ref_id] = legal[ref_id].model_copy(update={"required_text": ("invented recargo corpus anchor",)})

    assert any(
        "has invalid legal evidence 'ley-37-1992:art-161'" in failure
        for failure in _grounding_failures(catalogue, legal_override=legal)
    )
