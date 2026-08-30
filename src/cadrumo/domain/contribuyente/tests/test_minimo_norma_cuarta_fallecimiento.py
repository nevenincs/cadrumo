"""Art. 61 norma 4ª LIRPF: the death-in-period flat cuantía AND the ordering exclusion.

The rule has two limbs and each over-grants on its own when omitted, so every
case here is chosen to DISCRIMINATE between three implementations: neither limb,
limb one only, and both. A test that only checked the deceased's own amount
would pass against a limb-one-only fix, which is the half-fix this module exists
to prevent — 2.400 € is simultaneously the norma 4ª flat figure and the Art. 58.1
first-child tranche, so a partial implementation looks complete.

Expected totals are the AEAT Renta manual's PRINTED euro figures added by hand,
never values read back from the aggregate under test. ``test_registry_figures_are_the_manual_figures``
pins the registry parameters to those same printed figures, so a literal below
cannot quietly stop meaning what the manual says.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..descendant import DescendantInfo
from ..family_profile import RentaFamilyProfile
from ._registry_thresholds import (
    registry_birth_order_amounts,
    registry_fallecimiento_amount,
    registry_menor_tres_supplement,
    registry_thresholds,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

FILING_YEAR = 2024

#: The figures the bundled AEAT Renta manual prints under "Mínimo por
#: descendientes / Cuantías aplicables", transcribed once here so the expected
#: totals below can be read as the manual's own arithmetic.
_MANUAL_PRIMERO = Decimal("2400")
_MANUAL_SEGUNDO = Decimal("2700")
_MANUAL_TERCERO = Decimal("4000")
_MANUAL_MENOR_TRES = Decimal("2800")
#: "En caso de fallecimiento de un descendiente que genere derecho al mínimo por
#: este concepto, la cuantía aplicable es de 2.400 euros." Equal to the first
#: tranche by coincidence, not by derivation — kept as its own name for exactly
#: that reason.
_MANUAL_FALLECIMIENTO = Decimal("2400")

_THRESHOLDS = registry_thresholds(FILING_YEAR)


def _total(*descendientes: DescendantInfo) -> Decimal:
    """Run the aggregate exactly as the calculate path does, on registry figures."""
    primero, segundo, tercero, cuarto = registry_birth_order_amounts(FILING_YEAR)
    return RentaFamilyProfile(descendientes=descendientes).minimo_descendientes_estatal(
        FILING_YEAR,
        birth_order_amounts=[primero, segundo, tercero, cuarto],
        menor_tres_supplement=registry_menor_tres_supplement(FILING_YEAR),
        fallecimiento_amount=registry_fallecimiento_amount(FILING_YEAR),
        thresholds=_THRESHOLDS,
    )


def test_registry_figures_are_the_manual_figures() -> None:
    """The registry parameters carry the manual's printed euros.

    Guards every hand-computed expectation in this module: if a parameter is
    ever re-authored, the literals below stop being the manual's arithmetic and
    this fails first, naming the drift, instead of the totals failing obscurely.
    """
    primero, segundo, tercero, _cuarto = registry_birth_order_amounts(FILING_YEAR)
    assert primero == _MANUAL_PRIMERO
    assert segundo == _MANUAL_SEGUNDO
    assert tercero == _MANUAL_TERCERO
    assert registry_menor_tres_supplement(FILING_YEAR) == _MANUAL_MENOR_TRES
    assert registry_fallecimiento_amount(FILING_YEAR) == _MANUAL_FALLECIMIENTO


class TestLimbOneFlatCuantia:
    """The deceased takes the flat figure instead of their birth-order tranche."""

    def test_second_child_dying_takes_the_flat_figure_not_the_second_tranche(self) -> None:
        """A dying SECOND child is where limb one first becomes visible.

        Manual arithmetic: the survivor is "el primero" at 2.400, and the
        deceased takes the norma 4ª 2.400 rather than the 2.700 their rank
        would otherwise carry. Total 4.800.

        Omitting limb one yields 2.400 + 2.700 = 5.100, so this case fails
        against an implementation that ranks the deceased normally.
        """
        total = _total(
            DescendantInfo(birth_date=date(2010, 1, 1)),
            DescendantInfo(birth_date=date(2012, 1, 1), death_date=date(FILING_YEAR, 6, 15)),
        )
        assert total == _MANUAL_PRIMERO + _MANUAL_FALLECIMIENTO
        assert total == Decimal("4800")

    def test_only_child_dying_is_unchanged_because_the_figures_coincide(self) -> None:
        """A dying ONLY child is deliberately a no-op, and that is the trap.

        2.400 flat and 2.400 first-tranche agree, so this case cannot detect
        limb one at all. It is asserted anyway to record that the coincidence is
        understood rather than undiscovered: an implementation reviewed only
        against a single-child household would look correct while being wrong
        for every larger one.
        """
        assert _total(DescendantInfo(birth_date=date(2010, 1, 1), death_date=date(FILING_YEAR, 6, 15))) == Decimal(
            "2400",
        )


class TestLimbTwoOrderingExclusion:
    """The deceased vacates their rank, moving every younger sibling down a tranche."""

    def test_middle_child_dying_moves_the_younger_sibling_to_a_cheaper_rank(self) -> None:
        """The load-bearing case: it separates all three implementations.

        Three cohabiting children, the MIDDLE one dies in June. The manual's
        arithmetic: the deceased is not counted in the ordering, so the eldest
        is "el primero" (2.400) and the youngest becomes "el segundo" (2.700)
        rather than "el tercero"; the deceased takes the flat 2.400.
        Total 7.500.

        The two wrong answers are both 9.100 — with neither limb
        (2.400 + 2.700 + 4.000) and, coincidentally, with limb one alone
        (2.400 flat + 2.400 + 4.000). The youngest sitting at 4.000 instead of
        2.700 is the survivors' half of the over-grant, and it is invisible
        unless a test ranks a sibling BELOW the deceased.
        """
        total = _total(
            DescendantInfo(birth_date=date(2010, 1, 1)),
            DescendantInfo(birth_date=date(2012, 1, 1), death_date=date(FILING_YEAR, 6, 1)),
            DescendantInfo(birth_date=date(2014, 1, 1)),
        )
        assert total == Decimal("7500")
        assert total != Decimal("9100"), "survivors kept ranks the deceased should have vacated"

    def test_eldest_dying_moves_both_survivors_down_a_rank(self) -> None:
        """Eldest dies: the remaining two become primero and segundo.

        Manual arithmetic: 2.400 flat for the deceased, then 2.400 + 2.700 for
        the survivors re-ranked. Total 7.500. Without limb two the survivors
        stay at 2.700 + 4.000, giving 9.100.
        """
        total = _total(
            DescendantInfo(birth_date=date(2010, 1, 1), death_date=date(FILING_YEAR, 3, 20)),
            DescendantInfo(birth_date=date(2012, 1, 1)),
            DescendantInfo(birth_date=date(2014, 1, 1)),
        )
        assert total == _MANUAL_FALLECIMIENTO + _MANUAL_PRIMERO + _MANUAL_SEGUNDO
        assert total == Decimal("7500")

    def test_the_two_limbs_are_independently_necessary(self) -> None:
        """Neither limb alone reproduces the manual's total for the middle-child case.

        Recomputes the same household under each partial reading from the
        manual's printed figures, and asserts both differ from the correct
        answer. This is the guard against a future 'simplification' that
        collapses the two limbs into one condition.
        """
        both_limbs = Decimal("7500")
        neither_limb = _MANUAL_PRIMERO + _MANUAL_SEGUNDO + _MANUAL_TERCERO
        limb_one_only = _MANUAL_FALLECIMIENTO + _MANUAL_PRIMERO + _MANUAL_TERCERO
        assert neither_limb != both_limbs
        assert limb_one_only != both_limbs
        assert (
            _total(
                DescendantInfo(birth_date=date(2010, 1, 1)),
                DescendantInfo(birth_date=date(2012, 1, 1), death_date=date(FILING_YEAR, 6, 1)),
                DescendantInfo(birth_date=date(2014, 1, 1)),
            )
            == both_limbs
        )


class TestDevengoBoundary:
    """The limbs are scoped differently, and a 31-December death is where that shows."""

    def test_death_on_the_devengo_date_takes_the_flat_figure_but_keeps_its_rank(self) -> None:
        """Only the ordering limb is conditioned on preceding the devengo.

        The statute grants the flat cuantía on any "fallecimiento ... en el
        ejercicio", while the manual excludes from the ordering only those who
        died "con anterioridad a la fecha de devengo". A death ON 31 December is
        therefore inside the first and outside the second, so the youngest child
        stays "el tercero" at 4.000.

        Manual arithmetic: 2.400 + 2.400 flat + 4.000 = 8.800 — distinct from
        both the 30-December answer (7.500) and the no-death answer (9.100), so
        this case cannot be satisfied by collapsing the two conditions either way.
        """
        total = _total(
            DescendantInfo(birth_date=date(2010, 1, 1)),
            DescendantInfo(birth_date=date(2012, 1, 1), death_date=date(FILING_YEAR, 12, 31)),
            DescendantInfo(birth_date=date(2014, 1, 1)),
        )
        assert total == Decimal("8800")

    def test_death_one_day_before_the_devengo_excludes_from_the_ordering(self) -> None:
        """30 December is inside both limbs; the pair pins the boundary to the exact day."""
        total = _total(
            DescendantInfo(birth_date=date(2010, 1, 1)),
            DescendantInfo(birth_date=date(2012, 1, 1), death_date=date(FILING_YEAR, 12, 30)),
            DescendantInfo(birth_date=date(2014, 1, 1)),
        )
        assert total == Decimal("7500")


class TestMenorTresSupplementSurvivesDeath:
    """The flat cuantía replaces the tranche, never the Art. 58.2 increase."""

    def test_supplement_is_added_on_top_of_the_flat_figure(self) -> None:
        """The manual grants the under-three increase to a child who died in the period.

        "el incremento por descendientes menores de tres años resulta aplicable
        en los casos en que el descendiente haya fallecido durante el período
        impositivo". Manual arithmetic: 2.400 flat + 2.800 = 5.200.

        Reading the flat figure as the whole entitlement would yield 2.400 and
        UNDER-grant a bereaved filer — the opposite error to the one the rest of
        this module guards, and just as wrong.
        """
        total = _total(DescendantInfo(birth_date=date(2023, 5, 1), death_date=date(FILING_YEAR, 8, 1)))
        assert total == _MANUAL_FALLECIMIENTO + _MANUAL_MENOR_TRES
        assert total == Decimal("5200")


class TestDeathOutsideThePeriod:
    """A death in another year is not this period's norma 4ª case."""

    def test_death_in_a_prior_year_contributes_nothing(self) -> None:
        """A child who died before this period generates no mínimo at all.

        ``birth_date`` alone keeps satisfying "under 25 at year-end" for years
        after a death, so without an explicit gate a bereaved filer would go on
        claiming for a child who died long ago. The surviving sibling is then
        "el primero" at 2.400.
        """
        total = _total(
            DescendantInfo(birth_date=date(2010, 1, 1), death_date=date(FILING_YEAR - 1, 4, 4)),
            DescendantInfo(birth_date=date(2012, 1, 1)),
        )
        assert total == _MANUAL_PRIMERO

    def test_death_in_a_later_year_is_an_ordinary_living_descendant(self) -> None:
        """Profiles are effective-dated, so a later death must not reach back.

        Filing 2024 for a child who dies in 2025 is the ordinary two-child case:
        2.400 + 2.700.
        """
        total = _total(
            DescendantInfo(birth_date=date(2010, 1, 1)),
            DescendantInfo(birth_date=date(2012, 1, 1), death_date=date(FILING_YEAR + 1, 2, 2)),
        )
        assert total == _MANUAL_PRIMERO + _MANUAL_SEGUNDO


