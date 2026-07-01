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

    def test_same_year_is_eligible(self) -> None:
        verdict = dt12_regime_window_eligibility(contingencia_year=2024, rescate_year=2024)
        assert verdict.branch is Dt12WindowBranch.GENERAL
        assert verdict.eligible is True
        assert verdict.eligible_through_year == 2026

    def test_two_years_after_is_eligible(self) -> None:
        # 2024 contingencia + 2 following ejercicios -> eligible through 2026.
        verdict = dt12_regime_window_eligibility(contingencia_year=2024, rescate_year=2026)
        assert verdict.eligible is True
        assert verdict.eligible_through_year == 2026

    def test_three_years_after_is_out_of_window(self) -> None:
        # 2023 contingencia window closes end-2025; a 2026 rescate is out of window.
        verdict = dt12_regime_window_eligibility(contingencia_year=2023, rescate_year=2026)
        assert verdict.branch is Dt12WindowBranch.GENERAL
        assert verdict.eligible is False
        assert verdict.eligible_through_year == 2025

    def test_rescate_before_contingencia_is_ineligible(self) -> None:
        # The window opens with the contingency; a rescate percibida earlier
        # cannot apply the régimen.
        verdict = dt12_regime_window_eligibility(contingencia_year=2024, rescate_year=2023)
        assert verdict.eligible is False


class TestDt12WindowTransitional2011To2014Branch:
    """Contingencia 2011–2014: eligible through the eighth following ejercicio."""

    def test_2014_window_closes_end_2022(self) -> None:
        verdict = dt12_regime_window_eligibility(contingencia_year=2014, rescate_year=2022)
        assert verdict.branch is Dt12WindowBranch.TRANSITIONAL_2011_2014
        assert verdict.eligible is True
        assert verdict.eligible_through_year == 2022

    def test_2014_rescate_2023_is_out_of_window(self) -> None:
        verdict = dt12_regime_window_eligibility(contingencia_year=2014, rescate_year=2023)
        assert verdict.branch is Dt12WindowBranch.TRANSITIONAL_2011_2014
        assert verdict.eligible is False
        assert verdict.eligible_through_year == 2022

    def test_2011_window_closes_end_2019(self) -> None:
        verdict = dt12_regime_window_eligibility(contingencia_year=2011, rescate_year=2019)
        assert verdict.eligible is True
        assert verdict.eligible_through_year == 2019

    def test_2011_rescate_2020_is_out_of_window(self) -> None:
        verdict = dt12_regime_window_eligibility(contingencia_year=2011, rescate_year=2020)
        assert verdict.eligible is False


class TestDt12WindowCliff2010OrEarlierBranch:
    """Contingencia <= 2010: the hard 31-12-2018 cliff."""

    def test_2008_rescate_2018_is_eligible(self) -> None:
        verdict = dt12_regime_window_eligibility(contingencia_year=2008, rescate_year=2018)
        assert verdict.branch is Dt12WindowBranch.CLIFF_2010_OR_EARLIER
        assert verdict.eligible is True
        assert verdict.eligible_through_year == 2018

    def test_2010_rescate_2019_is_out_of_window(self) -> None:
        verdict = dt12_regime_window_eligibility(contingencia_year=2010, rescate_year=2019)
        assert verdict.branch is Dt12WindowBranch.CLIFF_2010_OR_EARLIER
        assert verdict.eligible is False
        assert verdict.eligible_through_year == 2018

    def test_every_current_filing_year_is_out_of_window_for_old_contingencia(self) -> None:
        # Research F5: for filing years this app serves (2019+), every
        # contingencia <= 2014 branch is already closed.
        for rescate_year in (2019, 2022, 2024, 2026):
            verdict = dt12_regime_window_eligibility(contingencia_year=2005, rescate_year=rescate_year)
            assert verdict.eligible is False


class TestDt12WindowInputGuards:
    """The predicate defends against implausible year inputs."""

    def test_implausible_year_raises(self) -> None:
        for year in (0, 1899, 2201, -1):
            with pytest.raises(PensionReduccionError):
                dt12_regime_window_eligibility(contingencia_year=year, rescate_year=2024)
            with pytest.raises(PensionReduccionError):
                dt12_regime_window_eligibility(contingencia_year=2024, rescate_year=year)
