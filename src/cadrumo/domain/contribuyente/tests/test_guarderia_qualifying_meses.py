"""The Art. 81.2 proration basis: qualifying months per descendant.

The increment "puede alcanzar hasta 1.000 euros anuales y se calculará
proporcionalmente al número de meses en que se cumplan de forma simultánea los
requisitos exigidos en el artículo 81.1 y 2". This module covers the 81.2 half
of that intersection — the month COUNT — which the per-child cap is prorated by.

The assertions are month counts rather than euros. The euro figures the manual
works (``1.000 / 12 x 2 = 166,67`` and ``x 6 = 500``) are asserted where the cap
is computed; asserting them here too would re-derive the same arithmetic twice
and prove nothing extra about this method.

The month SELECTION is required to agree with ``guarderia_contributing_spend``,
which decides the same months in euros. A test below pins that agreement
directly, because two derivations of one month set is exactly how a declared
spend month and a prorated month come to disagree.
"""

from __future__ import annotations

from datetime import date

import pytest

from ..descendant import DescendantInfo
from ..guarderia_mensual import parse_guarderia_mensual

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = 2024


def _child(birth: date, *, mensual: str = "", annual: int = 0, convive: bool = True) -> DescendantInfo:
    return DescendantInfo(
        birth_date=birth,
        convive_con_contribuyente=convive,
        gastos_guarderia_euros=annual,
        gastos_guarderia_mensuales=parse_guarderia_mensual(mensual, field="test"),
    )


class TestDeclaredMonthlyMapIsTheEvidence:
    """A monthly map states the months, so the count is read rather than inferred."""

    def test_two_declared_months_count_two(self) -> None:
        """The manual's worked case: two complete months, which prorates to 166,67."""
        assert _child(date(2022, 3, 1), mensual="5:250;6:250").guarderia_qualifying_meses(_YEAR) == 2

    def test_six_declared_months_count_six(self) -> None:
        """The manual's second worked case, which prorates to 500."""
        assert _child(date(2022, 3, 1), mensual="1-6:200").guarderia_qualifying_meses(_YEAR) == 6

    def test_a_declared_map_is_preferred_over_the_age_eligible_fallback(self) -> None:
        """A child under three all year who declares two months counts two, not twelve.

        The fallback exists only where no month information was given. Letting
        it win over declared evidence would restore the flat cap for anyone who
        supplied the detail the statute asks for.
        """
        child = _child(date(2022, 3, 1), mensual="5:250;6:250")

        assert child.age_eligible_guarderia_meses(_YEAR) == 12
        assert child.guarderia_qualifying_meses(_YEAR) == 2


class TestAnnualTotalFallsBackToAgeEligibleMonths:
    """The approximation, and the reason it is bounded rather than twelve."""

    def test_a_mid_year_birth_is_eligible_only_from_its_birth_month(self) -> None:
        """Born in June: seven months, not twelve.

        This is the population the flat cap over-granted most visibly, and it is
        fixed without any month evidence because the bound is computable from
        the birth date alone.
        """
        assert _child(date(_YEAR, 6, 15), annual=3000).guarderia_qualifying_meses(_YEAR) == 7

    def test_a_january_birth_is_eligible_for_the_whole_period(self) -> None:
        assert _child(date(_YEAR, 1, 20), annual=3000).guarderia_qualifying_meses(_YEAR) == 12

    def test_a_child_under_three_throughout_is_eligible_for_twelve(self) -> None:
        assert _child(date(2022, 3, 1), annual=3000).guarderia_qualifying_meses(_YEAR) == 12

    def test_a_child_born_after_the_period_is_eligible_for_none(self) -> None:
        """Profiles are effective-dated, so a later birth must not reach back."""
        assert _child(date(_YEAR + 1, 2, 1), annual=3000).age_eligible_guarderia_meses(_YEAR) == 0