class TestDeathInteractionWithProrrata:
    """Art. 61 norma 1ª still halves a shared deceased descendant's flat cuantía."""

    def test_custodia_compartida_halves_the_flat_figure(self) -> None:
        """The prorrata multiplies whatever the norma 4ª limb produced.

        Manual arithmetic: 2.400 flat × 0,5 = 1.200 for the shared deceased
        child, plus 2.400 for the sole-custody survivor who is "el primero"
        once the deceased vacates the ordering. Total 3.600.
        """
        total = _total(
            DescendantInfo(birth_date=date(2010, 1, 1)),
            DescendantInfo(
                birth_date=date(2012, 1, 1),
                death_date=date(FILING_YEAR, 6, 1),
                custodia_compartida=True,
            ),
        )
        assert total == _MANUAL_PRIMERO + (_MANUAL_FALLECIMIENTO * Decimal("0.5"))
        assert total == Decimal("3600")


class TestDeathDateRecordValidation:
    def test_death_before_birth_is_refused(self) -> None:
        with pytest.raises(ValueError, match="precedes birth_date"):
            DescendantInfo(birth_date=date(2012, 1, 1), death_date=date(2010, 1, 1))

    def test_twins_are_ranked_separately_when_one_dies(self) -> None:
        """Identically-declared siblings must not collapse onto one rank.

        ``DescendantInfo`` is a frozen model, so twins with the same birth date
        and no distinguishing fact compare EQUAL. A rank lookup keyed by the
        record rather than by position would give the survivor the deceased's
        index. Manual arithmetic: the deceased twin takes 2.400 flat and the
        surviving twin is "el primero" at 2.400. Total 4.800.
        """
        total = _total(
            DescendantInfo(birth_date=date(2012, 1, 1)),
            DescendantInfo(birth_date=date(2012, 1, 1), death_date=date(FILING_YEAR, 6, 1)),
        )
        assert total == Decimal("4800")
