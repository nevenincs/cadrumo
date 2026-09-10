"""Officially grounded Modelo 036 selectors for RIRPF article 95."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import (
    EntitySetFactQuery,
    ResolvedEntitySetFact,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from dev.registry.compiler.fact_validation import governed_fact_catalogue_failures
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from dev.registry.compiler.fact_loader import load_governed_facts
from dev.registry.compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SELECTOR_IDS = frozenset(
    {
        "rirpf-art-95:selector-m036-actividades-profesionales",
        "rirpf-art-95:selector-m036-actividades-agricolas-ganaderas",
        "rirpf-art-95:selector-m036-actividades-forestales",
        "rirpf-art-95:selector-m036-actividades-ganaderas-engorde-porcino-avicultura",
    }
)
_M036_TABLE_SOURCE = "aeat-m036-activity-code-table-2026-03-26"
_ARTICLE_95_SOURCE = "boe-rirpf-art-95-2023-01-26"
_FIRST_GROUNDED_DATE = date(2026, 3, 26)


def _catalogue() -> GovernedFactCatalogue:
    facts = load_governed_facts(bundled_path("registry", "aeat", "facts"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts if fact.fact_id in _SELECTOR_IDS})


def _resolve(fact_id: str, effective_date: date) -> ResolvedEntitySetFact:
    resolved = resolve_governed_fact(
        _catalogue(),
        EntitySetFactQuery(fact_id=fact_id, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date),
        authority_digest="4" * 64,
    )
    assert isinstance(resolved, ResolvedEntitySetFact)
    return resolved


@pytest.mark.parametrize(
    ("fact_id", "entities"),
    (
        ("rirpf-art-95:selector-m036-actividades-profesionales", frozenset({"A04", "A05"})),
        ("rirpf-art-95:selector-m036-actividades-agricolas-ganaderas", frozenset({"A02", "B01", "B02"})),
        ("rirpf-art-95:selector-m036-actividades-forestales", frozenset({"B03"})),
        ("rirpf-art-95:selector-m036-actividades-ganaderas-engorde-porcino-avicultura", frozenset()),
    ),
)
def test_article_95_activity_selectors_resolve_only_from_the_grounded_m036_table(
    fact_id: str, entities: frozenset[str]
) -> None:
    resolved = _resolve(fact_id, _FIRST_GROUNDED_DATE)

    assert resolved.payload.entities == entities
    assert resolved.variant_id.endswith(_FIRST_GROUNDED_DATE.isoformat())
    assert resolved.source_refs == (_M036_TABLE_SOURCE, _ARTICLE_95_SOURCE)

def test_article_95_activity_selectors_refuse_before_the_first_citable_m036_table() -> None:
    with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
        _resolve("rirpf-art-95:selector-m036-actividades-profesionales", date(2026, 3, 25))


def test_article_95_activity_selectors_cite_the_hash_pinned_table_and_boe_redaction() -> None:
    source_root = bundled_path()
    shared = load_shared_catalogues(source_root / "registry" / "aeat")
    catalogue = _catalogue()

    table = shared.sources[_M036_TABLE_SOURCE]
    assert table.sha256 == "a1c9cb40b1dbe78150421d5dd4575e1e12b0bae91c919bcabb60b5b8f012be39"
    assert table.bytes == 13893
    assert table.published_at is None
    assert table.applies_from == _FIRST_GROUNDED_DATE
    assert shared.sources[_ARTICLE_95_SOURCE].applies_from == date(2023, 1, 26)
    assert all(
        variant.valid_from == _FIRST_GROUNDED_DATE
        for fact in catalogue.facts.values()
        for variant in fact.variants
    )
    assert (
        governed_fact_catalogue_failures(
            catalogue,
            legal_ref_ids=shared.legal,
            source_ref_ids=shared.sources,
            legal_refs=shared.legal,
            source_refs=shared.sources,
            source_root=source_root,
        )
        == ()
    )
