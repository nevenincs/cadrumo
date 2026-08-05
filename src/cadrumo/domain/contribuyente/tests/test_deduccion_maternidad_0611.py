"""What survives around the Art. 81 LIRPF deducción maternidad (casilla 0611).

Covers the live arithmetic, the persistence boundary and the flag: the oracle and
anti-tautology cases for ``compute_deduccion_maternidad_0611``, the roundtrip of
``meses_madre_trabajo_2024`` through the fact index, and what the
``--descendiente`` flag accepts.

Art. 81 LIRPF: ``sum(min(meses_trabajados × 100, 1_200))`` per eligible hijo.
Oracle anchoring: two hijos at twelve months each gives 1200 + 1200 = 2400; at
six and twelve, 600 + 1200 = 1800. Anti-tautology: moving meses from zero to six
must move the result from 0 to 600.

A duplicate of that oracle used to run against a profile METHOD that recomputed
the same formula and had no production consumer. The method was retired and its
cases went with it, keeping the ones above, which drive the function the
calculate path actually calls.

Two of the retired cases asserted ELIGIBILITY -- that a child over three, or one
not cohabiting, contributes nothing. They had no counterpart to run against while
the live path consumed an operator-supplied list of (hijo, meses) pairs and
performed no filtering of its own. It now reads the descendant records instead,
and the child-side condition is the engine's: the authority grants the deduction
"por cada hijo hasta que el menor alcance los tres anos de edad" to women "que
tengan derecho a la aplicacion del minimo por descendientes". So those cases are
restored below against
:meth:`~domain.contribuyente.DescendantInfo.maternidad_contributing_meses`, which
is where that filtering now lives.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core import DescendantRelacion
from .._descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)
from ..family import DescendantInfo, RentaFamilyProfile
from ._registry_thresholds import registry_thresholds

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The Art. 58.1 / Art. 61 norma 2a ceilings, read from the registry rather than
#: retyped, so a revision that moves either cannot leave this module asserting
#: against a stale figure while the engine uses the new one.
_THRESHOLDS = registry_thresholds(2024)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _hijo_menor_3(meses: int) -> DescendantInfo:
    """Child born 2022-06-01 → age 2 at 2024-12-31, eligible menor-3."""
    return DescendantInfo(
        birth_date=date(2022, 6, 1),
        meses_madre_trabajo_2024=meses,
    )


def _hijo_no_menor_3() -> DescendantInfo:
    """Child born 2020-01-01 → age 4 at 2024-12-31, NOT menor-3 eligible."""
    return DescendantInfo(
        birth_date=date(2020, 1, 1),
        meses_madre_trabajo_2024=12,
    )


# ---------------------------------------------------------------------------
# Roundtrip: meses_madre_trabajo stored and reloaded from facts
# ---------------------------------------------------------------------------


class TestMesesTornoFacts:
    """Verify meses_madre_trabajo_2024 survives descendant_facts roundtrip."""

    def test_roundtrip_meses_stored_and_reloaded(self) -> None:
        """Fact serialisation: meses=6 → stored as '6' → reloaded as 6."""
        original = _hijo_menor_3(6)
        facts = dict(descendant_facts_from_list((original,)))

        assert facts.get("renta_family.descendiente.0.meses_madre_trabajo") == "6"

        reloaded = descendant_list_from_facts(facts)
        assert len(reloaded) == 1
        assert reloaded[0].meses_madre_trabajo_2024 == 6

    def test_roundtrip_zero_meses_not_stored(self) -> None:
        """Fact serialisation: meses=0 is not stored (absent means 0)."""
        original = _hijo_menor_3(0)
        facts = dict(descendant_facts_from_list((original,)))

        assert "renta_family.descendiente.0.meses_madre_trabajo" not in facts

        reloaded = descendant_list_from_facts(facts)
        assert reloaded[0].meses_madre_trabajo_2024 == 0

    def test_roundtrip_preserves_other_fields(self) -> None:
        """Adding meses does not disturb other fields on roundtrip."""
        original = DescendantInfo(
            birth_date=date(2022, 6, 1),
            custodia_compartida=True,
            meses_madre_trabajo_2024=9,
        )
        facts = dict(descendant_facts_from_list((original,)))
        reloaded = descendant_list_from_facts(facts)
        assert reloaded[0] == original


# ---------------------------------------------------------------------------
# parse_descendiente_flag: MESES_TRABAJO= key acceptance
# ---------------------------------------------------------------------------


class TestParseDescendienteFlagMesesTrabajo:
    """parse_descendiente_flag must accept MESES_TRABAJO= and validate 0–12 range."""

    def test_meses_trabajo_parsed(self) -> None:
        cases = (
            ("twelve", "NACIMIENTO=2022-06-01,MESES_TRABAJO=12", 12),
            ("six", "NACIMIENTO=2022-06-01,MESES_TRABAJO=6", 6),
            ("zero", "NACIMIENTO=2022-06-01,MESES_TRABAJO=0", 0),
            ("absent", "NACIMIENTO=2022-06-01", 0),
        )
        for case_id, spec, expected in cases:
            d = parse_descendiente_flag(spec)
            assert d.meses_madre_trabajo_2024 == expected, case_id

    def test_meses_trabajo_out_of_range_raises(self) -> None:
        for case_id, spec in (
            ("above-range", "NACIMIENTO=2022-06-01,MESES_TRABAJO=13"),
            ("negative", "NACIMIENTO=2022-06-01,MESES_TRABAJO=-1"),
        ):
            try:
                with pytest.raises(ValueError, match="MESES_TRABAJO must be 0"):
                    parse_descendiente_flag(spec)
            except AssertionError as exc:
                raise AssertionError(f"out-of-range MESES_TRABAJO was accepted: {case_id}") from exc


# ---------------------------------------------------------------------------
# CLI helper functions
# ---------------------------------------------------------------------------


class TestCLIHelpers:
    """Unit tests for compute_deduccion_maternidad_0611 (domain arithmetic)."""

    def test_compute_oracle_examples(self) -> None:
        """Domain arithmetic matches the Art. 81 oracle examples."""
        from .._deduccion_maternidad import compute_deduccion_maternidad_0611

        cases = (
            ("two-hijos-full-year", [("0", 12), ("1", 12)], 2400),
            ("two-hijos-partial-and-full", [("0", 6), ("1", 12)], 1800),
            ("one-hijo-cap", [("laia", 12)], 1200),
            ("zero-months", [("0", 0)], 0),
        )
        for case_id, inputs, expected in cases:
            assert compute_deduccion_maternidad_0611(inputs) == expected, case_id

    def test_compute_anti_tautology_delta(self) -> None:
        """Incrementing meses from 6 to 12 must change result by exactly 600."""
        from .._deduccion_maternidad import compute_deduccion_maternidad_0611

        r6 = compute_deduccion_maternidad_0611([("0", 6)])
        r12 = compute_deduccion_maternidad_0611([("0", 12)])
        assert r12 - r6 == 600


# ---------------------------------------------------------------------------
# The engine's half of the hybrid: which descendant contributes its months.
# ---------------------------------------------------------------------------


class TestMaternidadEligibleMeses:
    """The month window Art. 81.1 draws from the birth date alone.

    Two boundaries the authority states and neither of which is a year-end age
    test: the month of birth counts in full, and the month the child turns three
    does not count. The second is why a child who turns three mid-year is not
    simply excluded from the period.
    """

    def test_a_child_under_three_all_year_has_every_month(self) -> None:
        assert _hijo_menor_3(0).maternidad_eligible_meses(2024) == 12

    def test_the_birth_month_counts_in_full(self) -> None:
        """Born in June 2024: June to December is seven months, not six."""
        child = DescendantInfo(birth_date=date(2024, 6, 15))

        assert child.maternidad_eligible_meses(2024) == 7

    def test_the_month_the_child_turns_three_does_not_count(self) -> None:
        """Born April 2021, turns three in April 2024: January to March only."""
        child = DescendantInfo(birth_date=date(2021, 4, 15))

        assert child.maternidad_eligible_meses(2024) == 3

    def test_a_january_third_birthday_leaves_no_eligible_month(self) -> None:
        child = DescendantInfo(birth_date=date(2021, 1, 20))

        assert child.maternidad_eligible_meses(2024) == 0

    def test_a_leap_day_birth_resolves_without_constructing_a_third_birthday(self) -> None:
        """29 February has no anniversary in a non-leap year; the window still resolves."""
        child = DescendantInfo(birth_date=date(2020, 2, 29))

        assert child.maternidad_eligible_meses(2023) == 1

    def test_a_period_before_the_birth_has_no_eligible_month(self) -> None:
        assert DescendantInfo(birth_date=date(2025, 3, 1)).maternidad_eligible_meses(2024) == 0


class TestArt811EntryWindowDivergesFromArt582:
    """The Art. 81.1 entry window is DATE-scoped where Art. 58.2 is PERIOD-scoped.

    Two windows that agree on every case tried are indistinguishable from one
    window, so these cases are chosen to make them disagree, and to disagree in
    BOTH directions for the same child. A late-year inscription is the shape
    that separates them: the entry period is granted whole by the period-scoped
    limb while its earlier months sit outside the date-scoped one, and the
    fourth calendar year is inside the date-scoped one after the period-scoped
    one has closed.
    """

    #: Inscribed 15 November 2021. Art. 58.2 grants periods 2021, 2022 and 2023.
    #: Art. 81.1 runs from November 2021 to October 2024 inclusive.
    _ADOPTADO = DescendantInfo(
        birth_date=date(2016, 3, 2),
        relacion=DescendantRelacion.ADOPTADO,
        inscripcion_registro_civil_date=date(2021, 11, 15),
        meses_madre_trabajo_2024=12,
    )

    def test_the_entry_period_is_whole_for_art_58_2_and_partial_for_art_81_1(self) -> None:
        """First direction: the period limb is wider in the year of entry."""
        assert self._ADOPTADO.is_eligible_minimo_incremento_menor_tres(2021) is True
        assert self._ADOPTADO.art_81_1_entry_window_meses(2021) == 2

    def test_the_fourth_year_is_inside_art_81_1_and_outside_art_58_2(self) -> None:
        """Second direction: the date limb outlives the period limb."""
        assert self._ADOPTADO.is_eligible_minimo_incremento_menor_tres(2024) is False
        assert self._ADOPTADO.art_81_1_entry_window_meses(2024) == 10

    def test_the_window_is_age_independent(self) -> None:
        """ "Con independencia de la edad del menor": the child was five at inscription."""
        assert self._ADOPTADO.maternidad_eligible_meses(2022) == 0
        assert self._ADOPTADO.art_81_1_entry_window_meses(2022) == 12

    def test_a_relacion_the_statute_excludes_opens_no_window(self) -> None:
        """A temporal acogimiento carer takes the tranches and not this limb."""
        temporal = DescendantInfo(
            birth_date=date(2016, 3, 2),
            relacion=DescendantRelacion.ACOGIMIENTO_TEMPORAL,
            meses_madre_trabajo_2024=12,
        )

        assert temporal.art_81_1_entry_window_meses(2024) == 0

    def test_an_entitling_relacion_with_no_recorded_date_opens_no_window(self) -> None:
        """The window has nothing to measure from, so it withholds rather than guesses."""
        undated = DescendantInfo(
            birth_date=date(2016, 3, 2),
            relacion=DescendantRelacion.ADOPTADO,
            meses_madre_trabajo_2024=12,
        )

        assert undated.art_81_1_entry_window_meses(2024) == 0

    def test_a_fostered_then_adopted_child_gets_one_window_not_two(self) -> None:
        """The cap: anchoring on the later event would grant six years, not three."""
        fostered_then_adopted = DescendantInfo(
            birth_date=date(2016, 3, 2),
            relacion=DescendantRelacion.ADOPTADO,
            acogimiento_resolucion_date=date(2021, 11, 15),
            inscripcion_registro_civil_date=date(2023, 6, 1),
            meses_madre_trabajo_2024=12,
        )

        assert fostered_then_adopted.art_81_1_entry_window_meses(2024) == 10
        assert fostered_then_adopted.art_81_1_entry_window_meses(2025) == 0

    def test_the_two_limbs_union_rather_than_taking_the_wider(self) -> None:
        """An infant adopted in October is covered by both limbs over different months.

        Under three all year, and inside the entry window from October. Neither
        limb's own count is twelve; their union is.
        """
        infant = DescendantInfo(
            birth_date=date(2024, 1, 10),
            relacion=DescendantRelacion.ADOPTADO,
            inscripcion_registro_civil_date=date(2024, 10, 5),
            meses_madre_trabajo_2024=12,
        )

        assert infant.maternidad_eligible_meses(2024) == 12
        assert infant.art_81_1_entry_window_meses(2024) == 3
        assert infant.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 12

    def test_the_entry_window_reaches_the_deduccion(self) -> None:
        """The consumer clause: a window nothing calls is indistinguishable from no window.

        This child is five, so the under-three limb grants nothing. Every month
        that survives here came from the entry window.
        """
        assert self._ADOPTADO.maternidad_eligible_meses(2024) == 0
        assert self._ADOPTADO.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 10


class TestMaternidadContributingMeses:
    """The child-side condition Art. 81.1 delegates to the mínimo por descendientes.

    Restores the two eligibility cases the retired profile method carried, now
    against the predicate the calculate path actually consults.
    """

    def test_an_eligible_child_contributes_its_declared_months(self) -> None:
        assert _hijo_menor_3(9).maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 9

    def test_a_child_over_three_contributes_nothing(self) -> None:
        """Art. 81.1 runs only "hasta que el menor alcance los tres años de edad"."""
        assert _hijo_no_menor_3().maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 0

    def test_a_non_cohabiting_child_contributes_nothing(self) -> None:
        """The mínimo por descendientes the deduction keys on needs the household limb."""
        child = DescendantInfo(
            birth_date=date(2022, 6, 1),
            convive_con_contribuyente=False,
            meses_madre_trabajo_2024=12,
        )

        assert child.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 0

    def test_an_eligible_child_with_no_declared_months_contributes_nothing(self) -> None:
        """The employment months stay the operator's: absent means none, never inferred."""
        assert _hijo_menor_3(0).maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 0

    def test_a_child_over_the_rentas_ceiling_contributes_nothing(self) -> None:
        """The added half of the predicate: Art. 58.1 excludes on the descendant's own rentas.

        This case is unreachable through a bare age-and-cohabitation test, which
        is why tying the deduction to the mínimo predicate rather than to a
        bespoke one is a behaviour change and not a refactor.
        """
        child = DescendantInfo(
            birth_date=date(2022, 6, 1),
            rentas_anuales_euros=_THRESHOLDS.rentas_anuales_limite + Decimal("1"),
            meses_madre_trabajo_2024=12,
        )

        assert child.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 0

    def test_declared_months_are_capped_by_the_eligible_window(self) -> None:
        """A turning-three child whose mother worked all year contributes the window.

        Twelve declared months against a three-month window yields three. Before
        the window existed this child contributed NOTHING, because the age test
        ran once at year-end and the child was three by then -- an under-grant
        for every family whose child turns three mid-year.
        """
        child = DescendantInfo(birth_date=date(2021, 4, 15), meses_madre_trabajo_2024=12)

        assert child.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 3

    def test_the_cap_never_raises_a_declared_figure(self) -> None:
        """An operator who declared fewer months than the window keeps their figure."""
        child = DescendantInfo(birth_date=date(2022, 6, 1), meses_madre_trabajo_2024=4)

        assert child.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 4


