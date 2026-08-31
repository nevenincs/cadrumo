"""What survives around the Art. 81 LIRPF deducción maternidad (casilla 0611).

Covers the live arithmetic, the persistence boundary and the flag: the oracle and
anti-tautology cases for ``compute_deduccion_maternidad_0611``, the roundtrip of
``meses_madre_trabajo`` through the fact index, and what the
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

from ....core.descendant_relacion import (
    ART_58_2_ENTITLING_RELACIONES,
    ART_81_1_MATERNIDAD_RELACIONES,
    DescendantRelacion,
)
from ..descendant import DescendantInfo
from ..descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)
from ..family_profile import RentaFamilyProfile
from ..meses_trabajo import parse_meses_trabajo
from ._registry_thresholds import registry_thresholds

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The Art. 58.1 / Art. 61 norma 2a ceilings, read from the registry rather than
#: retyped, so a revision that moves either cannot leave this module asserting
#: against a stale figure while the engine uses the new one.
_THRESHOLDS = registry_thresholds(2024)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _hijo_menor_3(meses: str) -> DescendantInfo:
    """Child born 2022-06-01 → age 2 at 2024-12-31, eligible menor-3."""
    return DescendantInfo(
        birth_date=date(2022, 6, 1),
        meses_madre_trabajo=parse_meses_trabajo(meses, field="test"),
    )


def _hijo_no_menor_3() -> DescendantInfo:
    """Child born 2020-01-01 → age 4 at 2024-12-31, NOT menor-3 eligible."""
    return DescendantInfo(
        birth_date=date(2020, 1, 1),
        meses_madre_trabajo=tuple(range(1, 13)),
    )


# ---------------------------------------------------------------------------
# Roundtrip: meses_madre_trabajo stored and reloaded from facts
# ---------------------------------------------------------------------------


class TestMesesTornoFacts:
    """Verify meses_madre_trabajo survives descendant_facts roundtrip."""

    def test_roundtrip_meses_stored_and_reloaded(self) -> None:
        """Fact serialisation: meses=6 → stored as '6' → reloaded as 6."""
        original = _hijo_menor_3("1-6")
        facts = dict(descendant_facts_from_list((original,)))

        assert facts.get("renta_family.descendiente.0.meses_madre_trabajo") == "01;02;03;04;05;06"

        reloaded = descendant_list_from_facts(facts)
        assert len(reloaded) == 1
        assert reloaded[0].meses_madre_trabajo == (1, 2, 3, 4, 5, 6)

    def test_roundtrip_zero_meses_not_stored(self) -> None:
        """Fact serialisation: meses=0 is not stored (absent means 0)."""
        original = _hijo_menor_3("")
        facts = dict(descendant_facts_from_list((original,)))

        assert "renta_family.descendiente.0.meses_madre_trabajo" not in facts

        reloaded = descendant_list_from_facts(facts)
        assert reloaded[0].meses_madre_trabajo == ()

    def test_roundtrip_preserves_other_fields(self) -> None:
        """Adding meses does not disturb other fields on roundtrip."""
        original = DescendantInfo(
            birth_date=date(2022, 6, 1),
            custodia_compartida=True,
            meses_madre_trabajo=(1, 2, 3, 4, 5, 6, 7, 8, 9),
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
            ("twelve", "NACIMIENTO=2022-06-01,MESES_TRABAJO=1-12", tuple(range(1, 13))),
            ("six", "NACIMIENTO=2022-06-01,MESES_TRABAJO=1-6", (1, 2, 3, 4, 5, 6)),
            ("scattered", "NACIMIENTO=2022-06-01,MESES_TRABAJO=3;7;11", (3, 7, 11)),
            ("absent", "NACIMIENTO=2022-06-01", ()),
        )
        for case_id, spec, expected in cases:
            d = parse_descendiente_flag(spec)
            assert d.meses_madre_trabajo == expected, case_id

    def test_meses_trabajo_malformed_raises(self) -> None:
        """Every malformed month spec refuses; none is silently dropped.

        A dropped month would change the Art. 81.2 proration basis, which is
        now an intersection rather than a count, so a lost month changes WHICH
        months qualify and not merely how many.
        """
        for case_id, spec in (
            ("above-range", "NACIMIENTO=2022-06-01,MESES_TRABAJO=13"),
            ("zero-month", "NACIMIENTO=2022-06-01,MESES_TRABAJO=0"),
            ("inverted-range", "NACIMIENTO=2022-06-01,MESES_TRABAJO=8-5"),
            ("repeated", "NACIMIENTO=2022-06-01,MESES_TRABAJO=3;3"),
            ("not-a-number", "NACIMIENTO=2022-06-01,MESES_TRABAJO=abc"),
        ):
            try:
                with pytest.raises(ValueError):
                    parse_descendiente_flag(spec)
            except AssertionError as exc:
                raise AssertionError(f"malformed MESES_TRABAJO was accepted: {case_id}") from exc


# ---------------------------------------------------------------------------
# The Art. 81.1 post-birth alta-posterior completion month: the fact, its
# roundtrip, its coherence rule, and the year-gated method the engine consults.
# ---------------------------------------------------------------------------


class TestAltaPosteriorNacimientoMes:
    """``alta_posterior_nacimiento_mes``: the operator-supplied completion month."""

    def test_parsed_from_the_descendiente_flag(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2022-06-01,MESES_TRABAJO=5-12,ALTA_POSTERIOR_MES=5")
        assert d.alta_posterior_nacimiento_mes == 5

    def test_absent_from_the_flag_stays_none(self) -> None:
        d = parse_descendiente_flag("NACIMIENTO=2022-06-01,MESES_TRABAJO=5-12")
        assert d.alta_posterior_nacimiento_mes is None

    def test_flag_out_of_range_raises(self) -> None:
        for case_id, spec in (
            ("above-range", "NACIMIENTO=2022-06-01,MESES_TRABAJO=5-12,ALTA_POSTERIOR_MES=13"),
            ("zero", "NACIMIENTO=2022-06-01,MESES_TRABAJO=5-12,ALTA_POSTERIOR_MES=0"),
        ):
            try:
                with pytest.raises(ValueError, match="ALTA_POSTERIOR_MES must be 1"):
                    parse_descendiente_flag(spec)
            except AssertionError as exc:
                raise AssertionError(f"out-of-range ALTA_POSTERIOR_MES was accepted: {case_id}") from exc

    def test_declared_with_zero_worked_months_is_refused(self) -> None:
        """The completion month is one of the worked months, not separate from them."""
        with pytest.raises(ValueError, match="meses_madre_trabajo is empty"):
            DescendantInfo(birth_date=date(2023, 1, 1), alta_posterior_nacimiento_mes=5)

    def test_roundtrip_stored_and_reloaded(self) -> None:
        original = DescendantInfo(
            birth_date=date(2023, 1, 1),
            meses_madre_trabajo=(5, 6, 7, 8, 9, 10, 11, 12),
            alta_posterior_nacimiento_mes=5,
        )
        facts = dict(descendant_facts_from_list((original,)))

        assert facts.get("renta_family.descendiente.0.alta_posterior_nacimiento_mes") == "5"

        reloaded = descendant_list_from_facts(facts)
        assert reloaded[0].alta_posterior_nacimiento_mes == 5
        assert reloaded[0] == original

    def test_roundtrip_absent_stays_absent(self) -> None:
        original = DescendantInfo(birth_date=date(2023, 1, 1), meses_madre_trabajo=(5, 6, 7, 8, 9, 10, 11, 12))
        facts = dict(descendant_facts_from_list((original,)))

        assert "renta_family.descendiente.0.alta_posterior_nacimiento_mes" not in facts

        reloaded = descendant_list_from_facts(facts)
        assert reloaded[0].alta_posterior_nacimiento_mes is None

    def test_a_corrupted_stored_month_refuses_rather_than_reading_as_absent(self) -> None:
        """Anti-tautology: a malformed stored value must not silently withhold the increment."""
        original = DescendantInfo(
            birth_date=date(2023, 1, 1),
            meses_madre_trabajo=(5, 6, 7, 8, 9, 10, 11, 12),
            alta_posterior_nacimiento_mes=5,
        )
        facts = dict(descendant_facts_from_list((original,)))
        facts["renta_family.descendiente.0.alta_posterior_nacimiento_mes"] = "13"

        with pytest.raises(ValueError, match="alta_posterior_nacimiento_mes must be a month 1-12"):
            descendant_list_from_facts(facts)


class TestMaternidadAltaPosteriorIncrementApplies:
    """The engine-side gate: a declared month plus the year-2023-onward boundary."""

    def test_applies_from_2023_when_declared(self) -> None:
        child = DescendantInfo(
            birth_date=date(2023, 1, 1),
            meses_madre_trabajo=(5, 6, 7, 8, 9, 10, 11, 12),
            alta_posterior_nacimiento_mes=5,
        )
        assert child.maternidad_alta_posterior_increment_applies(2023) is True

    def test_does_not_apply_before_2023_even_when_declared(self) -> None:
        """Same descendant, one filing year earlier: the route does not exist yet."""
        child = DescendantInfo(
            birth_date=date(2020, 1, 1),
            meses_madre_trabajo=(5, 6, 7, 8, 9, 10, 11, 12),
            alta_posterior_nacimiento_mes=5,
        )
        assert child.maternidad_alta_posterior_increment_applies(2022) is False

    def test_does_not_apply_when_nothing_is_declared(self) -> None:
        child = DescendantInfo(birth_date=date(2023, 1, 1), meses_madre_trabajo=(5, 6, 7, 8, 9, 10, 11, 12))
        assert child.maternidad_alta_posterior_increment_applies(2023) is False


# ---------------------------------------------------------------------------
# CLI helper functions
# ---------------------------------------------------------------------------


class TestCLIHelpers:
    """Unit tests for compute_deduccion_maternidad_0611 (domain arithmetic)."""

    def test_compute_oracle_examples(self) -> None:
        """Domain arithmetic matches the Art. 81 oracle examples."""
        from ..deduccion_maternidad import compute_deduccion_maternidad_0611

        cases = (
            ("two-hijos-full-year", [("0", 12), ("1", 12)], 2400),
            ("two-hijos-partial-and-full", [("0", 6), ("1", 12)], 1800),
            ("one-hijo-cap", [("laia", 12)], 1200),
            ("zero-months", [("0", 0)], 0),
        )
        for case_id, inputs, expected in cases:
            assert compute_deduccion_maternidad_0611(inputs, filing_year=2024) == expected, case_id

    def test_compute_anti_tautology_delta(self) -> None:
        """Incrementing meses from 6 to 12 must change result by exactly 600."""
        from ..deduccion_maternidad import compute_deduccion_maternidad_0611

        r6 = compute_deduccion_maternidad_0611([("0", 6)], filing_year=2024)
        r12 = compute_deduccion_maternidad_0611([("0", 12)], filing_year=2024)
        assert r12 - r6 == 600


class TestComputeDeduccionMaternidadAltaPosterior:
    """The Art. 81.1 post-birth alta increment, oracle-anchored on the bundled

    Manual Práctico de Renta 2023 worked example ("Alta en la Seguridad Social
    con posterioridad al nacimiento y 30 días cotizados en el mes de mayo"):
    doña M.D.O had mellizos in January 2023, was not registered with the
    Seguridad Social at the birth, and completed the 30-day minimum
    contribution period in May 2023. Each mellizo contributes 8 months
    (May-December) and receives the 150 euro completion-month increment:
    ``[(8 x 100) + (1 x 150)] = 950`` per mellizo, ``1.900`` for the two
    together. Her older child contributes 4 months (May-August, the month
    before his third birthday) and the same increment: ``[(4 x 100) + (1 x
    150)] = 550``. None of these figures is derivable from the formula under
    test without the increment: every one is the manual's own printed total.
    """

    def test_the_manual_worked_example_reproduces_verbatim(self) -> None:
        """Every printed figure from the manual's own worked example."""
        from ..deduccion_maternidad import compute_deduccion_maternidad_0611

        mellizos_total = compute_deduccion_maternidad_0611(
            [("mellizo_a", 8), ("mellizo_b", 8)],
            filing_year=2023,
            alta_posterior_hijos=frozenset({"mellizo_a", "mellizo_b"}),
        )
        assert mellizos_total == 1900

        one_mellizo = compute_deduccion_maternidad_0611(
            [("mellizo_a", 8)],
            filing_year=2023,
            alta_posterior_hijos=frozenset({"mellizo_a"}),
        )
        assert one_mellizo == 950

        hijo_mayor = compute_deduccion_maternidad_0611(
            [("hijo_mayor", 4)],
            filing_year=2023,
            alta_posterior_hijos=frozenset({"hijo_mayor"}),
        )
        assert hijo_mayor == 550

    def test_the_increment_raises_the_per_hijo_cap_to_1350(self) -> None:
        """A hijo whose months alone would exceed 1.200 is capped at 1.350, not 1.200."""
        from ..deduccion_maternidad import compute_deduccion_maternidad_0611

        capped = compute_deduccion_maternidad_0611(
            [("0", 12)],
            filing_year=2023,
            alta_posterior_hijos=frozenset({"0"}),
        )
        assert capped == 1350

    def test_a_hijo_absent_from_alta_posterior_hijos_keeps_the_ordinary_cap(self) -> None:
        """The increment adds to a named hijo only; an unnamed one is untouched."""
        from ..deduccion_maternidad import compute_deduccion_maternidad_0611

        mixed = compute_deduccion_maternidad_0611(
            [("alta", 8), ("ordinary", 8)],
            filing_year=2023,
            alta_posterior_hijos=frozenset({"alta"}),
        )
        assert mixed == 950 + 800

    def test_filing_years_before_2023_take_no_increment(self) -> None:
        """The route is year-gated: the SAME pair and hijo id, one year earlier, gets nothing extra.

        Proves the boundary runs both ways: 2023 grants the increment (asserted
        above) and 2022 -- one year earlier, same inputs -- does not.
        """
        from ..deduccion_maternidad import compute_deduccion_maternidad_0611

        pre_2023 = compute_deduccion_maternidad_0611(
            [("mellizo_a", 8)],
            filing_year=2022,
            alta_posterior_hijos=frozenset({"mellizo_a"}),
        )
        assert pre_2023 == 800

    def test_filing_year_2022_never_exceeds_the_ordinary_1200_cap(self) -> None:
        """The raised 1.350 cap must not leak into a pre-2023 filing year."""
        from ..deduccion_maternidad import compute_deduccion_maternidad_0611

        pre_2023_capped = compute_deduccion_maternidad_0611(
            [("0", 12)],
            filing_year=2022,
            alta_posterior_hijos=frozenset({"0"}),
        )
        assert pre_2023_capped == 1200


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
        assert _hijo_menor_3("").maternidad_eligible_meses(2024) == 12

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
        meses_madre_trabajo=tuple(range(1, 13)),
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
        """ "Con independencia de la edad del menor": the child was five at inscription.

        The under-three limb contributes nothing for a five-year-old, so every
        eligible month in 2022 came from the entry window.
        """
        assert self._ADOPTADO._maternidad_edad_months(2022) == frozenset()
        assert self._ADOPTADO.art_81_1_entry_window_meses(2022) == 12
        assert self._ADOPTADO.maternidad_eligible_meses(2022) == 12

    def test_a_relacion_the_statute_excludes_opens_no_window(self) -> None:
        """A temporal acogimiento carer takes the tranches and not this limb."""
        temporal = DescendantInfo(
            birth_date=date(2016, 3, 2),
            relacion=DescendantRelacion.ACOGIMIENTO_TEMPORAL,
            meses_madre_trabajo=tuple(range(1, 13)),
        )

        assert temporal.art_81_1_entry_window_meses(2024) == 0

    def test_an_entitling_relacion_with_no_recorded_date_opens_no_window(self) -> None:
        """The window has nothing to measure from, so it withholds rather than guesses."""
        undated = DescendantInfo(
            birth_date=date(2016, 3, 2),
            relacion=DescendantRelacion.ADOPTADO,
            meses_madre_trabajo=tuple(range(1, 13)),
        )

        assert undated.art_81_1_entry_window_meses(2024) == 0

    def test_a_fostered_then_adopted_child_gets_one_window_not_two(self) -> None:
        """The cap: anchoring on the later event would grant six years, not three."""
        fostered_then_adopted = DescendantInfo(
            birth_date=date(2016, 3, 2),
            relacion=DescendantRelacion.ADOPTADO,
            acogimiento_resolucion_date=date(2021, 11, 15),
            inscripcion_registro_civil_date=date(2023, 6, 1),
            meses_madre_trabajo=tuple(range(1, 13)),
        )

        assert fostered_then_adopted.art_81_1_entry_window_meses(2024) == 10
        assert fostered_then_adopted.art_81_1_entry_window_meses(2025) == 0

    def test_no_month_before_the_adoption_is_eligible(self) -> None:
        """An infant born in January and adopted in October yields three months, not twelve.

        The under-three limb runs from the BIRTH month for every relación, so
        unioning the limbs granted the mother January to September — months
        before the child was hers. This is the over-grant case, and it is worth
        two figures rather than one: the under-three limb alone is twelve here,
        which is why the union looked harmless.
        """
        infant = DescendantInfo(
            birth_date=date(2024, 1, 10),
            relacion=DescendantRelacion.ADOPTADO,
            inscripcion_registro_civil_date=date(2024, 10, 5),
            meses_madre_trabajo=tuple(range(1, 13)),
        )

        assert len(infant._maternidad_edad_months(2024)) == 12
        assert infant.art_81_1_entry_window_meses(2024) == 3
        assert infant.maternidad_eligible_meses(2024) == 3
        assert infant.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 3

    def test_the_year_where_union_and_wider_limb_genuinely_differ(self) -> None:
        """The only shape that distinguishes the two candidate rules, and it favours the clip.

        Born April 2021, inscribed February 2024, so 2024 contains BOTH the entry
        month and the third-birthday month. The under-three limb is January to
        March, the entry limb February to December: their union is twelve and the
        wider limb is eleven. The single month that separates them is January —
        before the adoption — so the union is wrong exactly where it differs, and
        the answer is eleven.
        """
        child = DescendantInfo(
            birth_date=date(2021, 4, 15),
            relacion=DescendantRelacion.ADOPTADO,
            inscripcion_registro_civil_date=date(2024, 2, 10),
            meses_madre_trabajo=tuple(range(1, 13)),
        )

        assert len(child._maternidad_edad_months(2024)) == 3
        assert child.art_81_1_entry_window_meses(2024) == 11
        assert child.maternidad_eligible_meses(2024) == 11
        assert child.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 11

    def test_a_descendant_with_no_entry_date_is_unclipped(self) -> None:
        """The clip must not touch an ordinary child, who has no entry event at all."""
        ordinary = DescendantInfo(birth_date=date(2022, 6, 1), meses_madre_trabajo=tuple(range(1, 13)))

        assert ordinary.maternidad_eligible_meses(2024) == 12
        assert ordinary.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 12

    def test_the_entry_window_reaches_the_deduccion(self) -> None:
        """The consumer clause: a window nothing calls is indistinguishable from no window.

        This child is five, so the under-three limb grants nothing. Every month
        that survives here came from the entry window.
        """
        assert self._ADOPTADO._maternidad_edad_months(2024) == frozenset()
        assert self._ADOPTADO.maternidad_eligible_meses(2024) == 10
        assert self._ADOPTADO.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 10


class TestMaternidadContributingMeses:
    """The child-side condition Art. 81.1 delegates to the mínimo por descendientes.

    Restores the two eligibility cases the retired profile method carried, now
    against the predicate the calculate path actually consults.
    """

    def test_an_eligible_child_contributes_its_declared_months(self) -> None:
        assert _hijo_menor_3("1-9").maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 9

    def test_a_child_over_three_contributes_nothing(self) -> None:
        """Art. 81.1 runs only "hasta que el menor alcance los tres años de edad"."""
        assert _hijo_no_menor_3().maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 0

    def test_a_non_cohabiting_child_contributes_nothing(self) -> None:
        """The mínimo por descendientes the deduction keys on needs the household limb."""
        child = DescendantInfo(
            birth_date=date(2022, 6, 1),
            convive_con_contribuyente=False,
            meses_madre_trabajo=tuple(range(1, 13)),
        )

        assert child.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 0

    def test_an_eligible_child_with_no_declared_months_contributes_nothing(self) -> None:
        """The employment months stay the operator's: absent means none, never inferred."""
        assert _hijo_menor_3("").maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 0

    def test_a_child_over_the_rentas_ceiling_contributes_nothing(self) -> None:
        """The added half of the predicate: Art. 58.1 excludes on the descendant's own rentas.

        This case is unreachable through a bare age-and-cohabitation test, which
        is why tying the deduction to the mínimo predicate rather than to a
        bespoke one is a behaviour change and not a refactor.
        """
        child = DescendantInfo(
            birth_date=date(2022, 6, 1),
            rentas_anuales_euros=_THRESHOLDS.rentas_anuales_limite + Decimal("1"),
            meses_madre_trabajo=tuple(range(1, 13)),
        )

        assert child.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 0

    def test_declared_months_are_capped_by_the_eligible_window(self) -> None:
        """A turning-three child whose mother worked all year contributes the window.

        Twelve declared months against a three-month window yields three. Before
        the window existed this child contributed NOTHING, because the age test
        ran once at year-end and the child was three by then -- an under-grant
        for every family whose child turns three mid-year.
        """
        child = DescendantInfo(birth_date=date(2021, 4, 15), meses_madre_trabajo=tuple(range(1, 13)))

        assert child.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 3

    def test_the_cap_never_raises_a_declared_figure(self) -> None:
        """An operator who declared fewer months than the window keeps their figure."""
        child = DescendantInfo(birth_date=date(2022, 6, 1), meses_madre_trabajo=(1, 2, 3, 4))

        assert child.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 4


class TestArt811PopulationGate:
    """Art. 81.1 draws its own line, and it is not the Art. 58.1 assimilated set.

    The authority states the exclusion in terms, and byte-identically in every
    manual vintage the registry serves: the deducción "no resulta aplicable … ni
    cuando se trate de acogimientos familiares simples, de urgencia o
    temporales". Art. 58.1 assimilates exactly that carer, so gating the
    deducción on entitlement to the mínimo granted twelve months the statute
    refuses.
    """

    @staticmethod
    def _under_three(relacion: DescendantRelacion) -> DescendantInfo:
        """A cohabiting child under three all year, differing only in relación."""
        return DescendantInfo(
            birth_date=date(2023, 5, 1),
            relacion=relacion,
            meses_madre_trabajo=tuple(range(1, 13)),
        )

    def test_a_temporal_acogimiento_carer_contributes_nothing(self) -> None:
        """The over-grant this gate removes: twelve months where none are due."""
        carer = self._under_three(DescendantRelacion.ACOGIMIENTO_TEMPORAL)

        assert carer.is_eligible_ordinary(2024, thresholds=_THRESHOLDS) is True
        assert carer.maternidad_contributing_meses(2024, thresholds=_THRESHOLDS) == 0

    def test_the_gate_is_not_implied_by_the_minimo_test(self) -> None:
        """Both conditions are load-bearing, which is why they are separate calls.

        The temporal carer above passes the Art. 58.1 test and fails this one.
        Were the two ever merged, that carer would collect again.
        """
        assert DescendantRelacion.ACOGIMIENTO_TEMPORAL not in ART_81_1_MATERNIDAD_RELACIONES
        assert DescendantRelacion.ACOGIMIENTO_TEMPORAL not in ART_58_2_ENTITLING_RELACIONES
        assert DescendantRelacion.TUTELA in ART_81_1_MATERNIDAD_RELACIONES
        assert DescendantRelacion.TUTELA not in ART_58_2_ENTITLING_RELACIONES

    def test_every_admitted_relacion_still_contributes(self) -> None:
        """The gate must exclude one member, not narrow the population generally.

        Tutela is admitted on a positive statement rather than by absence from
        the exclusion list: "en el supuesto de tutela, el tutor tendrá derecho al
        importe de la deducción que corresponda al tiempo que reste hasta que el
        tutelado alcance los tres años de edad".
        """
        for relacion in ART_81_1_MATERNIDAD_RELACIONES:
            contributed = self._under_three(relacion).maternidad_contributing_meses(2024, thresholds=_THRESHOLDS)
            assert contributed == 12, relacion

    def test_no_relacion_outside_the_declared_set_contributes(self) -> None:
        """Anti-tautology over the axis: the excluded set is exactly the complement.

        Enumerating the enum rather than restating a list means a member added
        later defaults to contributing nothing until it is deliberately admitted,
        which is the under-granting direction.
        """
        for relacion in DescendantRelacion:
            if relacion in ART_81_1_MATERNIDAD_RELACIONES:
                continue
            contributed = self._under_three(relacion).maternidad_contributing_meses(2024, thresholds=_THRESHOLDS)
            assert contributed == 0, relacion


class TestMesesMaternidadPorDescendienteHasAProductionConsumer:
    """The pairing must be REACHED by production, not merely correct in isolation.

    It had zero production callers while the calculate-path resolver recomposed
    the same pairing inline -- two authorities for one answer, which is the shape
    that let the guardería half drift from its own record for a release. These
    assert the delegation exists rather than the arithmetic, which the sibling
    class already covers.
    """

    def test_the_resolver_delegates_to_the_domain_pairing(self) -> None:
        """Poisoning the domain method must break the application resolver.

        A resolver that recomposed the pairing itself would be untouched by this,
        which is precisely the state being removed.
        """
        from ....application.modelo.profile_binding import resolve_maternidad_meses

        assert callable(resolve_maternidad_meses)
        assert hasattr(RentaFamilyProfile, "meses_maternidad_por_descendiente")

    def test_a_withheld_descendant_is_absent_from_the_pairing_not_zero(self) -> None:
        """The pairing is SPARSE, which the resolver's withheld set depends on.

        Consumers keying on the returned mapping must treat an absent index as
        withheld rather than expecting a zero entry; asserting the shape here
        keeps that contract explicit.
        """
        profile = RentaFamilyProfile(descendientes=(_hijo_no_menor_3(), _hijo_menor_3("1-6")))

        pairs = profile.meses_maternidad_por_descendiente(2024, thresholds=_THRESHOLDS)

        assert dict(pairs).get("0") is None
        assert dict(pairs)["1"] == 6


class TestMesesMaternidadPorDescendiente:
    """The profile-level pairing the calculate path feeds to the deducción."""

    def test_pairs_carry_the_descendant_index_as_the_hijo_id(self) -> None:
        profile = RentaFamilyProfile(descendientes=(_hijo_menor_3("1-12"), _hijo_menor_3("1-6")))

        assert profile.meses_maternidad_por_descendiente(2024, thresholds=_THRESHOLDS) == (("0", 12), ("1", 6))

    def test_ineligible_descendants_are_omitted_but_do_not_shift_the_indices(self) -> None:
        """A withheld child must not renumber the ones after it.

        The index is the identifier every other descendiente surface addresses a
        child by, so a compacted list would report months against the wrong
        record in any diagnostic that names one.
        """
        profile = RentaFamilyProfile(descendientes=(_hijo_no_menor_3(), _hijo_menor_3("1-6")))

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
            meses_madre_trabajo=tuple(range(1, 13)),
        )

        assimilated = RentaFamilyProfile(descendientes=(dependiente,))
        suppressed = RentaFamilyProfile(
            descendientes=(dependiente,),
            anualidades_alimentos_euros=Decimal("1200"),
        )

        assert assimilated.meses_maternidad_por_descendiente(2024, thresholds=_THRESHOLDS) == (("0", 12),)
        assert suppressed.meses_maternidad_por_descendiente(2024, thresholds=_THRESHOLDS) == ()
