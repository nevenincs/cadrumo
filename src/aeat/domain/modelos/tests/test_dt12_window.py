"""LIRPF DT 12ª apartado-4 time-window eligibility predicate tests.

The window rule is certain date arithmetic over two declared years, grounded in
the bundled consolidated LIRPF (``ley-35-2006.html#dtduodecima`` apartado 4,
added by Ley 26/2014, ``BOE-A-2014-12327``). Expected verdicts are derived from
the verbatim apartado-4 branches, not from the predicate's own output, per the
no-tautological-calculation-tests rule:

- Contingencia in 2015 or later: eligible in the ejercicio the contingencia
  occurs "o en los dos ejercicios siguientes" — window ``[c, c+2]``.
- Contingencia in 2011–2014: eligible "hasta la finalización del octavo
  ejercicio siguiente" — window ``[c, c+8]`` (2011 closes end-2019, 2014
  closes end-2022).
- Contingencia in 2010 or earlier: eligible "hasta el 31 de diciembre de 2018"
  — window ``[c, 2018]``.
"""

from __future__ import annotations

import pytest

from ...modelos._dt12_reduccion import (
    Dt12WindowBranch,
    dt12_regime_window_eligibility,
)
from ...modelos._errors import PensionReduccionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class TestDt12WindowGeneralBranch:
    """Contingencia >= 2015: the general contingencia-plus-two window."""

    @pytest.mark.parametrize(
        ("contingencia_year", "rescate_year", "expected_eligible", "expected_through_year"),
        [
            pytest.param(2024, 2024, True, 2026, id="same-year"),
            pytest.param(2024, 2026, True, 2026, id="two-following-years"),
            pytest.param(2023, 2026, False, 2025, id="three-years-after"),
            pytest.param(2024, 2023, False, 2026, id="before-contingencia"),
        ],
    )
    def test_general_branch_window(
        self,
        contingencia_year: int,
        rescate_year: int,
        expected_eligible: bool,
        expected_through_year: int,
    ) -> None:
        verdict = dt12_regime_window_eligibility(
            contingencia_year=contingencia_year,
            rescate_year=rescate_year,
        )
        assert verdict.branch is Dt12WindowBranch.GENERAL
        assert verdict.eligible is expected_eligible
        assert verdict.eligible_through_year == expected_through_year


class TestDt12WindowTransitional2011To2014Branch:
    """Contingencia 2011–2014: eligible through the eighth following ejercicio."""

    @pytest.mark.parametrize(
        ("contingencia_year", "rescate_year", "expected_eligible", "expected_through_year"),
        [
            pytest.param(2014, 2022, True, 2022, id="2014-closes-2022"),
            pytest.param(2014, 2023, False, 2022, id="2014-after-close"),
            pytest.param(2011, 2019, True, 2019, id="2011-closes-2019"),
            pytest.param(2011, 2020, False, 2019, id="2011-after-close"),
        ],
    )
    def test_transitional_2011_2014_branch_window(
        self,
        contingencia_year: int,
        rescate_year: int,
        expected_eligible: bool,
        expected_through_year: int,
    ) -> None:
        verdict = dt12_regime_window_eligibility(
            contingencia_year=contingencia_year,
            rescate_year=rescate_year,
        )
        assert verdict.branch is Dt12WindowBranch.TRANSITIONAL_2011_2014
        assert verdict.eligible is expected_eligible
        assert verdict.eligible_through_year == expected_through_year


class TestDt12WindowCliff2010OrEarlierBranch:
    """Contingencia <= 2010: the hard 31-12-2018 cliff."""

    @pytest.mark.parametrize(
        ("contingencia_year", "rescate_year", "expected_eligible"),
        [
            pytest.param(2008, 2018, True, id="before-cliff"),
            pytest.param(2010, 2019, False, id="after-cliff"),
            pytest.param(2005, 2019, False, id="current-filing-2019"),
            pytest.param(2005, 2022, False, id="current-filing-2022"),
            pytest.param(2005, 2024, False, id="current-filing-2024"),
            pytest.param(2005, 2026, False, id="current-filing-2026"),
        ],
    )
    def test_cliff_2010_or_earlier_branch_window(
        self,
        contingencia_year: int,
        rescate_year: int,
        expected_eligible: bool,
    ) -> None:
        verdict = dt12_regime_window_eligibility(
            contingencia_year=contingencia_year,
            rescate_year=rescate_year,
        )
        assert verdict.branch is Dt12WindowBranch.CLIFF_2010_OR_EARLIER
        assert verdict.eligible is expected_eligible
        assert verdict.eligible_through_year == 2018


class TestDt12WindowInputGuards:
    """The predicate defends against implausible year inputs."""

    @pytest.mark.parametrize(
        ("contingencia_year", "rescate_year"),
        [
            pytest.param(0, 2024, id="zero-contingencia"),
            pytest.param(1899, 2024, id="low-contingencia"),
            pytest.param(2201, 2024, id="high-contingencia"),
            pytest.param(-1, 2024, id="negative-contingencia"),
            pytest.param(2024, 0, id="zero-rescate"),
            pytest.param(2024, 1899, id="low-rescate"),
            pytest.param(2024, 2201, id="high-rescate"),
            pytest.param(2024, -1, id="negative-rescate"),
        ],
    )
    def test_implausible_year_raises(self, contingencia_year: int, rescate_year: int) -> None:
        with pytest.raises(PensionReduccionError):
            dt12_regime_window_eligibility(
                contingencia_year=contingencia_year,
                rescate_year=rescate_year,
            )