class TestMesesMaternidadPorDescendiente:
    """The profile-level pairing the calculate path feeds to the deducción."""

    def test_pairs_carry_the_descendant_index_as_the_hijo_id(self) -> None:
        profile = RentaFamilyProfile(descendientes=(_hijo_menor_3(12), _hijo_menor_3(6)))

        assert profile.meses_maternidad_por_descendiente(2024, thresholds=_THRESHOLDS) == (("0", 12), ("1", 6))

    def test_ineligible_descendants_are_omitted_but_do_not_shift_the_indices(self) -> None:
        """A withheld child must not renumber the ones after it.

        The index is the identifier every other descendiente surface addresses a
        child by, so a compacted list would report months against the wrong
        record in any diagnostic that names one.
        """
        profile = RentaFamilyProfile(descendientes=(_hijo_no_menor_3(), _hijo_menor_3(6)))

        assert profile.meses_maternidad_por_descendiente(2024, thresholds=_THRESHOLDS) == (("1", 6),)

    def test_a_profile_with_no_contributing_descendants_pairs_nothing(self) -> None:
        profile = RentaFamilyProfile(descendientes=(_hijo_no_menor_3(),))

        assert profile.meses_maternidad_por_descendiente(2024, thresholds=_THRESHOLDS) == ()

    def test_declared_anualidades_suppress_a_dependency_assimilated_descendant(self) -> None:
        """The anualidades carve-out reaches the deducción, not only the mínimo.

        A non-cohabiting but economically dependent descendant is assimilated
        only while the filer declares no anualidades. Reading that flag off the
        profile is what keeps the two answers identical; a pairing that ignored
        it would grant months for a child the mínimo itself withholds.
        """
        dependiente = DescendantInfo(
            birth_date=date(2022, 6, 1),
            convive_con_contribuyente=False,
            dependencia_economica=True,
            meses_madre_trabajo_2024=12,
        )

        assimilated = RentaFamilyProfile(descendientes=(dependiente,))
        suppressed = RentaFamilyProfile(
            descendientes=(dependiente,),
            anualidades_alimentos_euros=Decimal("1200"),
        )

        assert assimilated.meses_maternidad_por_descendiente(2024, thresholds=_THRESHOLDS) == (("0", 12),)
        assert suppressed.meses_maternidad_por_descendiente(2024, thresholds=_THRESHOLDS) == ()
