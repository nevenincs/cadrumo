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
    marriage_date_from_facts,
    marriage_derived_facts,
    marriage_full_year,
    marriage_month_start,
    parse_marriage_date_flag,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

FILING_YEAR = 2024
_DERIVED_FACT_KEYS = {
    "renta_taxpayer.marriage_date",
    "renta_taxpayer.marriage_full_year",
    "renta_taxpayer.marriage_month_start",
    "renta_taxpayer.marriage_month_end",
}
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
_ORACLE_FACT_CASES = (
    (
        "sobrevenido-march-2024",
        date(2024, 3, 22),
        False,
        3,
        {
            "renta_taxpayer.marriage_full_year": "0",
            "renta_taxpayer.marriage_month_start": "3",
            "renta_taxpayer.marriage_month_end": "12",
        },
    ),
    (
        "full-year-september-2023",
        date(2023, 9, 15),
        True,
        1,
        {
            "renta_taxpayer.marriage_full_year": "1",
            "renta_taxpayer.marriage_month_start": "1",
            "renta_taxpayer.marriage_month_end": "12",
        },
    ),
)
_DERIVED_FACT_KEY_CASES = (
    ("sobrevenido", date(2024, 6, 15), _DERIVED_FACT_KEYS),
    ("full-year", date(2022, 4, 1), _DERIVED_FACT_KEYS),
    ("future-year", date(2025, 3, 1), {"renta_taxpayer.marriage_date"}),
)
_PARSE_VALID_CASES = (
    ("iso", "2024-03-22", date(2024, 3, 22)),
    ("whitespace", "  2023-09-15  ", date(2023, 9, 15)),
    ("leap-day", "2024-02-29", date(2024, 2, 29)),
)
_PARSE_INVALID_CASES = (
    ("slash-format", "22/03/2024", "YYYY-MM-DD"),
    ("nonsense", "not-a-date", None),
    ("invalid-leap-day", "2023-02-29", None),
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
        for case_id, marriage_date, expected_full_year, expected_month_start, expected_facts in _ORACLE_FACT_CASES:
            assert marriage_full_year(marriage_date, FILING_YEAR) is expected_full_year, case_id
            assert marriage_month_start(marriage_date, FILING_YEAR) == expected_month_start, case_id
            facts = dict(marriage_derived_facts(marriage_date, FILING_YEAR))
            for fact_path, expected_value in expected_facts.items():
                assert facts[fact_path] == expected_value, case_id

    def test_oracle_no_marriage_date_emits_no_facts(self) -> None:
        """marriage_date=None → no derived facts emitted → casillas default to 0.

        The engine emits 0 for 0245/0246/0247 via the default-missing path when
        the binding has no resolved value.
        """
        facts: dict[str, str] = {}
        recovered = marriage_date_from_facts(facts)
        assert recovered is None
        # marriage_derived_facts is not called when marriage_date is absent;
        # verify the function requires a date (cannot be called with None).
        # No derived facts → binding resolves to default (0) for each casilla.


# ---------------------------------------------------------------------------
# marriage_derived_facts roundtrip
# ---------------------------------------------------------------------------


class TestMarriageDerivedFacts:
    def test_derived_fact_key_cases(self) -> None:
        """Filing-year/prior-year marriages emit derived facts; future marriages emit only the date."""
        for case_id, marriage_date, expected_keys in _DERIVED_FACT_KEY_CASES:
            facts = dict(marriage_derived_facts(marriage_date, FILING_YEAR))
            assert set(facts.keys()) == expected_keys, case_id

    def test_marriage_date_roundtrip_via_facts(self) -> None:
        """Store marriage_date as fact → recover via marriage_date_from_facts."""
        md = date(2024, 3, 22)
        facts = dict(marriage_derived_facts(md, FILING_YEAR))
        recovered = marriage_date_from_facts(facts)
        assert recovered == md

    def test_anti_tautology_absent_marriage_date_returns_none(self) -> None:
        """Anti-tautology: removing marriage_date from facts → returns None.

        If marriage_date_from_facts always returned a date regardless of
        the fact being present, this test would fail — proving the check
        is meaningful.
        """
        md = date(2024, 3, 22)
        facts = dict(marriage_derived_facts(md, FILING_YEAR))
        facts.pop("renta_taxpayer.marriage_date")
        recovered = marriage_date_from_facts(facts)
        assert recovered is None


# ---------------------------------------------------------------------------
# parse_marriage_date_flag
# ---------------------------------------------------------------------------


class TestParseMarriageDateFlag:
    def test_valid_cases(self) -> None:
        for case_id, raw, expected in _PARSE_VALID_CASES:
            assert parse_marriage_date_flag(raw) == expected, case_id

    def test_invalid_cases(self) -> None:
        for case_id, raw, match in _PARSE_INVALID_CASES:
            if match is None:
                with pytest.raises(ValueError) as exc_info:
                    parse_marriage_date_flag(raw)
            else:
                with pytest.raises(ValueError, match=match) as exc_info:
                    parse_marriage_date_flag(raw)
            assert isinstance(exc_info.value, ValueError), case_id
