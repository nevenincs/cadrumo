"""Real-behaviour tests for :mod:`cadrumo.core.parsing.dates`.

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

from collections.abc import Callable
from datetime import date

import pytest

from ..dates import _parse_ddmmyyyy_date, _parse_iso8601_date

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_Parser = Callable[[str | None], date | None]


def test_date_parsers_accept_contract_formats_and_reject_foreign_formats() -> None:
    cases: tuple[tuple[str, _Parser, tuple[tuple[str, tuple[int, int, int]], ...], tuple[str, ...]], ...] = (
        (
            "iso8601",
            _parse_iso8601_date,
            (
                ("2024-12-31", (2024, 12, 31)),
                ("2000-01-01", (2000, 1, 1)),
                ("  2023-06-15  ", (2023, 6, 15)),
            ),
            (
                "31/12/2024",
                "31-12-2024",
                "not-a-date",
                "2024/12/31",
            ),
        ),
        (
            "ddmmyyyy",
            _parse_ddmmyyyy_date,
            (
                ("31-12-2024", (2024, 12, 31)),
                ("31/12/2024", (2024, 12, 31)),
                ("01-01-2000", (2000, 1, 1)),
                ("  15/06/2023  ", (2023, 6, 15)),
            ),
            (
                "2024-12-31",
                "2024/12/31",
                "not-a-date",
                "20241231",
                "31.12.2024",
                "32-01-2024",
                "00-01-2024",
                "31-02-2024",
            ),
        ),
    )

    for label, parser, valid_inputs, invalid_inputs in cases:
        for raw, expected_tuple in valid_inputs:
            result = parser(raw)
            assert result is not None, (label, raw)
            assert (result.year, result.month, result.day) == expected_tuple, (label, raw)
        for raw in (None, "", "   "):
            assert parser(raw) is None, (label, raw)
        for raw in invalid_inputs:
            with pytest.raises(ValueError):
                parser(raw)
