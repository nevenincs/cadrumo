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

from .....domain.justificante._errors import JustificanteParseError
from .._extract import _parse_datetime, _parse_decimal, _strip_accents

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


# ---------------------------------------------------------------------------
# _strip_accents
# ---------------------------------------------------------------------------


def test_strip_accents_passes_ascii_string_unchanged() -> None:
    assert _strip_accents("Codigo") == "Codigo"


def test_strip_accents_drops_acute_accent_on_o() -> None:
    """AEAT prints ``Código`` in many fields; the extractor must
    recover the value even when the accent's combining mark is in a
    non-canonical form."""
    assert _strip_accents("Código") == "Codigo"


def test_strip_accents_drops_tilde_n_and_full_accent_set() -> None:
    assert _strip_accents("ñoño") == "nono"
    assert _strip_accents("áéíóú") == "aeiou"


def test_strip_accents_handles_uppercase_accents() -> None:
    assert _strip_accents("ÁÉÍÓÚ") == "AEIOU"


def test_strip_accents_empty_string_returns_empty() -> None:
    assert _strip_accents("") == ""


# ---------------------------------------------------------------------------
# _parse_decimal
# ---------------------------------------------------------------------------


def test_parse_decimal_spanish_thousands_plus_decimal() -> None:
    """AEAT default printing — dots as thousands, comma as decimal."""
    assert _parse_decimal("1.234,56") == Decimal("1234.56")


def test_parse_decimal_plain_comma_decimal_no_thousands_separator() -> None:
    assert _parse_decimal("1234,56") == Decimal("1234.56")


def test_parse_decimal_plain_dot_decimal_no_thousands_separator() -> None:
    assert _parse_decimal("1234.56") == Decimal("1234.56")


def test_parse_decimal_us_style_thousands_with_dot_as_decimal() -> None:
    """When BOTH `,` and `.` are present and `.` is right-most, the
    dot wins as decimal (US-style: 1,234.56)."""
    assert _parse_decimal("1,234.56") == Decimal("1234.56")


def test_parse_decimal_strips_surrounding_whitespace() -> None:
    assert _parse_decimal("  1234,56  ") == Decimal("1234.56")


def test_parse_decimal_strips_internal_whitespace() -> None:
    """Some bank exports use thin-space thousands separators; the
    helper strips internal spaces before parsing."""
    assert _parse_decimal("1 234,56") == Decimal("1234.56")


def test_parse_decimal_preserves_negative_sign() -> None:
    assert _parse_decimal("-1.234,56") == Decimal("-1234.56")


def test_parse_decimal_zero_decimal_form() -> None:
    """Whole-amount edge case — zero with no separators."""
    assert _parse_decimal("0") == Decimal("0")


def test_parse_decimal_raises_on_malformed_input() -> None:
    with pytest.raises(JustificanteParseError, match="invalid decimal"):
        _parse_decimal("not-a-number")


def test_parse_decimal_raises_with_malformed_attribute_when_field_supplied() -> None:
    """Structured attribute shape: malformed=(field,) is set when field name is passed."""
    with pytest.raises(JustificanteParseError) as exc_info:
        _parse_decimal("not-a-number", field="total_a_ingresar")
    exc = exc_info.value
    assert exc.malformed == ("total_a_ingresar",)
    assert exc.missing == ()
    assert exc.ambiguous == ()
    assert exc.coverage is None


def test_parse_decimal_malformed_attribute_empty_when_no_field() -> None:
    """Without a field argument the malformed tuple is empty."""
    with pytest.raises(JustificanteParseError) as exc_info:
        _parse_decimal("bad")
    assert exc_info.value.malformed == ()


# ---------------------------------------------------------------------------
# _parse_datetime
# ---------------------------------------------------------------------------


def test_parse_datetime_iso_with_seconds() -> None:
    """Quarterly modelo receipts use ISO-like YYYY-MM-DD HH:MM:SS."""
    assert _parse_datetime("2026-04-30 14:30:00") == datetime(2026, 4, 30, 14, 30, 0)


def test_parse_datetime_iso_without_seconds() -> None:
    assert _parse_datetime("2026-04-30 14:30") == datetime(2026, 4, 30, 14, 30)


def test_parse_datetime_european_dmy_with_seconds() -> None:
    """Annual modelo receipts (100, 190, etc.) use DD-MM-YYYY HH:MM:SS."""
    assert _parse_datetime("30-04-2026 14:30:00") == datetime(2026, 4, 30, 14, 30, 0)


def test_parse_datetime_european_dmy_without_seconds() -> None:
    assert _parse_datetime("30-04-2026 14:30") == datetime(2026, 4, 30, 14, 30)


def test_parse_datetime_accepts_t_separator_between_date_and_time() -> None:
    """The helper replaces T with a space before parsing so ISO-8601-
    style ``2026-04-30T14:30:00`` works."""
    assert _parse_datetime("2026-04-30T14:30:00") == datetime(2026, 4, 30, 14, 30, 0)


def test_parse_datetime_strips_surrounding_whitespace() -> None:
    assert _parse_datetime("  2026-04-30 14:30:00  ") == datetime(2026, 4, 30, 14, 30, 0)


def test_parse_datetime_raises_on_unrecognised_format() -> None:
    with pytest.raises(JustificanteParseError, match="unrecognised datetime literal"):
        _parse_datetime("not-a-datetime")


def test_parse_datetime_raises_with_malformed_presented_at_attribute() -> None:
    """Structured attribute: malformed=('presented_at',) when datetime is unrecognised."""
    with pytest.raises(JustificanteParseError) as exc_info:
        _parse_datetime("not-a-datetime")
    exc = exc_info.value
    assert exc.malformed == ("presented_at",)
    assert exc.missing == ()
