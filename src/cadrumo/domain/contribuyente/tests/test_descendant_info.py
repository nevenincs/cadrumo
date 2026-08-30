"""Tests for DescendantInfo, derived properties, and Art. 58 mínimo oracle.

Oracle values come from the AEAT Modelo 100 2024 official parameters:
  - primer hijo:             €2,400  (renta-2024-minimo-descendientes-primer-hijo-2024)
  - segundo hijo:            €2,700  (renta-2024-minimo-descendientes-segundo-hijo-2024)
  - tercer hijo:             €4,000  (renta-2024-minimo-descendientes-tercer-hijo-2024)
  - cuarto y siguientes:     €4,500  (renta-2024-minimo-descendientes-cuarto-y-siguientes-2024)
  - menor de 3 años:         €2,800  (renta-2024-minimo-descendientes-menor-tres-anos-2024)

The registry parameters are the authoritative source; oracle test expected
values are derived from those registry-declared amounts, NOT from the formula
under test.

The spec's €2,800 for the bajo-3-años supplement differs from the registry
€2,800 — the registry is authoritative; this test suite uses €2,800.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import DescendantRelacion
from ..descendant import DescendantInfo
from ..descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)
from ..family_profile import RentaFamilyProfile
from ._registry_thresholds import (
    registry_birth_order_amounts,
    registry_fallecimiento_amount,
    registry_menor_tres_supplement,
    registry_thresholds,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

FILING_YEAR = 2024

# Art. 58 figures for the exercised filing year, read from the registry rather
# than restated: a literal here would decouple these cases from the parameters
# the engine actually resolves (`aeat-registry-authority-flow`).
_MINIMO_1, _MINIMO_2, _MINIMO_3, _MINIMO_4PLUS = registry_birth_order_amounts(FILING_YEAR)
_MENOR_TRES = registry_menor_tres_supplement(FILING_YEAR)
_FALLECIMIENTO = registry_fallecimiento_amount(FILING_YEAR)

_ART58_ORACLE_CASES: tuple[tuple[str, tuple[DescendantInfo, ...], Decimal], ...] = (
    (
        "one-descendant-born-2023-jan-15",
        (DescendantInfo(birth_date=date(2023, 1, 15)),),
        Decimal("5200"),
    ),
    (
        "two-descendants-both-born-pre-2024",
        (DescendantInfo(birth_date=date(2018, 5, 1)), DescendantInfo(birth_date=date(2020, 8, 10))),
        _MINIMO_1 + _MINIMO_2,
    ),
    (
        "ines-shape-adopted-2024-05-12",
        (
            DescendantInfo(
                birth_date=date(2022, 3, 1),
                relacion=DescendantRelacion.ADOPTADO,
                inscripcion_registro_civil_date=date(2024, 5, 12),
            ),
        ),
        Decimal("5200"),
    ),
    (
        "late-year-birth-full-annual-amount",
        (DescendantInfo(birth_date=date(2024, 7, 1)),),
        _MINIMO_1 + _MENOR_TRES,
    ),
    (
        "birth-order-ranks-by-birth-date",
        (DescendantInfo(birth_date=date(2020, 1, 1)), DescendantInfo(birth_date=date(2010, 1, 1))),
        _MINIMO_1 + _MINIMO_2,
    ),
    (
        "four-descendants-uses-cuarto-y-siguientes",
        tuple(DescendantInfo(birth_date=date(y, 1, 1)) for y in (2005, 2008, 2011, 2014)),
        _MINIMO_1 + _MINIMO_2 + _MINIMO_3 + _MINIMO_4PLUS,
    ),
    (
        "fifth-descendant-repeats-cuarto-y-siguientes",
        tuple(DescendantInfo(birth_date=date(y, 1, 1)) for y in (2005, 2008, 2011, 2014, 2016)),
        _MINIMO_1 + _MINIMO_2 + _MINIMO_3 + _MINIMO_4PLUS + _MINIMO_4PLUS,
    ),
    ("no-eligible-descendant-is-zero", (), Decimal("0")),
    (
        "custodia-compartida-halves-descendant-contribution",
        (DescendantInfo(birth_date=date(2015, 1, 1), custodia_compartida=True),),
        _MINIMO_1 * Decimal("0.5"),
    ),
    (
        "custodia-compartida-after-menor-tres-stacking",
        (DescendantInfo(birth_date=date(2023, 1, 15), custodia_compartida=True),),
        (_MINIMO_1 + _MENOR_TRES) * Decimal("0.5"),
    ),
)


_THRESHOLDS = registry_thresholds(FILING_YEAR)


def _minimo_descendientes_estatal(profile: RentaFamilyProfile) -> Decimal:
    return profile.minimo_descendientes_estatal(
        2024,
        birth_order_amounts=[_MINIMO_1, _MINIMO_2, _MINIMO_3, _MINIMO_4PLUS],
        menor_tres_supplement=_MENOR_TRES,
        fallecimiento_amount=_FALLECIMIENTO,
        thresholds=_THRESHOLDS,
    )


# ---------------------------------------------------------------------------
# DescendantInfo model validation
# ---------------------------------------------------------------------------


class TestDescendantInfoValidation:
    def test_requires_birth_date(self) -> None:
        # NEGATIVE TEST: deliberately validate without required birth_date.
        with pytest.raises(ValidationError):
            DescendantInfo.model_validate({})

    def test_birth_date_from_iso_string(self) -> None:
        d = DescendantInfo.model_validate({"birth_date": "2020-03-15"})
        assert d.birth_date == date(2020, 3, 15)

    def test_inscripcion_date_must_be_gte_birth_date(self) -> None:
        with pytest.raises((ValidationError, ValueError), match="inscripcion_registro_civil_date"):
            DescendantInfo(
                birth_date=date(2020, 6, 1),
                relacion=DescendantRelacion.ADOPTADO,
                inscripcion_registro_civil_date=date(2020, 5, 31),
            )

    def test_acogimiento_date_must_be_gte_birth_date(self) -> None:
        with pytest.raises((ValidationError, ValueError), match="acogimiento_resolucion_date"):
            DescendantInfo(
                birth_date=date(2020, 6, 1),
                relacion=DescendantRelacion.ACOGIMIENTO_PREADOPTIVO_O_PERMANENTE,
                acogimiento_resolucion_date=date(2020, 5, 31),
            )

    def test_inscripcion_date_equal_to_birth_date_is_accepted(self) -> None:
        d = DescendantInfo(
            birth_date=date(2020, 6, 1),
            relacion=DescendantRelacion.ADOPTADO,
            inscripcion_registro_civil_date=date(2020, 6, 1),
        )
        assert d.inscripcion_registro_civil_date == date(2020, 6, 1)

    def test_entry_dates_in_future_are_rejected(self) -> None:
        with pytest.raises((ValidationError, ValueError), match="future"):
            DescendantInfo(
                birth_date=date(2000, 1, 1),
                relacion=DescendantRelacion.ADOPTADO,
                inscripcion_registro_civil_date=date(2099, 1, 1),
            )
        with pytest.raises((ValidationError, ValueError), match="future"):
            DescendantInfo(
                birth_date=date(2000, 1, 1),
                relacion=DescendantRelacion.ACOGIMIENTO_PREADOPTIVO_O_PERMANENTE,
                acogimiento_resolucion_date=date(2099, 1, 1),
            )

    def test_discapacidad_grado_accepts_0_33_65(self) -> None:
        for grade in (0, 33, 65):
            d = DescendantInfo(birth_date=date(2010, 1, 1), discapacidad_grado=grade)
            assert d.discapacidad_grado == grade

    def test_discapacidad_grado_rejects_invalid_value(self) -> None:
        # NEGATIVE TEST: deliberately invalid grado.
        with pytest.raises(ValidationError):
            DescendantInfo.model_validate({"birth_date": date(2010, 1, 1), "discapacidad_grado": 50})

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

    def test_is_eligible_ordinary_age_boundary(self) -> None:
        cases = ((date(2000, 1, 1), True), (date(1999, 1, 1), False))
        for birth_date, expected in cases:
            d = DescendantInfo(birth_date=birth_date)
            assert d.is_eligible_ordinary(2024, thresholds=_THRESHOLDS) is expected, birth_date

    def test_is_eligible_ordinary_over_25_with_discapacidad_is_true(self) -> None:
        d = DescendantInfo(birth_date=date(1990, 1, 1), discapacidad_grado=33)
        assert d.is_eligible_ordinary(2024, thresholds=_THRESHOLDS) is True

    def test_is_eligible_ordinary_non_cohabiting_is_false(self) -> None:
        d = DescendantInfo(birth_date=date(2020, 1, 1), convive_con_contribuyente=False)
        assert d.is_eligible_ordinary(2024, thresholds=_THRESHOLDS) is False

    def test_is_eligible_menor_tres_age_1_is_true(self) -> None:
        d = DescendantInfo(birth_date=date(2023, 1, 15))
        assert d.is_eligible_menor_tres(2024) is True

    def test_is_eligible_menor_tres_age_3_is_false(self) -> None:
        d = DescendantInfo(birth_date=date(2021, 12, 31))
        assert d.is_eligible_menor_tres(2024) is False


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
        assert p.descendientes_eligible_minimum(2024, thresholds=_THRESHOLDS) == 2


# ---------------------------------------------------------------------------
# Oracle tests — Art. 58/61 mínimo por descendientes engine (registry-authoritative)
#
# The Art. 58.4 grounding is resolved:
# no within-year birth/adoption temporal prorrateo exists in the LIRPF for
# descendientes (Art. 58 has only the two numbered subsections above; Art. 61's
# temporal rules cover only a mid-year death (norma 4a, unrelated to entry
# timing) and ascendientes' half-period residency (norma 5a, scoped away from
# descendientes)). These oracle cases therefore assert the FULL annual
# birth-order amount regardless of the descendant's entry date within the
# year, exercised via RentaFamilyProfile.minimo_descendientes_estatal — the
# production method the registry binding calls, not a re-derived local helper.
# ---------------------------------------------------------------------------


class TestArt58MinimoDescendientesEstatalOracleCases:
    def test_oracle_cases(self) -> None:
        failures: list[str] = []
        for case_id, descendientes, expected in _ART58_ORACLE_CASES:
            profile = RentaFamilyProfile(descendientes=descendientes)
            total = _minimo_descendientes_estatal(profile)
            if total != expected:
                failures.append(f"{case_id}: expected {expected}, got {total}")

        assert not failures, "\n".join(failures)

    def test_empty_birth_order_amounts_is_rejected(self) -> None:
        p = RentaFamilyProfile(descendientes=(DescendantInfo(birth_date=date(2015, 1, 1)),))
        with pytest.raises(ValueError, match="birth_order_amounts"):
            p.minimo_descendientes_estatal(
                2024,
                birth_order_amounts=[],
                menor_tres_supplement=_MENOR_TRES,
                fallecimiento_amount=_FALLECIMIENTO,
                thresholds=_THRESHOLDS,
            )


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
            relacion=DescendantRelacion.ADOPTADO,
            inscripcion_registro_civil_date=date(2023, 4, 1),
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
        assert d.relacion is DescendantRelacion.DESCENDIENTE
        assert d.inscripcion_registro_civil_date is None
        assert d.acogimiento_resolucion_date is None
        assert d.convive_con_contribuyente is True
        assert d.discapacidad_grado is None

    def test_full_flag(self) -> None:
        d = parse_descendiente_flag(
            "NACIMIENTO=2020-03-15,RELACION=adoptado,INSCRIPCION=2024-05-12,"
            "ACOGIMIENTO=2022-01-10,DISCAPACIDAD=33,CONVIVENCIA=false,NIF=TAXIDABCD",
        )
        assert d.birth_date == date(2020, 3, 15)
        assert d.relacion is DescendantRelacion.ADOPTADO
        assert d.inscripcion_registro_civil_date == date(2024, 5, 12)
        assert d.acogimiento_resolucion_date == date(2022, 1, 10)
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

    @pytest.mark.parametrize(
        ("spelling", "expected"),
        (
            pytest.param("sí", True, id="si-accented"),
            pytest.param("si", True, id="si-bare"),
            pytest.param("s", True, id="s-abbreviated"),
            pytest.param("verdadero", True, id="verdadero"),
            pytest.param("no", False, id="no"),
            pytest.param("n", False, id="n-abbreviated"),
            pytest.param("falso", False, id="falso"),
        ),
    )
    def test_convivencia_reads_the_spanish_a_taxpayer_actually_writes(
        self,
        spelling: str,
        expected: bool,
    ) -> None:
        """Every spelling the canonical vocabulary accepts reads the same way here."""
        d = parse_descendiente_flag(f"NACIMIENTO=2020-03-15,CONVIVENCIA={spelling}")

        assert d.convive_con_contribuyente is expected

    @pytest.mark.parametrize("key", ("CONVIVENCIA", "CUSTODIA"))
    def test_an_unreadable_yes_no_refuses_rather_than_claiming(self, key: str) -> None:
        """A word the vocabulary cannot read must not resolve to a deduction.

        Both fields used to answer silently, and both answered in the
        direction that claims: ``CONVIVENCIA`` resolved an unreadable word to
        ``True`` (Art. 58 cohabitation, which qualifies the descendant at
        all), while ``CUSTODIA`` resolved it to ``False`` (the full mínimo
        rather than the Art. 61 half). Opposite booleans, same direction.
        """
        with pytest.raises(ValueError, match=key):
            parse_descendiente_flag(f"NACIMIENTO=2020-03-15,{key}=quizas")

    def test_the_yes_no_refusal_lists_the_spellings_it_accepts(self) -> None:
        """The refusal has to teach the vocabulary, not just reject the word."""
        with pytest.raises(ValueError) as caught:
            parse_descendiente_flag("NACIMIENTO=2020-03-15,CONVIVENCIA=quizas")

        message = str(caught.value)
        assert "sí" in message and "no" in message, "must name the Spanish spellings"
        assert "quizas" in message, "must echo what the operator wrote"

    def test_an_absent_yes_no_still_takes_its_documented_default(self) -> None:
        """Refusing an unreadable VALUE must not start refusing an absent one.

        The two defaults are the flag's published contract and point opposite
        ways, so a guard that collapsed absence into the refusal would break
        every short-form invocation.
        """
        d = parse_descendiente_flag("NACIMIENTO=2020-03-15")

        assert d.convive_con_contribuyente is True
        assert d.custodia_compartida is False
