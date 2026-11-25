"""Parity and resolution tests for the IVA recargo provider adapter."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.payloads import MappingFactPayload
from cadrumo.domain.calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedMappingFact,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import (
    GovernedFact,
    GovernedFactCatalogue,
)
from cadrumo.domain.calculations.registry.facts.variants import FactSelector
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.iva.recargo_equivalencia import (
    IVA_RECARGO_FACT_ID,
    recargo_rate_record_from_fact,
)

from ..compiler.fact_loader import load_governed_facts
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def iva_recargo_fact_query(applied_rate: Decimal, operation_date: date) -> MappingFactQuery:
    return MappingFactQuery(
        fact_id=IVA_RECARGO_FACT_ID,
        date_axis=DateAxis.DEVENGO_DATE,
        effective_date=operation_date,
        selectors=(FactSelector(name="applied_rate", value=applied_rate),),
    )


def _window(applied_rate: Decimal) -> tuple[date, date | None]:
    """Return the operation window the authored schedule gives one applied rate.

    The transitional rates are bounded by their own windows, so the days a test
    asks about come from the schedule and not from a year of its own.
    """
    (variant,) = (item for item in _authored_fact().variants if Decimal(str(item.selectors[0].value)) == applied_rate)
    assert variant.valid_from is not None
    return variant.valid_from, variant.valid_to


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
    projected: set[tuple[Decimal, date | None, date | None]] = set()
    for variant in fact.variants:
        assert isinstance(variant.payload, MappingFactPayload)
        assert {str(item.key) for item in variant.payload.entries} == {"recargo_rate", "notes"}
        projected.add((Decimal(str(variant.selectors[0].value)), variant.valid_from, variant.valid_to))

    assert fact.fact_id == IVA_RECARGO_FACT_ID == "iva-recargo-by-applied-rate"
    assert len(projected) == len(fact.variants)


def test_recargo_query_uses_applied_rate_and_inclusive_operation_window() -> None:
    catalogue = _catalogue()
    opening, closing = _window(Decimal("0.02"))
    assert closing is not None
    for boundary in (opening, closing):
        resolved = resolve_governed_fact(
            catalogue,
            iva_recargo_fact_query(Decimal("0.02"), boundary),
            authority_digest="c" * 64,
            support=committed_supported_filing_years(),
        )
        assert isinstance(resolved, ResolvedMappingFact)
        projected = recargo_rate_record_from_fact(resolved)
        assert projected.recargo_rate == Decimal("0.0026")
        assert projected.legal_refs == ("real-decreto-ley-4-2024:art-1",)
        assert resolved.authority_digest == "c" * 64

    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        resolve_governed_fact(
            catalogue,
            iva_recargo_fact_query(Decimal("0.02"), closing + timedelta(days=1)),
            authority_digest="c" * 64,
            support=committed_supported_filing_years(),
        )


def test_recargo_query_distinguishes_coexisting_applied_rates() -> None:
    catalogue = _catalogue()
    transitional_day, _end = _window(Decimal("0.05"))
    ordinary = resolve_governed_fact(
        catalogue,
        iva_recargo_fact_query(Decimal("0.10"), transitional_day),
        authority_digest="d" * 64,
        support=committed_supported_filing_years(),
    )
    transitional = resolve_governed_fact(
        catalogue,
        iva_recargo_fact_query(Decimal("0.05"), transitional_day),
        authority_digest="d" * 64,
        support=committed_supported_filing_years(),
    )

    assert isinstance(ordinary, ResolvedMappingFact)
    assert isinstance(transitional, ResolvedMappingFact)
    assert recargo_rate_record_from_fact(ordinary).recargo_rate == Decimal("0.014")
    assert recargo_rate_record_from_fact(transitional).recargo_rate == Decimal("0.0062")
