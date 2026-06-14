"""Tests for Art. 61 LIRPF custodia compartida prorrata 50 % axis.

Covers:
- DescendantInfo.custodia_compartida field: default False, accepted True
- RentaFamilyProfile.custodia_compartida_count derived property
- RentaFamilyProfile.custodia_compartida_prorrata_factor per-descendant factor
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

from .._descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)
from ..family import DescendantInfo, RentaFamilyProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

FILING_YEAR = 2024

# Registry-authoritative Art. 58 amounts (2024 revision)
_MINIMO_1 = Decimal("2400")
_MENOR_TRES = Decimal("2800")


# ---------------------------------------------------------------------------
# DescendantInfo.custodia_compartida field
# ---------------------------------------------------------------------------


def test_custodia_compartida_defaults_false() -> None:
    d = DescendantInfo(birth_date=date(2020, 3, 15))
    assert d.custodia_compartida is False


def test_custodia_compartida_accepts_true() -> None:
    d = DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True)
    assert d.custodia_compartida is True


# ---------------------------------------------------------------------------
# RentaFamilyProfile.custodia_compartida_count
# ---------------------------------------------------------------------------


def test_custodia_compartida_count_zero_when_no_descendants() -> None:
    p = RentaFamilyProfile()
    assert p.custodia_compartida_count(FILING_YEAR) == 0


def test_custodia_compartida_count_zero_when_none_flagged() -> None:
    p = RentaFamilyProfile(descendientes=(DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=False),))
    assert p.custodia_compartida_count(FILING_YEAR) == 0


def test_custodia_compartida_count_one_when_one_flagged_eligible() -> None:
    p = RentaFamilyProfile(descendientes=(DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True),))
    assert p.custodia_compartida_count(FILING_YEAR) == 1


def test_custodia_compartida_count_ignores_ineligible() -> None:
    # A 26-year-old without discapacidad is not eligible for the ordinary mínimo,
    # so custodia_compartida on such a descendant does not increment the count.
    p = RentaFamilyProfile(descendientes=(DescendantInfo(birth_date=date(1998, 1, 1), custodia_compartida=True),))
    assert p.custodia_compartida_count(FILING_YEAR) == 0


# ---------------------------------------------------------------------------
# RentaFamilyProfile.custodia_compartida_prorrata_factor
# ---------------------------------------------------------------------------


def test_prorrata_factor_is_half_for_custodia_eligible() -> None:
    d = DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True)
    p = RentaFamilyProfile(descendientes=(d,))
    assert p.custodia_compartida_prorrata_factor(d, FILING_YEAR) == Decimal("0.5")


def test_prorrata_factor_is_one_for_no_custodia() -> None:
    d = DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=False)
    p = RentaFamilyProfile(descendientes=(d,))
    assert p.custodia_compartida_prorrata_factor(d, FILING_YEAR) == Decimal("1")


def test_prorrata_factor_is_one_for_ineligible_with_custodia() -> None:
    # Age 26, no discapacidad — not mínimo-eligible even with custodia_compartida.
    d = DescendantInfo(birth_date=date(1998, 1, 1), custodia_compartida=True)
    p = RentaFamilyProfile(descendientes=(d,))
    assert p.custodia_compartida_prorrata_factor(d, FILING_YEAR) == Decimal("1")


# ---------------------------------------------------------------------------
# Two-progenitor scenario — each gets 50 % of mínimo primer hijo
# ---------------------------------------------------------------------------


def _mínimo_primer_hijo_with_prorrata(family: RentaFamilyProfile, filing_year: int) -> Decimal:
    """Compute mínimo primer hijo applying Art. 61 prorrata.

    Each eligible descendant contributes _MINIMO_1 (full year) multiplied by
    the per-descendant prorrata factor (0.5 when custodia compartida).
    """
    eligible = [d for d in family.descendientes if d.is_eligible_ordinary(filing_year)]
    if not eligible:
        return Decimal("0")
    first = eligible[0]
    prorrata = family.custodia_compartida_prorrata_factor(first, filing_year)
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


def test_advisory_none_when_no_custodia() -> None:
    p = RentaFamilyProfile(descendientes=(DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=False),))
    assert p.custodia_compartida_advisory(FILING_YEAR) is None


def test_advisory_returns_string_when_custodia_present() -> None:
    p = RentaFamilyProfile(descendientes=(DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True),))
    advisory = p.custodia_compartida_advisory(FILING_YEAR)
    assert advisory is not None
    assert isinstance(advisory, str)
    assert len(advisory) > 0


def test_advisory_antitautology_custodia_vs_no_custodia() -> None:
    """The advisory differs between a custodia and a non-custodia profile."""
    with_custodia = RentaFamilyProfile(
        descendientes=(DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True),),
    )
    without_custodia = RentaFamilyProfile(
        descendientes=(DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=False),),
    )
    assert with_custodia.custodia_compartida_advisory(FILING_YEAR) is not None
    assert without_custodia.custodia_compartida_advisory(FILING_YEAR) is None


# ---------------------------------------------------------------------------
# DescendantInfo facts roundtrip with custodia_compartida
# ---------------------------------------------------------------------------


class TestCustodiaCompartidaRoundtrip:
    def test_custodia_true_persists_and_reloads(self) -> None:
        d = DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True)
        facts = dict(descendant_facts_from_list((d,)))
        reloaded = descendant_list_from_facts(facts)
        assert len(reloaded) == 1
        assert reloaded[0].custodia_compartida is True

    def test_custodia_false_omitted_from_facts(self) -> None:
        # When False, no fact key is written (the absent key defaults to False on reload).
        d = DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=False)
        facts = dict(descendant_facts_from_list((d,)))
        assert "renta_family.descendiente.0.custodia_compartida" not in facts

    def test_custodia_false_roundtrips_via_absent_key(self) -> None:
        d = DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=False)
        facts = dict(descendant_facts_from_list((d,)))
        reloaded = descendant_list_from_facts(facts)
        assert reloaded[0].custodia_compartida is False

    def test_anti_tautology_removing_custodia_fact_reloads_as_false(self) -> None:
        d = DescendantInfo(birth_date=date(2020, 3, 15), custodia_compartida=True)
        facts = dict(descendant_facts_from_list((d,)))
        facts.pop("renta_family.descendiente.0.custodia_compartida")
        reloaded = descendant_list_from_facts(facts)
        assert reloaded[0].custodia_compartida is False


# ---------------------------------------------------------------------------
# parse_descendiente_flag: CUSTODIA= key
# ---------------------------------------------------------------------------


class TestParseDescendienteFlagCustodia:
    def test_custodia_true_parsed(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2020-03-15,CUSTODIA=true")
        assert d.custodia_compartida is True

    def test_custodia_false_parsed(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2020-03-15,CUSTODIA=false")
        assert d.custodia_compartida is False

    def test_custodia_absent_defaults_false(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2020-03-15")
        assert d.custodia_compartida is False

    def test_custodia_si_accepted(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2020-03-15,CUSTODIA=si")
        assert d.custodia_compartida is True
