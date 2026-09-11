"""Parity and resolution tests for the IVA recargo provider adapter."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

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
    MappingFactPayload,
)
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.iva.recargo_equivalencia import (
    IVA_RECARGO_FACT_ID,
    recargo_rate_record_from_fact,
)

from ..compiler.fact_loader import load_governed_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def iva_recargo_fact_query(applied_rate: Decimal, operation_date: date) -> MappingFactQuery:
    return MappingFactQuery(
        fact_id=IVA_RECARGO_FACT_ID,
        date_axis=DateAxis.DEVENGO_DATE,
        effective_date=operation_date,
        selectors=(FactSelector(name="applied_rate", value=applied_rate),),
    )


def _catalogue() -> GovernedFactCatalogue:
    fact = _authored_fact()
    return GovernedFactCatalogue(facts={fact.fact_id: fact})


def _authored_fact() -> GovernedFact:
    return next(
        fact
        for fact in load_governed_facts(bundled_path("registry", "aeat", "facts"))
        if fact.fact_id == IVA_RECARGO_FACT_ID
    )


def test_authored_recargo_fact_emits_identity_unique_authority_variants() -> None:
    """The normalized fact holds one unambiguous authority variant per pairing."""
    fact = _authored_fact()
    projected: set[tuple[Decimal, date, date | None]] = set()
    for variant in fact.variants:
        assert isinstance(variant.payload, MappingFactPayload)
        assert {str(item.key) for item in variant.payload.entries} == {"recargo_rate", "notes"}
        projected.add((Decimal(str(variant.selectors[0].value)), variant.valid_from, variant.valid_to))

    assert fact.fact_id == IVA_RECARGO_FACT_ID == "iva-recargo-by-applied-rate"
    assert len(projected) == len(fact.variants)


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
