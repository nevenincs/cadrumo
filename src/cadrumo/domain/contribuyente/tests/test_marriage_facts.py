"""Tests for marriage_date profile axis and Art. 82 LIRPF casillas 0245/0246/0247.

Oracle values come from Art. 82 LIRPF (ley-35-2006):
  - casilla 0245: 1 when matrimonio vigente todo el año, 0 when sobrevenido
  - casilla 0246: primer mes en que estuvo vigente el matrimonio (1-12)
  - casilla 0247: último mes completo en que estuvo vigente el matrimonio (12 by convention)

Oracle cases (from task spec #213):
  - marriage_date=2024-03-22, filing 2024 → 0245=0, 0246=3, 0247=12
  - marriage_date=2023-09-15, filing 2024 → 0245=1, 0246=1, 0247=12
  - marriage_date=None (soltera) → no facts emitted → 0245=0, 0246=0, 0247=0 via default-missing
"""

from __future__ import annotations

from datetime import date

import pytest

from ..marriage_facts import (
    marriage_full_year,
    marriage_month_start,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

FILING_YEAR = 2024
_FULL_YEAR_CASES = (
    ("prior-year", date(2023, 9, 15), True),
    ("same-year", date(2024, 3, 22), False),
    ("same-year-first-day", date(2024, 1, 1), False),
    ("future-year", date(2025, 1, 1), False),
)
_MONTH_START_CASES = (
    ("prior-year", date(2023, 9, 15), 1),
    ("march", date(2024, 3, 22), 3),
    ("december", date(2024, 12, 1), 12),
    ("future-year", date(2025, 3, 1), None),
)
_ORACLE_CASES = (
    (
        "sobrevenido-march-2024",
        date(2024, 3, 22),
        False,
        3,
    ),
    (
        "full-year-september-2023",
        date(2023, 9, 15),
        True,
        1,
    ),
)


# ---------------------------------------------------------------------------
# marriage_full_year and marriage_month_start unit contracts
# ---------------------------------------------------------------------------


class TestMarriageFullYear:
    def test_cases(self) -> None:
        """Prior-year marriage is full-year; filing-year or future marriage is not."""
        for case_id, marriage_date, expected in _FULL_YEAR_CASES:
            assert marriage_full_year(marriage_date, FILING_YEAR) is expected, case_id


class TestMarriageMonthStart:
    def test_cases(self) -> None:
        """Prior-year, filing-year, and future-year marriage month-start cases."""
        for case_id, marriage_date, expected in _MONTH_START_CASES:
            assert marriage_month_start(marriage_date, FILING_YEAR) == expected, case_id


# ---------------------------------------------------------------------------
# Oracle tests — casillas 0245 / 0246 / 0247 from spec #213
# ---------------------------------------------------------------------------


class TestMarriageOracleCases:
    """Oracle cases from task spec #213 grounded in Art. 82 LIRPF."""

    def test_oracle_fact_cases(self) -> None:
        """Task spec #213 oracle cases for casillas 0245, 0246, and 0247."""
        for case_id, marriage_date, expected_full_year, expected_month_start in _ORACLE_CASES:
            assert marriage_full_year(marriage_date, FILING_YEAR) is expected_full_year, case_id
            assert marriage_month_start(marriage_date, FILING_YEAR) == expected_month_start, case_id
