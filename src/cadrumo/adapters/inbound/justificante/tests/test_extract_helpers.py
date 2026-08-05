"""Focused unit tests for justificante._extract pure helpers.

The three helpers — `_strip_accents`, `_parse_decimal`,
`_parse_datetime` — gate justificante extraction correctness.
Currently exercised only indirectly through fixture-driven
end-to-end tests in `test_extract_modelos.py`. A regression in the
locale-aware decimal parsing (e.g., swapping comma-vs-dot
priority) or the multi-format datetime parser (dropping the
DD-MM-YYYY annual format) would silently corrupt every parsed
justificante.

Tests pin the helpers' documented parsing rules; assertions are
predicate-contract assertions, not calculation tautologies.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from .....domain.justificante import JustificanteParseError
from .._extract import _parse_datetime, _parse_decimal, _strip_accents

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_STRIP_ACCENTS_CASES = (
    ("ascii", "Codigo", "Codigo"),
    ("codigo-accent", "Código", "Codigo"),
    ("tilde-n", "ñoño", "nono"),
    ("lower-vowels", "áéíóú", "aeiou"),
    ("upper-vowels", "ÁÉÍÓÚ", "AEIOU"),
    ("empty", "", ""),
)

_DECIMAL_CASES = (
    ("spanish-thousands", "1.234,56", Decimal("1234.56")),
    ("plain-comma", "1234,56", Decimal("1234.56")),
    ("plain-dot", "1234.56", Decimal("1234.56")),
    ("us-thousands", "1,234.56", Decimal("1234.56")),
    ("surrounding-whitespace", "  1234,56  ", Decimal("1234.56")),
    ("internal-whitespace", "1 234,56", Decimal("1234.56")),
    ("negative", "-1.234,56", Decimal("-1234.56")),
    ("zero", "0", Decimal("0")),
)

_DATETIME_CASES = (
    ("iso-seconds", "2026-04-30 14:30:00", datetime(2026, 4, 30, 14, 30, 0)),
    ("iso-minutes", "2026-04-30 14:30", datetime(2026, 4, 30, 14, 30)),
    ("dmy-seconds", "30-04-2026 14:30:00", datetime(2026, 4, 30, 14, 30, 0)),
    ("dmy-minutes", "30-04-2026 14:30", datetime(2026, 4, 30, 14, 30)),
    ("t-separator", "2026-04-30T14:30:00", datetime(2026, 4, 30, 14, 30, 0)),
    ("surrounding-whitespace", "  2026-04-30 14:30:00  ", datetime(2026, 4, 30, 14, 30, 0)),
)


# ---------------------------------------------------------------------------
# _strip_accents
# ---------------------------------------------------------------------------


def test_strip_accents_cases() -> None:
    """AEAT prints ``Código`` in many fields; the extractor must
    recover the value even when the accent's combining mark is in a
    non-canonical form."""
    for case_id, value, expected in _STRIP_ACCENTS_CASES:
        assert _strip_accents(value) == expected, case_id


# ---------------------------------------------------------------------------
# _parse_decimal
# ---------------------------------------------------------------------------


def test_parse_decimal_cases() -> None:
    """When BOTH `,` and `.` are present and `.` is right-most, the
    dot wins as decimal (US-style: 1,234.56)."""
    for case_id, value, expected in _DECIMAL_CASES:
        assert _parse_decimal(value) == expected, case_id


def test_parse_decimal_raises_on_malformed_input_and_preserves_error_shape() -> None:
    with pytest.raises(JustificanteParseError, match="invalid decimal"):
        _parse_decimal("not-a-number")

    with pytest.raises(JustificanteParseError) as exc_info:
        _parse_decimal("not-a-number", field="total_a_ingresar")
    exc = exc_info.value
    assert exc.malformed == ("total_a_ingresar",)
    assert exc.missing == ()
    assert exc.ambiguous == ()
    assert exc.coverage is None

    with pytest.raises(JustificanteParseError) as exc_info:
        _parse_decimal("bad")
    assert exc_info.value.malformed == ()


def test_parse_decimal_refuses_the_ambiguous_thousands_reading() -> None:
    """A dot-only amount is refused rather than read a thousandfold small.

    The receipt amount regexes capture ``([0-9][0-9\\.,]*)``, which -- unlike
    ``SPANISH_AMOUNT_GROUP`` -- does not require the ``,NN`` tail. Without this
    guard ``1.234`` decodes as ``Decimal("1.234")``, so a receipt total of one
    thousand two hundred thirty-four would be recorded as one euro twenty-three.
    """
    for raw in ("1.234", "45.678", "100.000"):
        with pytest.raises(JustificanteParseError, match="ambiguous thousands"):
            _parse_decimal(raw)

    with pytest.raises(JustificanteParseError) as exc_info:
        _parse_decimal("1.234", field="total_a_ingresar")
    exc = exc_info.value
    assert exc.malformed == ("total_a_ingresar",)
    assert exc.missing == ()


def test_parse_decimal_ambiguity_guard_stays_narrow() -> None:
    """Every shape carrying its own evidence still parses.

    A comma settles the reading, a four-digit lead cannot be a thousands run,
    and a bare integer has no dot to be ambiguous about. The guard must reject
    only the genuinely two-way token, or it would refuse real receipts.
    """
    unambiguous: tuple[tuple[str, Decimal], ...] = (
        ("1.234,56", Decimal("1234.56")),
        ("1234.56", Decimal("1234.56")),
        ("0.333", Decimal("0.333")),
        ("1234", Decimal("1234")),
        ("-1.234,56", Decimal("-1234.56")),
    )
    for raw, expected in unambiguous:
        assert _parse_decimal(raw) == expected, raw


# ---------------------------------------------------------------------------
# _parse_datetime
# ---------------------------------------------------------------------------


def test_parse_datetime_cases() -> None:
    """Annual modelo receipts (100, 190, etc.) use DD-MM-YYYY HH:MM:SS."""
    for case_id, value, expected in _DATETIME_CASES:
        assert _parse_datetime(value) == expected, case_id


def test_parse_datetime_raises_on_unrecognised_format_with_malformed_presented_at() -> None:
    with pytest.raises(JustificanteParseError, match="unrecognised datetime literal"):
        _parse_datetime("not-a-datetime")

    with pytest.raises(JustificanteParseError) as exc_info:
        _parse_datetime("not-a-datetime")
    exc = exc_info.value
    assert exc.malformed == ("presented_at",)
    assert exc.missing == ()
