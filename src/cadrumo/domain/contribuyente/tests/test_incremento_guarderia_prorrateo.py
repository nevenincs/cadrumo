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

from .._guarderia_mensual import parse_guarderia_mensual
from ..family import DescendantInfo, RentaFamilyProfile
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
    meses_madre: int = 12,
) -> DescendantInfo:
    return DescendantInfo(
        birth_date=birth,
        meses_madre_trabajo_2024=meses_madre,
        gastos_guarderia_euros=annual,
        gastos_guarderia_mensuales=parse_guarderia_mensual(mensual, field="test"),
    )


def _total(*descendientes: DescendantInfo) -> Decimal:
    return RentaFamilyProfile(descendientes=descendientes).incremento_guarderia_0613(
        _YEAR,
        thresholds=_THRESHOLDS,
        cap_anual=_CAP_ANUAL,
    )


class TestManualWorkedOracles:
    """The two figures the bundled manual prints for its own cases."""

    def test_two_qualifying_months_prorate_to_166_67(self) -> None:
        """1.000 ÷ 12 × 2 = 166,67, and the manual states it as that child's limit.

        Spend of 2.290 far exceeds the prorated cap, so the cap binds — which is
        the manual's own note: "El incremento de 166,67 euros no supera el
        límite del importe total del gasto efectivo no subvencionado: 2.290".
        """
        child = _child(date(2022, 3, 1), mensual="5:1145;6:1145", meses_madre=4)

        assert _total(child) == Decimal("166.67")

    def test_six_qualifying_months_prorate_to_500(self) -> None:
        """1.000 ÷ 12 × 6 = 500 exactly."""
        child = _child(date(2022, 3, 1), mensual="1-6:400", meses_madre=12)

        assert _total(child) == Decimal("500.00")

    def test_the_flat_cap_would_have_produced_1000_for_the_first_case(self) -> None:
        """The defect, stated as the number it produced.

        The retired form applied ``count × 1.000`` with no month term, so the
        two-month child above was granted 1.000 against a correct 166,67 — an
        over-grant of 833,33 € reachable through the documented entry surface.
        Asserting the delta pins what was removed, so a regression to a
        flat cap fails with the figure that motivated the fix.
        """
        child = _child(date(2022, 3, 1), mensual="5:1145;6:1145", meses_madre=4)

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
        heavy = _child(date(2022, 3, 1), mensual="1-12:417", meses_madre=12)
        light = _child(date(2022, 4, 1), mensual="5:50;6:50", meses_madre=12)

        assert _total(heavy, light) == Decimal("1100.00")

    def test_a_childs_own_spend_still_bounds_its_prorated_cap(self) -> None:
        """The per-child bound cuts both ways: spend below the cap wins.

        Six months gives a 500 cap, but only 120 was spent, so 120 is granted.
        A cap applied without the spend bound would grant 500 against 120 of
        evidenced expense.
        """
        child = _child(date(2022, 3, 1), mensual="1-6:20", meses_madre=12)

        assert _total(child) == Decimal("120")


class TestSimultaneityBound:
    """The Art. 81.1 side bounds the Art. 81.2 side."""

    def test_the_mothers_months_bound_a_longer_nursery_enrolment(self) -> None:
        """Nursery paid for twelve months, mother qualified for three.

        The requirements must hold SIMULTANEOUSLY, so three months is the basis:
        1.000 ÷ 12 × 3 = 250.
        """
        child = _child(date(2022, 3, 1), mensual="1-12:500", meses_madre=3)

        assert _total(child) == Decimal("250.00")

    def test_a_mother_with_no_qualifying_months_contributes_nothing(self) -> None:
        """No Art. 81.1 entitlement means no increment to increase."""
        child = _child(date(2022, 3, 1), mensual="1-12:500", meses_madre=0)

        assert _total(child) == Decimal("0")


class TestMidYearBirthIsTheCommonCase:
    """The population the flat cap over-granted most visibly."""

    def test_a_june_birth_declaring_an_annual_total_prorates_to_seven_months(self) -> None:
        """Born mid-June: eligible from June, so seven months, not twelve.

        1.000 ÷ 12 × 7 = 583,33. The flat cap granted 1.000 on the same facts.
        No month evidence is needed, because the bound comes from the birth date.
        """
        child = _child(date(_YEAR, 6, 15), annual=4000, meses_madre=12)

        assert _total(child) == Decimal("583.33")


class TestZeroCases:
    def test_a_childless_profile_is_zero(self) -> None:
        assert _total() == Decimal("0")

    def test_a_child_with_no_declared_spend_contributes_nothing(self) -> None:
        """Qualifying months alone grant nothing; the increment is of SPEND."""
        assert _total(_child(date(2022, 3, 1), meses_madre=12, annual=0)) == Decimal("0")
