"""Real-behaviour tests for :mod:`cadrumo.core.parsing.dates`.

Contract under test (contract / contract):

* :func:`parse_iso8601_date` — accepts ``YYYY-MM-DD``; REJECTS
  ``DD/MM/YYYY`` and ``DD-MM-YYYY`` with :exc:`ValueError`.

* :func:`parse_ddmmyyyy_date` — accepts ``DD-MM-YYYY`` and ``DD/MM/YYYY``;
  REJECTS ``YYYY-MM-DD`` with :exc:`ValueError`.

The two variants are intentionally distinct because they serve different wire
formats.  A cross-format rejection test proves they cannot silently accept
each other's input.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

import pytest

from ..dates import _date_shape, parse_ddmmyyyy_date, parse_iso8601_date

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_Parser = Callable[[str | None], date | None]


def test_date_parsers_accept_contract_formats_and_reject_foreign_formats() -> None:
    cases: tuple[tuple[str, _Parser, tuple[tuple[str, tuple[int, int, int]], ...], tuple[str, ...]], ...] = (
        (
            "iso8601",
            parse_iso8601_date,
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
            parse_ddmmyyyy_date,
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


def test_refused_dates_are_diagnosed_by_shape_and_never_logged_in_clear_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A refused date is personal data; the log must carry its shape, not it.

    The values these parsers refuse arrive from a descendant's birth date and
    from the censo registration dates scraped off G313, so echoing one into a
    log writes personal data to a surface that no redaction boundary covers.
    The diagnostic must still say what was wrong, which is what the shape mask
    carries.
    """
    birth_date_canary = "1997-13-45"
    censo_date_canary = "31.12.1998"

    with caplog.at_level(logging.DEBUG, logger="cadrumo.core.parsing.dates"):
        with pytest.raises(ValueError):
            parse_iso8601_date(birth_date_canary)
        with pytest.raises(ValueError):
            parse_ddmmyyyy_date(censo_date_canary)

    logged = "\n".join(record.getMessage() for record in caplog.records)

    # No digit of either value survives into the log.
    assert birth_date_canary not in logged
    assert censo_date_canary not in logged
    for fragment in ("1997", "13", "45", "31", "12", "1998"):
        assert fragment not in logged, fragment
    # The diagnostic is still actionable: each refusal names the shape that
    # arrived and the shape that was expected.
    assert "9999-99-99" in logged
    assert "99.99.9999" in logged


def test_date_shape_classes_every_character_without_carrying_it() -> None:
    """The mask is built from literals: same shape in, same mask out."""
    assert _date_shape("1997-13-45") == "9999-99-99"
    assert _date_shape("2001-13-45") == "9999-99-99"
    assert _date_shape("31/12/1998") == "99/99/9999"
    assert _date_shape("nacimiento") == "AAAAAAAAAA"
    assert _date_shape("12 de mayo") == "99 AA AAAA"
    assert _date_shape("1997-01-02T00:00:00") == "9999-99-99T99:99:99"
    # Accented letters are letters; an unclassed character is neither.
    assert _date_shape("año1") == "AAA9"
    assert _date_shape("1997_01") == "9999?99"
