"""Tests for Art. 61 LIRPF custodia compartida prorrata 50 % axis.

Covers:
- DescendantInfo.custodia_compartida field: default False, accepted True
- RentaFamilyProfile.custodia_compartida_count derived property
- RentaFamilyProfile.minimo_prorrata_factor per-descendant factor
- RentaFamilyProfile.custodia_compartida_advisory (tr-based string or None)
- DescendantInfo roundtrip via facts with custodia_compartida=True
- parse_descendiente_flag CUSTODIA= key acceptance
- Two-progenitor scenario: each gets 50 % of the mínimo
- Anti-tautology: without custodia_compartida, full mínimo applies
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..descendant import DescendantInfo
from ..descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)
from ..family_profile import RentaFamilyProfile
from ._registry_thresholds import (
    registry_birth_order_amounts,
    registry_menor_tres_supplement,
    registry_thresholds,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

FILING_YEAR = 2024

# Art. 58 amounts read from the registry, never restated as Python literals
# (`aeat-registry-authority-flow`).
_MINIMO_1 = registry_birth_order_amounts(FILING_YEAR)[0]
_MENOR_TRES = registry_menor_tres_supplement(FILING_YEAR)
_THRESHOLDS = registry_thresholds(FILING_YEAR)
_CUSTODIA_FACT_KEY = "renta_family.descendiente.0.custodia_compartida"
_CUSTODIA_FIELD_CASES = (
    ("default", DescendantInfo(birth_date=date(2020, 3, 15)), False),
    ("explicit-true", DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True), True),
)
_CUSTODIA_COUNT_CASES = (
    ("no-descendants", (), 0),
    ("none-flagged", (DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=False),), 0),
    ("one-eligible", (DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True),), 1),
    ("ineligible", (DescendantInfo(birth_date=date(1998, 1, 1), custodia_compartida=True),), 0),
)
_PRORRATA_FACTOR_CASES = (
    ("custodia-eligible", DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True), Decimal("0.5")),
    ("no-custodia", DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=False), Decimal("1")),
    ("ineligible-custodia", DescendantInfo(birth_date=date(1998, 1, 1), custodia_compartida=True), Decimal("1")),
)
_PARSE_CUSTODIA_CASES = (
    ("true", "NACIMIENTO=2020-03-15,CUSTODIA=true", True),
    ("false", "NACIMIENTO=2020-03-15,CUSTODIA=false", False),
    ("absent", "NACIMIENTO=2020-03-15", False),
    ("si", "NACIMIENTO=2020-03-15,CUSTODIA=si", True),
)


# ---------------------------------------------------------------------------
# DescendantInfo.custodia_compartida field
# ---------------------------------------------------------------------------


def test_custodia_compartida_field_cases() -> None:
    for case_id, descendant, expected in _CUSTODIA_FIELD_CASES:
        assert descendant.custodia_compartida is expected, case_id


# ---------------------------------------------------------------------------
# RentaFamilyProfile.custodia_compartida_count
# ---------------------------------------------------------------------------


def test_custodia_compartida_count_cases() -> None:
    for case_id, descendants, expected in _CUSTODIA_COUNT_CASES:
        p = RentaFamilyProfile(descendientes=descendants)
        assert p.custodia_compartida_count(FILING_YEAR, thresholds=_THRESHOLDS) == expected, case_id


# ---------------------------------------------------------------------------
# RentaFamilyProfile.minimo_prorrata_factor
# ---------------------------------------------------------------------------


def test_prorrata_factor_cases() -> None:
    for case_id, descendant, expected in _PRORRATA_FACTOR_CASES:
        p = RentaFamilyProfile(descendientes=(descendant,))
        assert p.minimo_prorrata_factor(descendant, FILING_YEAR, thresholds=_THRESHOLDS) == expected, case_id


# ---------------------------------------------------------------------------
# Two-progenitor scenario — each gets 50 % of mínimo primer hijo
# ---------------------------------------------------------------------------


def _mínimo_primer_hijo_with_prorrata(family: RentaFamilyProfile, filing_year: int) -> Decimal:
    """Compute mínimo primer hijo applying Art. 61 prorrata.

    Each eligible descendant contributes _MINIMO_1 (full year) multiplied by
    the per-descendant prorrata factor (0.5 when custodia compartida).
    """
    eligible = [d for d in family.descendientes if d.is_eligible_ordinary(filing_year, thresholds=_THRESHOLDS)]
    if not eligible:
        return Decimal("0")
    first = eligible[0]
    prorrata = family.minimo_prorrata_factor(first, filing_year, thresholds=_THRESHOLDS)
    return _MINIMO_1 * prorrata


def test_two_progenitors_each_get_50_pct_minimo() -> None:
    """Art. 61 LIRPF: shared custody → each progenitor claims 50 % of the mínimo.

    Expected: each progenitor profile has 1 eligible custodia child and each
    receives €1,200 (50 % of €2,400) as their mínimo primer hijo contribution.
    """
    # Progenitor A (the child lives with both; custodia_compartida=True)
    child_a = DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True)
    family_a = RentaFamilyProfile(descendientes=(child_a,))

    # Progenitor B — same child, same flag
    child_b = DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True)
    family_b = RentaFamilyProfile(descendientes=(child_b,))

    minimo_a = _mínimo_primer_hijo_with_prorrata(family_a, FILING_YEAR)
    minimo_b = _mínimo_primer_hijo_with_prorrata(family_b, FILING_YEAR)

    assert minimo_a == _MINIMO_1 * Decimal("0.5")  # €1,200
    assert minimo_b == _MINIMO_1 * Decimal("0.5")  # €1,200
    # Combined equals full mínimo — no double-dip, no shortfall.
    assert minimo_a + minimo_b == _MINIMO_1


# Anti-tautology: without custodia_compartida, full mínimo applies.
def test_antitautology_without_custodia_full_minimo() -> None:
    """Without custodia_compartida=True the prorrata factor is 1 (full mínimo)."""
    child = DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=False)
    family = RentaFamilyProfile(descendientes=(child,))
    minimo = _mínimo_primer_hijo_with_prorrata(family, FILING_YEAR)
    assert minimo == _MINIMO_1  # €2,400, not €1,200


# ---------------------------------------------------------------------------
# Advisory
# ---------------------------------------------------------------------------


def test_advisory_antitautology_custodia_vs_no_custodia() -> None:
    """The advisory differs between a custodia and a non-custodia profile."""
    with_custodia = RentaFamilyProfile(
        descendientes=(DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True),),
    )
    without_custodia = RentaFamilyProfile(
        descendientes=(DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=False),),
    )
    advisory = with_custodia.custodia_compartida_advisory(FILING_YEAR, thresholds=_THRESHOLDS)
    assert advisory is not None
    assert isinstance(advisory, str)
    assert len(advisory) > 0
    assert without_custodia.custodia_compartida_advisory(FILING_YEAR, thresholds=_THRESHOLDS) is None


# ---------------------------------------------------------------------------
# DescendantInfo facts roundtrip with custodia_compartida
# ---------------------------------------------------------------------------


class TestCustodiaCompartidaRoundtrip:
    def test_cases(self) -> None:
        d = DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True)
        facts = dict(descendant_facts_from_list((d,)))
        reloaded = descendant_list_from_facts(facts)
        assert len(reloaded) == 1
        assert reloaded[0].custodia_compartida is True

        # When False, no fact key is written (the absent key defaults to False on reload).
        d = DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=False)
        facts = dict(descendant_facts_from_list((d,)))
        assert _CUSTODIA_FACT_KEY not in facts

        reloaded = descendant_list_from_facts(facts)
        assert reloaded[0].custodia_compartida is False

        d = DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True)
        facts = dict(descendant_facts_from_list((d,)))
        facts.pop(_CUSTODIA_FACT_KEY)
        reloaded = descendant_list_from_facts(facts)
        assert reloaded[0].custodia_compartida is False


# ---------------------------------------------------------------------------
# parse_descendiente_flag: CUSTODIA= key
# ---------------------------------------------------------------------------


class TestParseDescendienteFlagCustodia:
    def test_cases(self) -> None:
        for case_id, raw, expected in _PARSE_CUSTODIA_CASES:
            d = parse_descendiente_flag(raw)
            assert d.custodia_compartida is expected, case_id
