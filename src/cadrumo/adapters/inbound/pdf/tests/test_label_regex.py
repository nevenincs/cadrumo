"""Unit tests for the shared label-regex primitive.

Covers the Spanish-decimal parser and the ``SPANISH_AMOUNT_GROUP`` regex,
including its NBSP-thousands acceptance and column-separator rejection guard.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from ..label_regex import SPANISH_AMOUNT_GROUP, parse_spanish_decimal

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class TestParseSpanishDecimal:
    """:func:`parse_spanish_decimal` round-trip and tolerance coverage."""

    def test_parses(self) -> None:
        """Each canonical Spanish-decimal shape decodes to the expected Decimal."""
        cases: tuple[tuple[str, Decimal | None], ...] = (
            ("1.234,56", Decimal("1234.56")),
            ("0,00", Decimal("0.00")),
            ("-42,50", Decimal("-42.50")),
            ("1.000.000,00", Decimal("1000000.00")),
            ("1234.56", Decimal("1234.56")),
            ("", None),
            ("-", None),
            ("not a number", None),
        )

        for raw, expected in cases:
            assert parse_spanish_decimal(raw) == expected, raw

    def test_parses_whitespace_thousands_separator(self) -> None:
        """Whitespace-thousands forms decode at the parse layer."""
        cases: tuple[tuple[str, str, Decimal], ...] = (
            # parse_spanish_decimal() tolerates every unicode
            # whitespace variant (including ASCII / tab) for robustness
            # on messy input. The REGEX capture is stricter (NBSP / narrow
            # NBSP only — see TestSpanishAmountGroupRegex) to avoid
            # crossing column-separator whitespace on AEAT PDFs.
            ("nbsp", "1\xa0234,56", Decimal("1234.56")),  # U+00A0 non-breaking space
            ("ascii-space", "1 234,56", Decimal("1234.56")),  # ASCII space — parse tolerates
            ("tab", "1\t234,56", Decimal("1234.56")),  # tab — parse tolerates
        )

        for case_id, raw, expected in cases:
            assert parse_spanish_decimal(raw) == expected, case_id


class TestSpanishAmountGroupRegex:
    """Capture-group behaviour of :data:`SPANISH_AMOUNT_GROUP`."""

    def test_regex_captures_nbsp_thousands(self) -> None:
        """The regex captures both dot-separated and NBSP-separated thousands."""
        pattern = re.compile(rf"(?m)^\s*01\s.*?{SPANISH_AMOUNT_GROUP}")
        cases: tuple[tuple[str, str, Decimal], ...] = (
            ("dot-sep", "01 Ingresos 1.234,56", Decimal("1234.56")),
            ("nbsp", "01 Ingresos 1\xa0234,56", Decimal("1234.56")),  # U+00A0 NBSP
        )

        for case_id, line, expected in cases:
            match = pattern.search(line)
            assert match is not None, f"{case_id}: regex failed to match {line!r}"
            assert parse_spanish_decimal(match.group(1)) == expected, case_id

    def test_regex_does_not_cross_column_ascii_space(self) -> None:
        """ASCII column-separator whitespace must not act as a thousands separator.

        Otherwise ``03 400,00`` (casilla ref + value on one line)
        would collapse into ``3400,00``.
        """
        pattern = re.compile(rf"(?m)^\s*04\s.*?{SPANISH_AMOUNT_GROUP}")
        text = "04 2 por ciento s/casilla 03 400,00"
        match = pattern.search(text)
        assert match is not None
        assert parse_spanish_decimal(match.group(1)) == Decimal("400.00")
