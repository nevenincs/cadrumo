"""Unit tests for the Spanish-locale decimal parser."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._decimal import parse_decimal
from ._errors import HistoryParseError

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


class TestParseDecimal:
    def test_spanish_locale_with_thousands(self) -> None:
        assert parse_decimal("1.234,56") == Decimal("1234.56")

    def test_spanish_locale_without_thousands(self) -> None:
        assert parse_decimal("1234,56") == Decimal("1234.56")

    def test_english_locale(self) -> None:
        assert parse_decimal("1234.56") == Decimal("1234.56")

    def test_zero(self) -> None:
        assert parse_decimal("0,00") == Decimal("0.00")

    def test_large_value(self) -> None:
        assert parse_decimal("1.234.567,89") == Decimal("1234567.89")

    def test_strips_whitespace(self) -> None:
        assert parse_decimal("  123,45  ") == Decimal("123.45")

    def test_negative(self) -> None:
        assert parse_decimal("-1.234,56") == Decimal("-1234.56")

    def test_empty_raises(self) -> None:
        with pytest.raises(HistoryParseError):
            parse_decimal("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(HistoryParseError):
            parse_decimal("   ")

    def test_garbage_raises(self) -> None:
        with pytest.raises(HistoryParseError):
            parse_decimal("not a number")
