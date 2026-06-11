"""Tests for DescendantInfo, derived properties, and Art. 58 mínimo oracle.

Oracle values come from the AEAT Modelo 100 2024 official parameters:
  - primer hijo:             €2,400  (renta-2024-minimo-descendientes-primer-hijo-2024)
  - segundo hijo:            €2,700  (renta-2024-minimo-descendientes-segundo-hijo-2024)
  - tercer hijo:             €4,000  (renta-2024-minimo-descendientes-tercer-hijo-2024)
  - cuarto y siguientes:     €4,500  (renta-2024-minimo-descendientes-cuarto-y-siguientes-2024)
  - menor de 3 años:         €3,000  (renta-2024-minimo-descendientes-menor-tres-anos-2024)

The registry parameters are the authoritative source; oracle test expected
values are derived from those registry-declared amounts, NOT from the formula
under test.

The spec's €2,800 for the bajo-3-años supplement differs from the registry
€3,000 — the registry is authoritative; this test suite uses €3,000.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .._descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)
from ..family import DescendantInfo, RentaFamilyProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

FILING_YEAR = 2024

# Registry-authoritative Art. 58 amounts (from TOML parameters in 2024 revision)
_MINIMO_1 = Decimal("2400")
_MINIMO_2 = Decimal("2700")
_MINIMO_3 = Decimal("4000")
_MINIMO_4PLUS = Decimal("4500")
_MENOR_TRES = Decimal("3000")


# ---------------------------------------------------------------------------
# DescendantInfo model validation
# ---------------------------------------------------------------------------


class TestDescendantInfoValidation:
    def test_requires_birth_date(self) -> None:
        # NEGATIVE TEST: deliberately call without required birth_date (ty: missing-argument, py: reportCallIssue)
        with pytest.raises(ValidationError):
            DescendantInfo()  # type: ignore

    def test_birth_date_from_iso_string(self) -> None:
        d = DescendantInfo.model_validate({"birth_date": "2020-03-15"})
        assert d.birth_date == date(2020, 3, 15)

    def test_adoption_date_must_be_gte_birth_date(self) -> None:
        with pytest.raises((ValidationError, ValueError), match="adoption_date"):
            DescendantInfo(birth_date=date(2020, 6, 1), adoption_date=date(2020, 5, 31))

    def test_adoption_date_equal_to_birth_date_is_accepted(self) -> None:
        d = DescendantInfo(birth_date=date(2020, 6, 1), adoption_date=date(2020, 6, 1))
        assert d.adoption_date == date(2020, 6, 1)

    def test_adoption_date_in_future_is_rejected(self) -> None:
        with pytest.raises((ValidationError, ValueError), match="future"):
            DescendantInfo(birth_date=date(2000, 1, 1), adoption_date=date(2099, 1, 1))

    def test_discapacidad_grado_accepts_0_33_65(self) -> None:
        for grade in (0, 33, 65):
            d = DescendantInfo(birth_date=date(2010, 1, 1), discapacidad_grado=grade)
            assert d.discapacidad_grado == grade

    def test_discapacidad_grado_rejects_invalid_value(self) -> None:
        # NEGATIVE TEST: deliberately invalid grado (ty: invalid-argument-type, py: reportArgumentType)
        with pytest.raises(ValidationError):
            DescendantInfo(birth_date=date(2010, 1, 1), discapacidad_grado=50)  # type: ignore

    def test_nif_must_be_9_characters(self) -> None:
        with pytest.raises((ValidationError, ValueError), match="9 characters"):
            DescendantInfo(birth_date=date(2010, 1, 1), nif="12345")

    def test_blank_nif_is_rejected(self) -> None:
        with pytest.raises((ValidationError, ValueError)):
            DescendantInfo(birth_date=date(2010, 1, 1), nif="  ")

    def test_nif_is_normalised_to_uppercase(self) -> None:
        d = DescendantInfo(birth_date=date(2010, 1, 1), nif="taxidabcd")
        assert d.nif == "TAXIDABCD"

    def test_frozen_model_rejects_mutation(self) -> None:
        d = DescendantInfo(birth_date=date(2010, 1, 1))
        with pytest.raises(ValidationError, match="frozen"):
            d.__setattr__("birth_date", date(2011, 1, 1))


# ---------------------------------------------------------------------------
# DescendantInfo derived methods
# ---------------------------------------------------------------------------


class TestDescendantInfoAgeCalculation:
    def test_age_at_year_end_2024_for_2023_january_birth(self) -> None:
        d = DescendantInfo(birth_date=date(2023, 1, 15))
        assert d.age_at_year_end(2024) == 1

    def test_age_at_year_end_birthday_on_dec_31(self) -> None:
        d = DescendantInfo(birth_date=date(2022, 12, 31))
        assert d.age_at_year_end(2024) == 2

    def test_age_at_year_end_birthday_in_2024_is_0(self) -> None:
        d = DescendantInfo(birth_date=date(2024, 6, 15))
        assert d.age_at_year_end(2024) == 0

    def test_is_eligible_ordinary_age_24_is_true(self) -> None:
        d = DescendantInfo(birth_date=date(2000, 1, 1))
        assert d.is_eligible_ordinary(2024) is True

    def test_is_eligible_ordinary_age_25_is_false(self) -> None:
        d = DescendantInfo(birth_date=date(1999, 1, 1))
        assert d.is_eligible_ordinary(2024) is False

    def test_is_eligible_ordinary_over_25_with_discapacidad_is_true(self) -> None:
        d = DescendantInfo(birth_date=date(1990, 1, 1), discapacidad_grado=33)
        assert d.is_eligible_ordinary(2024) is True

    def test_is_eligible_ordinary_non_cohabiting_is_false(self) -> None:
        d = DescendantInfo(birth_date=date(2020, 1, 1), convive_con_contribuyente=False)
        assert d.is_eligible_ordinary(2024) is False

    def test_is_eligible_menor_tres_age_1_is_true(self) -> None:
        d = DescendantInfo(birth_date=date(2023, 1, 15))
        assert d.is_eligible_menor_tres(2024) is True

    def test_is_eligible_menor_tres_age_3_is_false(self) -> None:
        d = DescendantInfo(birth_date=date(2021, 12, 31))
        assert d.is_eligible_menor_tres(2024) is False

    def test_joined_before_1_july_true_for_prior_year_birth(self) -> None:
        d = DescendantInfo(birth_date=date(2020, 3, 15))
        assert d.joined_before_or_on_1_july(2024) is True

    def test_joined_before_1_july_true_for_june_30_birth_in_filing_year(self) -> None:
        d = DescendantInfo(birth_date=date(2024, 6, 30))
        assert d.joined_before_or_on_1_july(2024) is True

    def test_joined_before_1_july_false_for_july_1_birth_in_filing_year(self) -> None:
        d = DescendantInfo(birth_date=date(2024, 7, 1))
        assert d.joined_before_or_on_1_july(2024) is False

    def test_adopted_before_1_july_uses_adoption_date(self) -> None:
        d = DescendantInfo(birth_date=date(2020, 1, 1), adoption_date=date(2024, 5, 12))
        assert d.joined_before_or_on_1_july(2024) is True

    def test_adopted_on_1_july_is_not_full_year(self) -> None:
        d = DescendantInfo(birth_date=date(2020, 1, 1), adoption_date=date(2024, 7, 1))
        assert d.joined_before_or_on_1_july(2024) is False


# ---------------------------------------------------------------------------
# RentaFamilyProfile derived properties
# ---------------------------------------------------------------------------


class TestRentaFamilyProfileDerivedProperties:
    def test_descendientes_count_empty(self) -> None:
        p = RentaFamilyProfile()
        assert p.descendientes_count == 0

    def test_descendientes_count_matches_tuple_length(self) -> None:
        p = RentaFamilyProfile(
            descendientes=(
                DescendantInfo(birth_date=date(2018, 6, 1)),
                DescendantInfo(birth_date=date(2021, 3, 15)),
            ),
        )
        assert p.descendientes_count == 2

    def test_descendientes_menores_3_count(self) -> None:
        p = RentaFamilyProfile(
            descendientes=(
                DescendantInfo(birth_date=date(2023, 1, 15)),  # age 1 at year-end 2024
                DescendantInfo(birth_date=date(2019, 6, 1)),  # age 5 at year-end 2024
            ),
        )
        assert p.descendientes_menores_3_year_end(2024) == 1

    def test_descendientes_eligible_minimum_count(self) -> None:
        p = RentaFamilyProfile(
            descendientes=(
                DescendantInfo(birth_date=date(2000, 1, 1)),  # age 24, eligible
                DescendantInfo(birth_date=date(1999, 1, 1)),  # age 25, not eligible
                DescendantInfo(birth_date=date(1990, 1, 1), discapacidad_grado=33),  # disabled, eligible
            ),
        )
        assert p.descendientes_eligible_minimum(2024) == 2

    def test_descendientes_full_year_minimum_count(self) -> None:
        p = RentaFamilyProfile(
            descendientes=(
                DescendantInfo(birth_date=date(2023, 1, 15)),  # before 1-July, full year
                DescendantInfo(birth_date=date(2024, 9, 1)),  # after 1-July, half year
            ),
        )
        assert p.descendientes_full_year_minimum(2024) == 1


# ---------------------------------------------------------------------------
# Oracle tests — Art. 58.1 mínimo por descendientes (registry-authoritative)
# ---------------------------------------------------------------------------


def _minimo_descendientes_estatal(descendientes: tuple[DescendantInfo, ...], filing_year: int) -> Decimal:
    """Compute Art. 58.1 mínimo aggregate for casilla 0513 (part estatal).

    Uses the registry-authoritative amounts from the 2024 AEAT parameters.
    Full-year and half-year prorrata per Art. 58.4 LIRPF.
    """
    amounts = [_MINIMO_1, _MINIMO_2, _MINIMO_3]

    eligible = [d for d in descendientes if d.is_eligible_ordinary(filing_year)]
    total = Decimal("0")
    for rank, d in enumerate(eligible):
        amount = amounts[rank] if rank < len(amounts) else _MINIMO_4PLUS
        if d.joined_before_or_on_1_july(filing_year):
            total += amount
        else:
            total += amount * Decimal("0.5")
    return total


def _minimo_menor_tres_estatal(descendientes: tuple[DescendantInfo, ...], filing_year: int) -> Decimal:
    """Compute Art. 58.3 bajo-3-años supplement for casilla (part estatal).

    Registry amount for each qualifying descendant.
    """
    total = Decimal("0")
    for d in descendientes:
        if d.is_eligible_menor_tres(filing_year):
            if d.joined_before_or_on_1_july(filing_year):
                total += _MENOR_TRES
            else:
                total += _MENOR_TRES * Decimal("0.5")
    return total


class TestArt58OracleCases:
    def test_oracle_1_descendiente_born_2023_jan_15(self) -> None:
        """1 descendiente born 2023-01-15 (age 1 at 2024 year-end).

        Registry amounts: mínimo 1er hijo €2,400 + menor-3-años €3,000 = €5,400.
        (The spec says €5,200 using €2,800 for menor-3, but the 2024 registry
        declares €3,000; the registry is authoritative per project rules.)
        """
        d = DescendantInfo(birth_date=date(2023, 1, 15))
        descendientes = (d,)
        minimo = _minimo_descendientes_estatal(descendientes, 2024)
        menor3 = _minimo_menor_tres_estatal(descendientes, 2024)
        assert minimo == _MINIMO_1  # €2,400
        assert menor3 == _MENOR_TRES  # €3,000
        assert minimo + menor3 == Decimal("5400")

    def test_oracle_2_descendientes_both_born_pre_2024(self) -> None:
        """2 descendientes, both born before 2024.

        Registry amounts: €2,400 + €2,700 = €5,100 total mínimo estatal.
        """
        d1 = DescendantInfo(birth_date=date(2018, 5, 1))
        d2 = DescendantInfo(birth_date=date(2020, 8, 10))
        minimo = _minimo_descendientes_estatal((d1, d2), 2024)
        assert minimo == _MINIMO_1 + _MINIMO_2  # €5,100

    def test_oracle_ines_shape_adopted_2024_05_12(self) -> None:
        """Inés shape: 1 descendant adopted 2024-05-12 (before 1 July → full year).

        Registry amounts: mínimo 1er hijo €2,400 (full year).
        The descendant born in 2022 → age 2 at year-end 2024 → qualifies for menor-3.
        Menor-3 supplement: €3,000 (full year via adoption before 1 July).
        Total: €2,400 + €3,000 = €5,400.
        """
        d = DescendantInfo(birth_date=date(2022, 3, 1), adoption_date=date(2024, 5, 12))
        descendientes = (d,)
        minimo = _minimo_descendientes_estatal(descendientes, 2024)
        menor3 = _minimo_menor_tres_estatal(descendientes, 2024)
        assert d.joined_before_or_on_1_july(2024) is True
        assert d.is_eligible_menor_tres(2024) is True
        assert minimo == _MINIMO_1  # €2,400
        assert menor3 == _MENOR_TRES  # €3,000
        assert minimo + menor3 == Decimal("5400")

    def test_oracle_half_year_prorrata_july_birth(self) -> None:
        """Descendant born 2024-07-01 → after 1-July → 50% prorrata."""
        d = DescendantInfo(birth_date=date(2024, 7, 1))
        minimo = _minimo_descendientes_estatal((d,), 2024)
        # 50% of €2,400 = €1,200
        assert minimo == _MINIMO_1 * Decimal("0.5")


# ---------------------------------------------------------------------------
# Roundtrip test for DescendantInfo serialisation via facts
# ---------------------------------------------------------------------------


class TestDescendantFactsRoundtrip:
    def test_two_descendientes_roundtrip_via_facts(self) -> None:
        """Save 2 DescendantInfo → flat facts → reload → assert equality."""
        d1 = DescendantInfo(
            birth_date=date(2020, 3, 15),
            discapacidad_grado=33,
            nif="TAXIDABCD",
        )
        d2 = DescendantInfo(
            birth_date=date(2022, 11, 5),
            adoption_date=date(2023, 4, 1),
            convive_con_contribuyente=True,
        )
        original = (d1, d2)
        facts = descendant_facts_from_list(original)
        fact_dict = dict(facts)
        reloaded = descendant_list_from_facts(fact_dict)
        assert reloaded == original

    def test_anti_tautology_missing_birth_date_drops_entry(self) -> None:
        """Anti-tautology: removing birth_date from facts → entry is silently dropped on reload.

        The contract is: an entry without birth_date cannot be reconstructed;
        the reload skips it. This proves the roundtrip does not silently accept
        corrupted data and reconstruct a wrong DescendantInfo.
        """
        d = DescendantInfo(birth_date=date(2020, 6, 1))
        facts = dict(descendant_facts_from_list((d,)))
        facts.pop("renta_family.descendiente.0.birth_date")
        reloaded = descendant_list_from_facts(facts)
        assert len(reloaded) == 0

    def test_count_fact_is_stored(self) -> None:
        d = DescendantInfo(birth_date=date(2018, 1, 1))
        facts = dict(descendant_facts_from_list((d,)))
        assert facts["renta_family.descendientes_count"] == "1"


# ---------------------------------------------------------------------------
# parse_descendiente_flag
# ---------------------------------------------------------------------------


class TestParseDescendienteFlag:
    def test_nacimiento_only(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2020-03-15")
        assert d.birth_date == date(2020, 3, 15)
        assert d.adoption_date is None
        assert d.convive_con_contribuyente is True
        assert d.discapacidad_grado is None

    def test_full_flag(self) -> None:
        d = parse_descendiente_flag(
            "NACIMIENTO=2020-03-15,ADOPCION=2024-05-12,DISCAPACIDAD=33,CONVIVENCIA=false,NIF=TAXIDABCD",
        )
        assert d.birth_date == date(2020, 3, 15)
        assert d.adoption_date == date(2024, 5, 12)
        assert d.discapacidad_grado == 33
        assert d.convive_con_contribuyente is False
        assert d.nif == "TAXIDABCD"

    def test_missing_nacimiento_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="NACIMIENTO"):
            parse_descendiente_flag("ADOPCION=2024-05-12")

    def test_invalid_discapacidad_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="DISCAPACIDAD"):
            parse_descendiente_flag("NACIMIENTO=2020-01-01,DISCAPACIDAD=50")

    def test_case_insensitive_keys(self) -> None:
        d = parse_descendiente_flag("nacimiento=2020-03-15")
        assert d.birth_date == date(2020, 3, 15)
