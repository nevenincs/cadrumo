"""Real-behaviour tests for :mod:`aeat.core.parsing._dates`.

Contract under test (contract / contract):

* :func:`_parse_iso8601_date` — accepts ``YYYY-MM-DD``; REJECTS
  ``DD/MM/YYYY`` and ``DD-MM-YYYY`` with :exc:`ValueError`.

* :func:`_parse_ddmmyyyy_date` — accepts ``DD-MM-YYYY`` and ``DD/MM/YYYY``;
  REJECTS ``YYYY-MM-DD`` with :exc:`ValueError`.

The two variants are intentionally distinct because they serve different wire
formats.  A cross-format rejection test proves they cannot silently accept
each other's input.
"""

from __future__ import annotations

import pytest

from .._dates import _parse_ddmmyyyy_date, _parse_iso8601_date

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# _parse_iso8601_date — valid inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected_tuple",
    [
        ("2024-12-31", (2024, 12, 31)),
        ("2000-01-01", (2000, 1, 1)),
        ("  2023-06-15  ", (2023, 6, 15)),
    ],
)
def test_iso8601_accepts_valid_dates(raw: str, expected_tuple: tuple[int, int, int]) -> None:
    result = _parse_iso8601_date(raw)
    assert result is not None
    assert (result.year, result.month, result.day) == expected_tuple


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_iso8601_absent_returns_none(raw: str | None) -> None:
    assert _parse_iso8601_date(raw) is None


# ---------------------------------------------------------------------------
# _parse_iso8601_date — REJECTS foreign (dd/mm/yyyy) format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "foreign",
    [
        "31/12/2024",  # dd/mm/yyyy with slash separator — the canonical ddmmyyyy format
        "31-12-2024",  # dd-mm-yyyy with dash separator
        "not-a-date",
        "2024/12/31",  # slash separator is not ISO-8601 extended
    ],
)
def test_iso8601_rejects_foreign_format(foreign: str) -> None:
    """ISO-8601 parser MUST reject day-first and other non-standard inputs."""
    with pytest.raises(ValueError):
        _parse_iso8601_date(foreign)


# ---------------------------------------------------------------------------
# _parse_ddmmyyyy_date — valid inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected_tuple",
    [
        ("31-12-2024", (2024, 12, 31)),
        ("31/12/2024", (2024, 12, 31)),
        ("01-01-2000", (2000, 1, 1)),
        ("  15/06/2023  ", (2023, 6, 15)),
    ],
)
def test_ddmmyyyy_accepts_valid_dates(raw: str, expected_tuple: tuple[int, int, int]) -> None:
    result = _parse_ddmmyyyy_date(raw)
    assert result is not None
    assert (result.year, result.month, result.day) == expected_tuple


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_ddmmyyyy_absent_returns_none(raw: str | None) -> None:
    assert _parse_ddmmyyyy_date(raw) is None


# ---------------------------------------------------------------------------
# _parse_ddmmyyyy_date — REJECTS foreign (ISO-8601) format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "foreign",
    [
        "2024-12-31",  # ISO-8601 with dash separator
        "2024/12/31",  # ISO-8601 with slash separator
        "not-a-date",
        "20241231",  # no separator at all
        "31.12.2024",  # dot separator not supported
    ],
)
def test_ddmmyyyy_rejects_foreign_format(foreign: str) -> None:
    """Day-first parser MUST reject ISO-8601 and other non-day-first inputs."""
    with pytest.raises(ValueError):
        _parse_ddmmyyyy_date(foreign)


# ---------------------------------------------------------------------------
# _parse_ddmmyyyy_date — invalid calendar dates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_calendar",
    [
        "32-01-2024",  # day 32 does not exist
        "00-01-2024",  # day 0 does not exist
        "31-02-2024",  # Feb 31 does not exist
    ],
)
def test_ddmmyyyy_rejects_invalid_calendar_date(invalid_calendar: str) -> None:
    with pytest.raises(ValueError):
        _parse_ddmmyyyy_date(invalid_calendar)
