"""LIRPF DT 12ª apartado-3 time-window eligibility predicate tests.

The window rule is certain date arithmetic over two declared years, grounded in
the bundled consolidated LIRPF (``ley-35-2006.html#dtduodecima`` apartado 3,
added by Ley 26/2014, ``BOE-A-2014-12327``). Expected verdicts are derived from
the verbatim apartado-3 branches, not from the predicate's own output, per the
aeat-quality-gates rule:

- Contingencia in 2015 or later: eligible in the ejercicio the contingencia
  occurs "o en los dos ejercicios siguientes" — window ``[c, c+2]``.
- Contingencia in 2011–2014: eligible "hasta la finalización del octavo
  ejercicio siguiente" — window ``[c, c+8]`` (2011 closes end-2019, 2014
  closes end-2022).
- Contingencia in 2010 or earlier: eligible "hasta el 31 de diciembre de 2018"
  — window ``[c, 2018]``.
"""

from __future__ import annotations

from datetime import date

import pytest

from ...calculations.registry.tests.legal_text import legal_text_match
from ...calculations.registry.tests.published_authority import PublishedGovernedFactSource
from ..dt12_reduccion import (
    Dt12WindowBranch,
    dt12_regime_window_eligibility,
)
from ..errors import PensionReduccionError
from ..modelo_fact_context import ModeloFactResolutionContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_CONTEXT = ModeloFactResolutionContext(
    authority=PublishedGovernedFactSource(),
    filing_period=date(2025, 12, 31),
    devengo_date=date(2025, 12, 31),
)
# DT 12ª apartado 4 (added by Ley 26/2014), read from the published provision:
# contingencias in the span it names keep the eighth-following-ejercicio window, and
# earlier ones are eligible only through the cliff date it prints.
_TRANSITIONAL_FIRST_CONTINGENCIA, _TRANSITIONAL_LAST_CONTINGENCIA = (
    int(year)
    for year in legal_text_match(
        "ley-35-2006:dt-12", r"contingencias acaecidas en los ejercicios (\d{4}) a (\d{4})"
    ).groups()
)
_CLIFF_LAST_ELIGIBLE_YEAR = int(
    legal_text_match("ley-35-2006:dt-12", r"\d{4} o anteriores.*?hasta el 31 de diciembre de (\d{4})").group(1)
)


class TestDt12WindowGeneralBranch:
    """Contingencia >= 2015: the general contingencia-plus-two window."""

    def test_general_branch_window(self) -> None:
        cases = (
            (2024, 2024, True, 2026),
            (2024, 2026, True, 2026),
            (2023, 2026, False, 2025),
            (2024, 2023, False, 2026),
        )
        for contingencia_year, rescate_year, expected_eligible, expected_through_year in cases:
            verdict = dt12_regime_window_eligibility(
                contingencia_year=contingencia_year,
                rescate_year=rescate_year,
                context=_CONTEXT,
            )
            assert verdict.branch is Dt12WindowBranch.GENERAL
            assert verdict.eligible is expected_eligible, (contingencia_year, rescate_year)
            assert verdict.eligible_through_year == expected_through_year


class TestDt12WindowTransitionalBranch:
    """Contingencia in the transitional span: eligible through the eighth following ejercicio."""

    def test_transitional_branch_window(self) -> None:
        last = _TRANSITIONAL_LAST_CONTINGENCIA
        first = _TRANSITIONAL_FIRST_CONTINGENCIA
        cases = (
            (last, last + 8, True, last + 8),
            (last, last + 9, False, last + 8),
            (first, first + 8, True, first + 8),
            (first, first + 9, False, first + 8),
        )
        for contingencia_year, rescate_year, expected_eligible, expected_through_year in cases:
            verdict = dt12_regime_window_eligibility(
                contingencia_year=contingencia_year,
                rescate_year=rescate_year,
                context=_CONTEXT,
            )
            assert verdict.branch is Dt12WindowBranch.TRANSITIONAL_2011_2014
            assert verdict.eligible is expected_eligible, (contingencia_year, rescate_year)
            assert verdict.eligible_through_year == expected_through_year


class TestDt12WindowCliffBranch:
    """Contingencia before the transitional span: the hard 31 December cliff."""

    def test_cliff_branch_window(self) -> None:
        before_span = _TRANSITIONAL_FIRST_CONTINGENCIA - 1
        cliff = _CLIFF_LAST_ELIGIBLE_YEAR
        cases = (
            (before_span - 2, cliff, True),
            (before_span, cliff + 1, False),
            (before_span - 5, cliff + 1, False),
            (before_span - 5, cliff + 4, False),
            (before_span - 5, cliff + 6, False),
            (before_span - 5, cliff + 8, False),
        )
        for contingencia_year, rescate_year, expected_eligible in cases:
            verdict = dt12_regime_window_eligibility(
                contingencia_year=contingencia_year,
                rescate_year=rescate_year,
                context=_CONTEXT,
            )
            assert verdict.branch is Dt12WindowBranch.CLIFF_2010_OR_EARLIER
            assert verdict.eligible is expected_eligible, (contingencia_year, rescate_year)
            assert verdict.eligible_through_year == cliff


class TestDt12WindowInputGuards:
    """The predicate defends against implausible year inputs."""

    def test_implausible_year_raises(self) -> None:
        cases = (
            (0, 2024),
            (1899, 2024),
            (2201, 2024),
            (-1, 2024),
            (2024, 0),
            (2024, 1899),
            (2024, 2201),
            (2024, -1),
        )
        for contingencia_year, rescate_year in cases:
            with pytest.raises(PensionReduccionError):
                dt12_regime_window_eligibility(
                    contingencia_year=contingencia_year,
                    rescate_year=rescate_year,
                    context=_CONTEXT,
                )
