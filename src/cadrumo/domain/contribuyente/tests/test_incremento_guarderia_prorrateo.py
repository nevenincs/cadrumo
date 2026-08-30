"""Art. 81.2 guardería increment: proration and the per-child cap (casilla 0613).

The expected euros are the AEAT manual's own printed figures for its two worked
cases, transcribed and re-derived by hand from the statement of the rule rather
than read back from the method under test:

* ``(1.000 euros ÷ 12 meses x 2 meses) = 166,67``
* ``(1.000 euros ÷ 12 meses x 6 meses) = 500``

Two things beyond the oracles are asserted, because reproducing the manual's own
cases would not catch either defect these tests remove. The cap must be applied
PER CHILD rather than over the household, and it must be PRORATED rather than
flat — and the flat form reproduces both oracles' households incorrectly only in
the total, which is exactly why it survived.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..descendant import DescendantInfo
from ..family_profile import RentaFamilyProfile
from ..guarderia_mensual import parse_guarderia_mensual
from ..meses_trabajo import parse_meses_trabajo
from ._registry_thresholds import registry_thresholds

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = 2024
_THRESHOLDS = registry_thresholds(_YEAR)

#: "puede alcanzar hasta 1.000 euros anuales". Supplied by the caller in
#: production from its registry parameter; named here so the expectations below
#: read as the manual's arithmetic.
_CAP_ANUAL = Decimal("1000")


def _child(
    birth: date,
    *,
    mensual: str = "",
    annual: int = 0,
    meses_madre: str = "1-12",
    segundo_ciclo_mes: int | None = None,
) -> DescendantInfo:
    """A descendant for the increment tests.

    ``segundo_ciclo_mes`` is the month the second cycle of educación infantil may
    begin, which Art. 81.2 makes the ceiling on the gastos window in the período
    the child turns three. It is the OPERATOR's declaration and this application
    never infers it, so a turning-three fixture that omits it is exercising the
    refusal path rather than an arithmetic result.
    """
    return DescendantInfo(
        birth_date=birth,
        meses_madre_trabajo=parse_meses_trabajo(meses_madre, field="test"),
        gastos_guarderia_euros=annual,
        gastos_guarderia_mensuales=parse_guarderia_mensual(mensual, field="test"),
        segundo_ciclo_infantil_inicio_mes=segundo_ciclo_mes,
    )


def _total(*descendientes: DescendantInfo, year: int = _YEAR) -> Decimal:
    return RentaFamilyProfile(descendientes=descendientes).incremento_guarderia_0613(
        year,
        thresholds=_THRESHOLDS if year == _YEAR else registry_thresholds(year),
        cap_anual=_CAP_ANUAL,
    )


class TestManualWorkedOracles:
    """The two figures the bundled manual prints for its own cases."""

    def test_two_qualifying_months_prorate_to_166_67(self) -> None:
        """Caso a on the manual's REAL facts: a PARTIAL overlap of two month sets.

        The mother does not work before May and is entitled "de mayo a agosto
        ambos incluidos"; the nursery's complete months are January to June. The
        two share exactly May and June, so ``1.000 ÷ 12 × 2 = 166,67``, which the
        manual states as that child's limit. Spend far exceeds the prorated cap,
        so the cap binds — the manual's own note: "El incremento de 166,67 euros
        no supera el límite del importe total del gasto efectivo no
        subvencionado: 2.290".

        These facts are the point of the test and must not be substituted. This
        case previously declared the nursery at months 5-6 only, which made the
        NURSERY count the binding term of a ``min`` over two counts and reached
        166,67 without ever intersecting anything. It passed both before and
        after the count-based defect, and on AEAT's real facts the same code
        returned 333,33 — a 2x over-grant, which under-declares tax. A test that
        reaches the right number through the wrong mechanism is why that survived.
        """
        child = _child(date(2021, 9, 2), mensual="1-6:500", meses_madre="5-8", segundo_ciclo_mes=9)

        assert _total(child) == Decimal("166.67")

    def test_six_qualifying_months_prorate_to_500(self) -> None:
        """1.000 ÷ 12 × 6 = 500 exactly."""
        child = _child(date(2022, 3, 1), mensual="1-6:400")

        assert _total(child) == Decimal("500.00")

    def test_the_manuals_own_turning_three_child_prorates_to_500(self) -> None:
        """The manual's REAL facts for the 500 figure, not a convenient substitute.

        The case above reproduces the arithmetic with a child who is TWO all
        year, so it routes through the under-three branch. The manual's own
        child is not that child: "tendrá derecho a la citada deducción hasta el
        mes de agosto incluido, pues en septiembre cumple 3 años" — born
        September 2021, turning three IN the filing period, and granted the
        increment over "6 meses completos (de enero a junio)", every one of them
        BEFORE the birthday.

        Substituting the younger child is what kept a real defect invisible:
        the right number was reproduced through a branch the real case never
        takes, and the real case returned 0,00 against the manual's 500. Do not
        re-substitute convenient facts here — the birth date is the point.

        The mother's months are the manual's too, and are declared rather than
        left to the fixture default. She is entitled "hasta el mes de agosto
        incluido", so January to August. The figure is 500 either way, because
        the six complete nursery months are the binding term — which is exactly
        why it is worth pinning: a default of all twelve reproduces the right
        number while leaving the Art. 81.1 side of the intersection untested,
        the same shape as the substitution this docstring warns about, one
        field over.
        """
        child = _child(date(2021, 9, 15), mensual="1-6:500", meses_madre="1-8", segundo_ciclo_mes=9)

        assert child.age_at_year_end(_YEAR) == 3
        assert _total(child) == Decimal("500.00")

    def test_the_flat_cap_would_have_produced_1000_for_the_first_case(self) -> None:
        """The defect, stated as the number it produced.

        The retired form applied ``count × 1.000`` with no month term, so the
        two-month child above was granted 1.000 against a correct 166,67 — an
        over-grant of 833,33 € reachable through the documented entry surface.
        Asserting the delta pins what was removed, so a regression to a
        flat cap fails with the figure that motivated the fix.
        """
        child = _child(date(2021, 9, 2), mensual="1-6:500", meses_madre="5-8", segundo_ciclo_mes=9)

        assert _total(child) == Decimal("166.67")
        assert Decimal("1000") - _total(child) == Decimal("833.33")


class TestTheCapIsPerChildNotPerHousehold:
    """An aggregate min lets one child's unused cap absorb another's excess spend."""

    def test_one_childs_spend_cannot_consume_another_childs_unused_cap(self) -> None:
        """Two children, one heavily enrolled and one barely.

        Child A: 12 qualifying months, cap 1.000, spend 5.000 → contributes 1.000.
        Child B: 2 qualifying months, cap 166,67, spend 100 → contributes 100.
        Correct total 1.100.

        A household-wide ``min(total_spend, total_cap)`` would compute
        ``min(5.100, 1.166,67) = 1.166,67`` and grant child B's unused 66,67 to
        child A, who has no entitlement to it.
        """
        heavy = _child(date(2022, 3, 1), mensual="1-12:417")
        light = _child(date(2022, 4, 1), mensual="5:50;6:50")

        assert _total(heavy, light) == Decimal("1100.00")

    def test_a_childs_own_spend_still_bounds_its_prorated_cap(self) -> None:
        """The per-child bound cuts both ways: spend below the cap wins.

        Six months gives a 500 cap, but only 120 was spent, so 120 is granted.
        A cap applied without the spend bound would grant 500 against 120 of
        evidenced expense.
        """
        child = _child(date(2022, 3, 1), mensual="1-6:20")

        assert _total(child) == Decimal("120")


class TestTheThreeGeometries:
    """Two month sets of the same SIZES can share every month, some, or none.

    The article prorates by "el número de meses en que se cumplan de forma
    simultánea los requisitos", which is a question about WHICH months. A count
    cannot answer it: containment, partial overlap and disjointness are
    indistinguishable once each side is reduced to its size, and the three have
    different correct answers. Each geometry is pinned here with the same six
    nursery months, so only the mother's months move.

    The disjoint case could not be written at all before the months were
    carried. With a stored count, "six months worked" against nursery July to
    December was byte-identical to the overlapping declaration, so no correct
    implementation could return zero from it — the inputs did not determine an
    answer. It is the shape change, not a better fixture, that made this
    testable.
    """

    def test_containment_takes_every_nursery_month(self) -> None:
        """Mother January to December contains nursery January to June: six months.

        A must-not-move CONTROL, not a detector. Containment is the one geometry
        a count reading already gets right — ``min(12, 6)`` is also six — so this
        row cannot fail under the count defect and passing it confirms nothing
        about the intersection. It earns its place by pinning the common case
        against a "fix" that chases the rare geometries and moves this one. Two
        of the three rows below discriminate; this one anchors.
        """
        child = _child(date(2022, 3, 1), mensual="1-6:500", meses_madre="1-12")

        assert _total(child) == Decimal("500.00")

    def test_partial_overlap_takes_only_the_shared_months(self) -> None:
        """Mother June to December against nursery January to August shares June to August.

        Three months. Sizes seven and eight, so a ``min`` over the counts takes
        SEVEN and returns 583,33 — measured, not inferred. The answer is neither
        size, which is the point: only the months can say which three coincide.
        """
        child = _child(date(2022, 3, 1), mensual="1-8:500", meses_madre="6-12")

        assert _total(child) == Decimal("250.00")

    def test_disjoint_months_grant_nothing(self) -> None:
        """Mother January to June, nursery July to December: no simultaneous month.

        Both sides declare six months, so every count-based reading yields six
        and 500,00. The correct answer is zero, and only the months can say so.
        """
        child = _child(date(2022, 3, 1), mensual="7-12:500", meses_madre="1-6")

        assert _total(child) == Decimal("0")


class TestSimultaneityBound:
    """The Art. 81.1 side bounds the Art. 81.2 side."""

    def test_the_mothers_months_bound_a_longer_nursery_enrolment(self) -> None:
        """Nursery paid for twelve months, mother qualified for three.

        The requirements must hold SIMULTANEOUSLY, so three months is the basis:
        1.000 ÷ 12 × 3 = 250.
        """
        child = _child(date(2022, 3, 1), mensual="1-12:500", meses_madre="1-3")

        assert _total(child) == Decimal("250.00")

    def test_a_mother_with_no_qualifying_months_contributes_nothing(self) -> None:
        """No Art. 81.1 entitlement means no increment to increase.

        Still correct after the increment was decoupled from the deducción's
        age ceiling: what was removed there is the CHILD's age limb, not the
        mother's own requirement. A mother who never met it has no simultaneous
        months whatever the child's age.
        """
        child = _child(date(2022, 3, 1), mensual="1-12:500", meses_madre="")

        assert _total(child) == Decimal("0")


class TestMaternidadLapsesWhileTheIncrementContinues:
    """Capítulo 18's two named cases, where the deducción stops and the increment does not.

    "en el supuesto de que el descendiente cumpla los tres años en el mes de
    enero o en el caso de que la madre comience a trabajar en el año en el que
    el hijo cumple esa edad, pero después de haberla cumplido, no se podrá
    aplicar la deducción por maternidad, si bien ello no impedirá aplicar el
    incremento de gastos de guardería".

    Both once returned 0,00, because the increment was prorated by the
    deducción's own month count and that count carries the child's under-three
    ceiling. The direction of the error is an under-grant, which is a taxpayer
    paying more than they owe.
    """

    def test_a_child_turning_three_in_january_still_carries_the_increment(self) -> None:
        """The deducción window is empty, and the increment is not.

        Turning three in January leaves no under-three month in the period, so
        the Art. 81.1 deducción has zero months. Five declared nursery months
        from February still prorate: 1.000 ÷ 12 × 5 = 416,67.
        """
        child = _child(date(2022, 1, 20), mensual="2-6:500", segundo_ciclo_mes=9)

        assert child.maternidad_contributing_meses(_YEAR + 1, thresholds=registry_thresholds(_YEAR + 1)) == 0
        assert _total(child, year=_YEAR + 1) == Decimal("416.67")

    def test_a_mother_starting_work_after_the_birthday_still_carries_the_increment(self) -> None:
        """Work begins in April, the child turned three in March.

        The deducción's own months are the two before the birthday, which the
        mother did not work; the increment prorates by her nine worked months
        bounded by the five declared nursery months: 1.000 ÷ 12 × 5 = 416,67.
        """
        child = _child(date(2022, 3, 10), mensual="4-8:500", meses_madre="4-12", segundo_ciclo_mes=9)

        assert _total(child, year=_YEAR + 1) == Decimal("416.67")


class TestMidYearBirthIsTheCommonCase:
    """The population the flat cap over-granted most visibly."""

    def test_a_june_birth_declaring_an_annual_total_prorates_to_seven_months(self) -> None:
        """Born mid-June: eligible from June, so seven months, not twelve.

        1.000 ÷ 12 × 7 = 583,33. The flat cap granted 1.000 on the same facts.
        No month evidence is needed, because the bound comes from the birth date.
        """
        child = _child(date(_YEAR, 6, 15), annual=4000, meses_madre="6-12")

        assert _total(child) == Decimal("583.33")


class TestZeroCases:
    def test_a_childless_profile_is_zero(self) -> None:
        assert _total() == Decimal("0")

    def test_a_child_with_no_declared_spend_contributes_nothing(self) -> None:
        """Qualifying months alone grant nothing; the increment is of SPEND."""
        assert _total(_child(date(2022, 3, 1), annual=0)) == Decimal("0")


class TestSegundoCicloCeiling:
    """Art. 81.2's ceiling: gastos count only up to the month before the second cycle.

    The rule is normative and stated in every year of the manual under its own
    heading, but AEAT never works an example of it and writes the month in the
    SUBJUNCTIVE throughout — "aquel en el que PUEDA comenzar". The authority
    declines to fix the month, so this application declares or discloses and never
    assumes one. September is what the worked examples happen to use; defaulting to
    it would be the same confident month-selection rule this box was already wrong
    with once.
    """

    def test_the_declared_month_bounds_the_turning_three_window(self) -> None:
        """A January birthday with the cycle declared at September: eight months, not twelve.

        The measured gap this class closes. Nursery is declared for all twelve
        months and the mother qualifies throughout, so nothing but the ceiling can
        reduce the window — the increment was granting 1.000,00 where 666,67 is due,
        an over-grant that under-declares tax.
        """
        child = _child(date(2022, 1, 20), mensual="1-12:500", segundo_ciclo_mes=9)

        assert _total(child, year=_YEAR + 1) == Decimal("666.67")

    def test_an_undeclared_month_withholds_the_window_rather_than_opening_it(self) -> None:
        """Undeclared, the turning-three window is refused and the operator is told.

        Refusing under-grants, which over-taxes; opening would over-grant, which
        under-declares. Between two wrong answers this takes the recoverable one:
        the operator can see the advisory and supply the month their centre already
        reports on the modelo 233.
        """
        child = _child(date(2022, 1, 20), mensual="1-12:500")

        assert _total(child, year=_YEAR + 1) == Decimal("0")
        assert child.guarderia_needs_segundo_ciclo_month(_YEAR + 1) is True

    def test_a_child_who_never_turns_three_keeps_months_after_september(self) -> None:
        """The boundary pin, on AEAT's own 2020 caso — the ceiling is scoped, not general.

        Renta 2020 works a child who is two all year with NON-CONTIGUOUS nursery
        months: January to June, plus OCTOBER and NOVEMBER, to eight months. Both of
        those fall after September, and AEAT counts them. A ceiling applied outside
        the turning-three período would silently drop two months the authority
        grants, so this pins the scope rather than the arithmetic.

        The manual prints 666,64 here, rounding the monthly quota first; the engine
        rounds last and yields 666,67, which is what the 2024 and 2025 manuals do for
        their own case. The discrepancy is AEAT's across editions and is deliberately
        not chased — see the row's finding 5.
        """
        child = _child(date(2018, 1, 31), mensual="1-6:500;10:500;11:500")

        assert child.guarderia_needs_segundo_ciclo_month(2020) is False
        assert _total(child, year=2020) == Decimal("666.67")

    def test_a_declared_month_is_not_needed_before_the_turning_three_period(self) -> None:
        """No ceiling, no advisory: the question is only put where it can change an answer."""
        child = _child(date(2022, 3, 1), mensual="1-12:500")

        assert child.guarderia_needs_segundo_ciclo_month(_YEAR) is False


class TestCotizacionesCeilingIsDisclosedNotComputed:
    """The second consumer of the declared month, which this application does not compute.

    Art. 81 bounds the cotizaciones limb in the same período — "las devengadas hasta
    el mes anterior a aquel en el que el hijo pueda iniciar el segundo ciclo". It is
    disclosed rather than applied because the figure is a HOUSEHOLD annual scalar
    while the ceiling is PER CHILD: a household with one child turning three and one
    younger has no single bounding month, and AEAT states no apportionment rule.
    Computing one would invent the number this whole rule exists to stop us inventing.
    """

    def test_it_reports_where_the_unbounded_ceiling_can_change_an_outcome(self) -> None:
        child = _child(date(2022, 1, 20), mensual="1-12:500", segundo_ciclo_mes=9)
        profile = RentaFamilyProfile(descendientes=(child,), cotizaciones_ss_madre_2024=5000)

        assert profile.guarderia_cotizaciones_ceiling_is_unbounded(_YEAR + 1) is True

    def test_it_stays_silent_when_no_cotizaciones_figure_is_declared(self) -> None:
        """With none declared the ceiling binds at zero, which the operator can already see."""
        child = _child(date(2022, 1, 20), mensual="1-12:500", segundo_ciclo_mes=9)
        profile = RentaFamilyProfile(descendientes=(child,), cotizaciones_ss_madre_2024=0)

        assert profile.guarderia_cotizaciones_ceiling_is_unbounded(_YEAR + 1) is False

    def test_it_stays_silent_without_a_turning_three_child(self) -> None:
        """No ceiling applies, so the cotizaciones figure needs no bounding."""
        child = _child(date(2022, 3, 1), mensual="1-12:500")
        profile = RentaFamilyProfile(descendientes=(child,), cotizaciones_ss_madre_2024=5000)

        assert profile.guarderia_cotizaciones_ceiling_is_unbounded(_YEAR) is False
