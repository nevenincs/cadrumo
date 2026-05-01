"""Unit tests for the shared label-regex primitive (#305 refactor)."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from . import SPANISH_AMOUNT_GROUP, LabelHit, apply_label_regex, parse_spanish_decimal

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


class TestParseSpanishDecimal:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1.234,56", Decimal("1234.56")),
            ("0,00", Decimal("0.00")),
            ("-42,50", Decimal("-42.50")),
            ("1.000.000,00", Decimal("1000000.00")),
            ("1234.56", Decimal("1234.56")),
            ("", None),
            ("-", None),
            ("not a number", None),
        ],
    )
    def test_parses(self, raw: str, expected: Decimal | None) -> None:
        assert parse_spanish_decimal(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # parse_spanish_decimal() tolerates every unicode
            # whitespace variant (including ASCII / tab) for robustness
            # on messy input. The REGEX capture is stricter (NBSP / narrow
            # NBSP only — see TestSpanishAmountGroupRegex) to avoid
            # crossing column-separator whitespace on AEAT PDFs.
            ("1\xa0234,56", Decimal("1234.56")),  # U+00A0 non-breaking space
            ("1 234,56", Decimal("1234.56")),  # ASCII space — parse tolerates
            ("1\t234,56", Decimal("1234.56")),  # tab — parse tolerates
        ],
        ids=["nbsp", "ascii-space", "tab"],
    )
    def test_parses_whitespace_thousands_separator(self, raw: str, expected: Decimal) -> None:
        assert parse_spanish_decimal(raw) == expected


class TestSpanishAmountGroupRegex:
    """the regex must capture NBSP-separated thousands."""

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("01 Ingresos 1.234,56", Decimal("1234.56")),
            ("01 Ingresos 1\xa0234,56", Decimal("1234.56")),  # U+00A0 NBSP
        ],
        ids=["dot-sep", "nbsp"],
    )
    def test_regex_captures_nbsp_thousands(self, line: str, expected: Decimal) -> None:
        pattern = re.compile(rf"(?m)^\s*01\s.*?{SPANISH_AMOUNT_GROUP}")
        hits = apply_label_regex(line, {"01": pattern})
        assert "01" in hits, f"regex failed to match {line!r}"
        assert hits["01"].decimal_value == expected

    def test_regex_does_not_cross_column_ascii_space(self) -> None:
        """Regression guard: the regex must NOT treat ASCII
        column-separator whitespace as a thousands separator — that
        would collapse `03 400,00` (casilla ref + value on one line)
        into `3400,00`.
        """
        pattern = re.compile(rf"(?m)^\s*04\s.*?{SPANISH_AMOUNT_GROUP}")
        text = "04 2 por ciento s/casilla 03 400,00"
        hits = apply_label_regex(text, {"04": pattern})
        assert hits["04"].decimal_value == Decimal("400.00")


class TestApplyLabelRegex:
    def test_first_match_wins(self) -> None:
        pattern = re.compile(rf"(?m)^\s*01\s.*?{SPANISH_AMOUNT_GROUP}")
        text = "01 Ingresos 10.000,00\n01 Ingresos duplicados 99,99"
        hits = apply_label_regex(text, {"01": pattern})
        assert "01" in hits
        assert hits["01"].raw_value == "10.000,00"
        assert hits["01"].decimal_value == Decimal("10000.00")

    def test_match_count_reports_ambiguity(self) -> None:
        pattern = re.compile(rf"(?m)^\s*01\s.*?{SPANISH_AMOUNT_GROUP}")
        text = "01 Ingresos 10.000,00\n01 Duplicado 99,99"
        hits = apply_label_regex(text, {"01": pattern})
        assert hits["01"].match_count == 2

    def test_missing_pattern_absent_from_output(self) -> None:
        pattern = re.compile(rf"(?m)^\s*02\s.*?{SPANISH_AMOUNT_GROUP}")
        hits = apply_label_regex("01 Ingresos 10,00", {"02": pattern})
        assert hits == {}


class TestLabelHitShape:
    def test_frozen_dataclass(self) -> None:
        hit = LabelHit(
            casilla_id="01",
            raw_value="10,00",
            decimal_value=Decimal("10.00"),
            match_count=1,
        )
        with pytest.raises(AttributeError):
            hit.casilla_id = "02"  # type: ignore[misc,assignment]  # ty: ignore[invalid-assignment]
