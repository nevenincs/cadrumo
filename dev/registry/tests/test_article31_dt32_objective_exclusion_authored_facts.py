"""Temporal LIRPF article 31 and DT 32 exclusion facts."""

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.resolution import ScalarFactQuery, resolve_governed_fact
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from dev.registry.compiler.fact_loader import load_governed_facts
from dev.registry.compiler.legal_parameters import compile_legal_parameter_facts

_IDS = frozenset(
    (
        "lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur",
        "lirpf-dt-32:eo-exclusion-rendimientos-factura-eur",
        "lirpf-dt-32:eo-exclusion-compras-eur",
        "lirpf-art-31:eo-exclusion-rendimientos-agricolas-ganaderos-forestales-eur",
    )
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _catalogue() -> GovernedFactCatalogue:
    facts = load_governed_facts(bundled_path("registry", "aeat", "facts"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts if fact.fact_id in _IDS})


def _value(fact_id: str, effective_date: date) -> Decimal:
    resolved = resolve_governed_fact(
        _catalogue(),
        ScalarFactQuery(fact_id=fact_id, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date),
        authority_digest="3" * 64,
    )
    return resolved.payload.value


@pytest.mark.parametrize(
    ("fact_id", "override", "baseline"),
    (
        ("lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur", "250000", "150000"),
        ("lirpf-dt-32:eo-exclusion-rendimientos-factura-eur", "125000", "75000"),
        ("lirpf-dt-32:eo-exclusion-compras-eur", "250000", "150000"),
    ),
)
def test_dt32_override_ends_after_2024(fact_id: str, override: str, baseline: str) -> None:
    assert _value(fact_id, date(2016, 1, 1)) == Decimal(override)
    assert _value(fact_id, date(2024, 12, 31)) == Decimal(override)
    assert _value(fact_id, date(2025, 1, 1)) == Decimal(baseline)


def test_agricultural_threshold_is_direct_article31_fact_from_2016() -> None:
    fact_id = "lirpf-art-31:eo-exclusion-rendimientos-agricolas-ganaderos-forestales-eur"
    assert _value(fact_id, date(2016, 1, 1)) == Decimal("250000")
    assert _value(fact_id, date(2026, 1, 1)) == Decimal("250000")


def test_objective_exclusion_ids_are_not_legal_parameter_adapter_projections() -> None:
    adapter_ids = {fact.fact_id for fact in compile_legal_parameter_facts(bundled_path("registry", "aeat"))}
    assert not _IDS & adapter_ids
