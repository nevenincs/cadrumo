"""Unit tests for the shared label-regex primitive.

Covers the Spanish-decimal parser, the ``SPANISH_AMOUNT_GROUP``
regex (including its NBSP-thousands acceptance and the column-
separator rejection guard), the :func:`apply_label_regex`
first-match-wins / ``match_count`` semantics, and the
strict + frozen :class:`LabelHit` shape.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .. import SPANISH_AMOUNT_GROUP, LabelHit, apply_label_regex, parse_spanish_decimal

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]
_TEST_LABEL_CASILLA: CasillaId = validated_casilla_id("01", surface="_TEST_LABEL_CASILLA")


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
            hits = apply_label_regex(line, {"01": pattern})
            assert "01" in hits, f"{case_id}: regex failed to match {line!r}"
            assert hits["01"].decimal_value == expected, case_id

    def test_regex_does_not_cross_column_ascii_space(self) -> None:
        """ASCII column-separator whitespace must not act as a thousands separator.

        Otherwise ``03 400,00`` (casilla ref + value on one line)
        would collapse into ``3400,00``.
        """
        pattern = re.compile(rf"(?m)^\s*04\s.*?{SPANISH_AMOUNT_GROUP}")
        text = "04 2 por ciento s/casilla 03 400,00"
        hits = apply_label_regex(text, {"04": pattern})
        assert hits["04"].decimal_value == Decimal("400.00")


class TestApplyLabelRegex:
    """Dispatch semantics of :func:`apply_label_regex`."""

    def test_first_match_wins(self) -> None:
        """When a label matches twice, the first hit wins."""
        pattern = re.compile(rf"(?m)^\s*01\s.*?{SPANISH_AMOUNT_GROUP}")
        text = "01 Ingresos 10.000,00\n01 Ingresos duplicados 99,99"
        hits = apply_label_regex(text, {"01": pattern})
        assert "01" in hits
        assert hits["01"].raw_value == "10.000,00"
        assert hits["01"].decimal_value == Decimal("10000.00")

    def test_match_count_reports_ambiguity(self) -> None:
        """``match_count`` reports the number of regex hits for a label."""
        pattern = re.compile(rf"(?m)^\s*01\s.*?{SPANISH_AMOUNT_GROUP}")
        text = "01 Ingresos 10.000,00\n01 Duplicado 99,99"
        hits = apply_label_regex(text, {"01": pattern})
        assert hits["01"].match_count == 2

    def test_missing_pattern_absent_from_output(self) -> None:
        """A label whose pattern matches nothing is absent from the output."""
        pattern = re.compile(rf"(?m)^\s*02\s.*?{SPANISH_AMOUNT_GROUP}")
        hits = apply_label_regex("01 Ingresos 10,00", {"02": pattern})
        assert hits == {}


class TestLabelHitShape:
    """Strict + frozen invariants of :class:`LabelHit`."""

    def test_frozen_dataclass(self) -> None:
        """Mutating an attribute on a frozen :class:`LabelHit` raises."""
        hit = LabelHit(
            casilla_id=_TEST_LABEL_CASILLA,
            raw_value="10,00",
            decimal_value=Decimal("10.00"),
            match_count=1,
        )
        _attr = "casilla_id"
        with pytest.raises(AttributeError, match=r"frozen|cannot|casilla_id"):
            setattr(hit, _attr, "02")