class TestAgeEligibleMonthsIsTotalNotJustCorrectWhereItIsCalled:
    """The accessor answers honestly for inputs its one caller cannot produce.

    ``guarderia_qualifying_meses`` reaches it only under an "under three at
    year-end" guard, where "alive" and "alive and under three" coincide. A
    version that simply returned twelve would be indistinguishable in
    production -- and wrong the moment anything else asked. It is public so an
    operator-facing advisory can quote the months it prorated by, and a figure
    quoted to a taxpayer must be reproducible from their own child's age.
    """

    def test_a_child_already_over_three_all_year_is_eligible_for_none(self) -> None:
        """The case that read as twelve before this was made total."""
        assert _child(date(2019, 6, 10)).age_eligible_guarderia_meses(_YEAR) == 0

    def test_a_child_turning_three_is_eligible_only_until_the_birthday_month(self) -> None:
        """Turning three in June: January to May, five months.

        The birthday month is excluded, matching the boundary the spend method
        already draws for that period.
        """
        assert _child(date(2021, 6, 10)).age_eligible_guarderia_meses(_YEAR) == 5

    def test_a_january_third_birthday_leaves_no_eligible_months(self) -> None:
        assert _child(date(2021, 1, 10)).age_eligible_guarderia_meses(_YEAR) == 0

    def test_the_live_path_is_unchanged_by_making_it_total(self) -> None:
        """Under the caller's guard the answer is identical to before.

        Pins that this correction is contract honesty rather than a behaviour
        change: every descendant the one caller can reach still prorates on the
        same month count.
        """
        for birth in (date(2022, 3, 1), date(2022, 12, 31), date(_YEAR, 6, 15), date(_YEAR, 1, 1)):
            child = _child(birth, annual=1000)
            assert child.age_at_year_end(_YEAR) < 3
            assert child.guarderia_qualifying_meses(_YEAR) == child.age_eligible_guarderia_meses(_YEAR)


class TestTurningThreePeriod:
    """The Art. 81.2 extension, month-scoped, and the one asymmetric case."""

    def test_every_declared_month_counts_including_before_the_birthday(self) -> None:
        """Turning three in June: all four declared months qualify, not just the later two.

        The birthday is not a boundary for the increment. Capítulo 18's
        post-birthday sentence grants months the under-three limb could not
        reach; read as a restriction it would drop the pre-birthday months and
        return zero on the manual's own worked case, which counts January to
        June for a child turning three in September.
        """
        child = _child(date(2021, 6, 10), mensual="4:200;5:200;7:200;8:200")

        assert child.age_at_year_end(_YEAR) == 3
        assert child.guarderia_qualifying_meses(_YEAR) == 4

    def test_an_annual_total_in_the_turning_three_period_counts_nothing(self) -> None:
        """No fallback here, deliberately — and the reason is the UPPER edge.

        Not the birthday, which draws no line: a single yearly figure cannot be
        apportioned to a window whose closing month this application declines to
        derive, because the region determines when the second infant-education
        cycle may begin. The spend method returns zero for this shape and raises
        the monthly-detail advisory; the count agrees rather than inventing a
        basis the euros do not have.
        """
        child = _child(date(2021, 6, 10), annual=3000)

        assert child.guarderia_contributing_spend(_YEAR) == 0
        assert child.guarderia_qualifying_meses(_YEAR) == 0

    def test_a_child_past_the_turning_three_period_counts_nothing(self) -> None:
        assert _child(date(2020, 6, 10), mensual="1-12:200").guarderia_qualifying_meses(_YEAR) == 0


class TestNonCohabitingContributesNothing:
    def test_a_non_cohabiting_descendant_has_no_qualifying_months(self) -> None:
        child = _child(date(2022, 3, 1), mensual="1-6:200", convive=False)

        assert child.guarderia_contributing_spend(_YEAR) == 0
        assert child.guarderia_qualifying_meses(_YEAR) == 0


class TestMonthSelectionAgreesWithTheSpendMethod:
    """One month set, two renderings. They must not be able to disagree."""

    @pytest.mark.parametrize(
        "birth",
        [date(2022, 3, 1), date(2021, 6, 10), date(2020, 6, 10), date(_YEAR, 6, 15)],
        ids=["under-three", "turning-three", "past-three", "born-mid-year"],
    )
    def test_zero_months_and_zero_spend_coincide_for_a_declared_map(self, birth: date) -> None:
        """Whenever one is zero on a declared map, so is the other.

        The load-bearing agreement: a descendant contributing spend but no
        months would divide by an empty basis, and one contributing months but
        no spend would prorate a cap against nothing. Either state is a
        divergence between two derivations of the same months.
        """
        child = _child(birth, mensual="1-12:100")

        assert (child.guarderia_qualifying_meses(_YEAR) == 0) == (child.guarderia_contributing_spend(_YEAR) == 0)

    def test_the_turning_three_methods_select_the_same_declared_entries(self) -> None:
        """Both methods read the SAME declared entries, checked by construction.

        Distinct per-month amounts and months on both sides of the birthday, so
        if either method reintroduced a birthday filter the other did not, the
        euro sum and the month count would diverge here. That divergence is the
        regression this pins: it is how a declared spend month and a prorated
        month come to disagree, and re-adding the filter to one method alone
        makes exactly one of these two assertions fail.
        """
        child = _child(date(2021, 6, 10), mensual="1:100;2:200;3:300;7:400;8:500")

        assert child.guarderia_contributing_spend(_YEAR) == 1_500
        assert child.guarderia_qualifying_meses(_YEAR) == 5
