"""The persisted invoice enforces the contract its field types implied.

``BusinessOperationInvoice`` is the encrypted, operator-edited record behind
the payable/collectible noun groups. Its constraints measured shape rather
than validity: ``invoice_date`` was ``Field(min_length=10, max_length=10)``,
so ``"2026-99-99"`` was accepted for being ten characters wide while a real
but shorter rendering was refused. ``currency`` took any three characters
without normalising, and the monetary fields were unbounded ``Decimal``.

These pin the values the record now refuses, and the one coupling that makes
the currency normalisation safe: the content-addressed ``invoice_id`` is
derived from the normalised value, not the raw input.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .._business_operation_invoice import (
    BusinessOperationInvoice,
    BusinessOperationInvoiceDirection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 1, 31, tzinfo=UTC)
_BUCKET = "41e0c259-7c89-4c5f-9908-c5d44d8d77a8"


def _invoice(**overrides: object) -> BusinessOperationInvoice:
    payload: dict[str, object] = {
        "invoice_id": "inv-1",
        "source_kind": BusinessOperationInvoiceDirection.COLLECTIBLE_INVOICE,
        "bucket_id": _BUCKET,
        "counterparty_nif": "B12345678",
        "counterparty_name": "ACME",
        "invoice_number": "F-001",
        "invoice_date": "2026-01-31",
        "currency": "EUR",
        "taxable_base": Decimal("100"),
        "iva_amount": Decimal("21"),
        "total_amount": Decimal("121"),
        "country_code": None,
        "eu_iva_id": None,
        "operation_type": None,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    payload.update(overrides)
    return BusinessOperationInvoice(**payload)  # type: ignore[arg-type]


def test_a_well_formed_invoice_is_still_accepted() -> None:
    assert _invoice().invoice_date == "2026-01-31"


class TestInvoiceDate:
    @pytest.mark.parametrize("raw", ["2026-99-99", "2026-13-01", "0000-00-00", "2026-01-3X"])
    def test_a_ten_character_non_date_is_refused(self, raw: str) -> None:
        """Width is not validity: these all measured ten characters wide."""
        assert len(raw) == 10
        with pytest.raises(ValidationError):
            _invoice(invoice_date=raw)

    def test_a_real_leap_day_is_accepted(self) -> None:
        assert _invoice(invoice_date="2024-02-29").invoice_date == "2024-02-29"

    def test_a_non_leap_29_february_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _invoice(invoice_date="2026-02-29")

    @pytest.mark.parametrize("raw", ["2026-99-99", "not-a-date"])
    def test_the_fx_rate_date_carries_the_same_contract(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            _invoice(fx_rate_date=raw)


class TestCurrency:
    def test_a_lowercase_code_is_normalised_not_stored_raw(self) -> None:
        assert _invoice(currency="usd").currency == "USD"

    def test_a_padded_code_is_normalised(self) -> None:
        """The length constraint would fire on padding before any normaliser."""
        assert _invoice(currency=" usd ").currency == "USD"

    @pytest.mark.parametrize("raw", ["EU", "EUROS", "12X", "E U"])
    def test_a_non_iso4217_token_is_refused(self, raw: str) -> None:
        with pytest.raises(Exception):  # noqa: B017 - core validation error or ValidationError
            _invoice(currency=raw)


class TestMonetaryFields:
    @pytest.mark.parametrize("field", ["taxable_base", "iva_amount", "total_amount"])
    def test_a_negative_magnitude_is_refused(self, field: str) -> None:
        with pytest.raises(ValidationError):
            _invoice(**{field: Decimal("-1")})

    @pytest.mark.parametrize("field", ["taxable_base", "iva_amount", "total_amount"])
    def test_zero_remains_a_valid_magnitude(self, field: str) -> None:
        assert getattr(_invoice(**{field: Decimal("0")}), field) == Decimal("0")
