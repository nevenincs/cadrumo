from datetime import date
from decimal import Decimal
from typing import override

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

from .._models import (
    CurrencyNormalizationStatus,
    MonetaryAmount,
)
from .._service import CurrencyNormalizationService, ExchangeRateProvider


class _TableRateProvider(ExchangeRateProvider):
    @override
    def get_eur_rate(self, currency: str, rate_date: date) -> Decimal | None:
        if currency == "USD":
            return Decimal("0.85")
        if currency == "GBP":
            return Decimal("1.15")
        return None


def test_currency_normalization_native_eur() -> None:
    svc = CurrencyNormalizationService()
    amount = MonetaryAmount(amount=Decimal("100.00"), currency="EUR")
    result = svc.normalize(amount, date(2026, 1, 1))

    assert result.status == CurrencyNormalizationStatus.NATIVE_EUR
    assert result.eur_amount == Decimal("100.00")
    assert result.rate == Decimal("1.0")
    assert result.rate_source == "native"
    assert result.original == amount


def test_currency_normalization_missing_provider() -> None:
    svc = CurrencyNormalizationService(rate_provider=None)
    amount = MonetaryAmount(amount=Decimal("100.00"), currency="USD")
    result = svc.normalize(amount, date(2026, 1, 1))

    assert result.status == CurrencyNormalizationStatus.MISSING_RATE
    assert result.eur_amount == Decimal("0.0")
    assert result.original == amount


def test_currency_normalization_missing_rate() -> None:
    svc = CurrencyNormalizationService(rate_provider=_TableRateProvider())
    amount = MonetaryAmount(amount=Decimal("100.00"), currency="JPY")
    result = svc.normalize(amount, date(2026, 1, 1))

    assert result.status == CurrencyNormalizationStatus.MISSING_RATE
    assert result.eur_amount == Decimal("0.0")
    assert result.original == amount


def test_currency_normalization_success() -> None:
    svc = CurrencyNormalizationService(rate_provider=_TableRateProvider())
    amount = MonetaryAmount(amount=Decimal("100.00"), currency="USD")
    result = svc.normalize(amount, date(2026, 1, 1))

    assert result.status == CurrencyNormalizationStatus.NORMALIZED
    assert result.eur_amount == Decimal("85.00")
    assert result.rate == Decimal("0.85")
    assert result.rate_source == "provider"
    assert result.original == amount
