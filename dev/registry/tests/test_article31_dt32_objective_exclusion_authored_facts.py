"""Temporal LIRPF article 31 and DT 32 exclusion facts."""

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.resolution import (
    ResolvedScalarFact,
    ScalarFactQuery,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.schema_base import DateAxis

from ..compiler.fact_loader import load_governed_facts
from .authored_edition_support import legal_text_match
from .profile_schema_support import authored_history_supported_filing_years, committed_supported_filing_years

_IDS = frozenset(
    (
        "lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur",
        "lirpf-dt-32:eo-exclusion-rendimientos-factura-eur",
        "lirpf-dt-32:eo-exclusion-compras-eur",
        "lirpf-art-31:eo-exclusion-rendimientos-agricolas-ganaderos-forestales-eur",
    )
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORT = committed_supported_filing_years()
# LIRPF DT 32 raises these thresholds for the span of exercises its heading names;
# the article 31 baseline governs every later exercise.
_DT32_WINDOW = legal_text_match("ley-35-2006:dt-32", r"en los ejercicios (\d{4}) a (\d{4})")
_DT32_FIRST_EXERCISE = int(_DT32_WINDOW.group(1))
_DT32_LAST_EXTENDED_EXERCISE = int(_DT32_WINDOW.group(2))


def _catalogue() -> GovernedFactCatalogue:
    facts = load_governed_facts(bundled_path("registry", "aeat", "facts"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts if fact.fact_id in _IDS})


def _value(fact_id: str, effective_date: date) -> Decimal:
    resolved = resolve_governed_fact(
        _catalogue(),
        ScalarFactQuery(fact_id=fact_id, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date),
        authority_digest="3" * 64,
        support=authored_history_supported_filing_years(),
    )
    if not isinstance(resolved, ResolvedScalarFact):
        raise TypeError(f"fact {fact_id!r} resolved to a non-scalar payload")
    value = resolved.payload.value
    if not isinstance(value, Decimal):
        raise TypeError(f"fact {fact_id!r} resolved to a non-decimal scalar")
    return value


@pytest.mark.parametrize(
    ("fact_id", "override", "baseline"),
    (
        ("lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur", "250000", "150000"),
        ("lirpf-dt-32:eo-exclusion-rendimientos-factura-eur", "125000", "75000"),
        ("lirpf-dt-32:eo-exclusion-compras-eur", "250000", "150000"),
    ),
)
def test_dt32_override_ends_after_its_last_extended_exercise(fact_id: str, override: str, baseline: str) -> None:
    assert _value(fact_id, date(_DT32_FIRST_EXERCISE, 1, 1)) == Decimal(override)
    assert _value(fact_id, date(_DT32_LAST_EXTENDED_EXERCISE, 12, 31)) == Decimal(override)
    assert _value(fact_id, date(_DT32_LAST_EXTENDED_EXERCISE + 1, 1, 1)) == Decimal(baseline)
    for year in _SUPPORT.years:
        expected = override if year <= _DT32_LAST_EXTENDED_EXERCISE else baseline
        assert _value(fact_id, date(year, 1, 1)) == Decimal(expected), year


def test_agricultural_threshold_is_direct_article31_fact_from_the_dt32_start() -> None:
    fact_id = "lirpf-art-31:eo-exclusion-rendimientos-agricolas-ganaderos-forestales-eur"
    for year in (_DT32_FIRST_EXERCISE, *_SUPPORT.years):
        assert _value(fact_id, date(year, 1, 1)) == Decimal("250000"), year
