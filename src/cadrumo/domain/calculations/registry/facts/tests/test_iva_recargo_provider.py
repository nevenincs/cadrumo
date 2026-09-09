"""Parity and resolution tests for the IVA recargo provider adapter."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import ResolvedMappingFact, resolve_governed_fact
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.iva.recargo_equivalencia import (
    IVA_RECARGO_FACT_ID,
    compile_iva_recargo_facts,
    iva_recargo_fact_query,
    load_recargo_rate_table,
    recargo_rate_record_from_fact,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _catalogue() -> GovernedFactCatalogue:
    fact, = compile_iva_recargo_facts(bundled_path("registry", "aeat"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact})


def test_recargo_provider_projects_every_legacy_pairing_without_loss() -> None:
    legacy = {
        (row.iva_rate, row.recargo_rate, row.effective_from, row.effective_until, row.legal_refs)
        for row in load_recargo_rate_table()
    }
    fact, = compile_iva_recargo_facts(bundled_path("registry", "aeat"))
    projected = {
        (
            Decimal(str(variant.selectors[0].value)),
            Decimal(str({str(item.key): item.value for item in variant.payload.entries}["recargo_rate"])),
            variant.valid_from,
            variant.valid_to,
            variant.legal_refs,
        )
        for variant in fact.variants
    }

    assert fact.fact_id == IVA_RECARGO_FACT_ID == "iva-recargo-by-applied-rate"
    assert projected == legacy


def test_recargo_query_uses_applied_rate_and_inclusive_operation_window() -> None:
    catalogue = _catalogue()
    for boundary in (date(2024, 10, 1), date(2024, 12, 31)):
        resolved = resolve_governed_fact(
            catalogue,
            iva_recargo_fact_query(Decimal("0.02"), boundary),
            authority_digest="c" * 64,
        )
        assert isinstance(resolved, ResolvedMappingFact)
        projected = recargo_rate_record_from_fact(resolved)
        assert projected.recargo_rate == Decimal("0.0026")
        assert projected.legal_refs == ("real-decreto-ley-4-2024:art-1",)
        assert resolved.authority_digest == "c" * 64

    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        resolve_governed_fact(
            catalogue,
            iva_recargo_fact_query(Decimal("0.02"), date(2025, 1, 1)),
            authority_digest="c" * 64,
        )


def test_recargo_query_distinguishes_coexisting_applied_rates() -> None:
    catalogue = _catalogue()
    ordinary = resolve_governed_fact(
        catalogue,
        iva_recargo_fact_query(Decimal("0.10"), date(2024, 6, 1)),
        authority_digest="d" * 64,
    )
    transitional = resolve_governed_fact(
        catalogue,
        iva_recargo_fact_query(Decimal("0.05"), date(2024, 6, 1)),
        authority_digest="d" * 64,
    )

    assert isinstance(ordinary, ResolvedMappingFact)
    assert isinstance(transitional, ResolvedMappingFact)
    assert recargo_rate_record_from_fact(ordinary).recargo_rate == Decimal("0.014")
    assert recargo_rate_record_from_fact(transitional).recargo_rate == Decimal("0.0062")
