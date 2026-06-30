from datetime import date
from decimal import Decimal

import pytest

from ....adapters.outbound.fx import EcbReferenceRateProvider
from .._models import (
    CurrencyNormalizationStatus,
    MonetaryAmount,
)
from .._service import CurrencyNormalizationService

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_ECB_2026_01_02_USD_QUOTE = Decimal("1.1700")
_ECB_2026_01_02_USD_RATE = Decimal("1") / _ECB_2026_01_02_USD_QUOTE


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
    svc = CurrencyNormalizationService(rate_provider=EcbReferenceRateProvider())
    amount = MonetaryAmount(amount=Decimal("100.00"), currency="JPY")
    result = svc.normalize(amount, date(2026, 1, 2))

    assert result.status == CurrencyNormalizationStatus.MISSING_RATE
    assert result.eur_amount == Decimal("0.0")
    assert result.original == amount


def test_currency_normalization_success() -> None:
    svc = CurrencyNormalizationService(rate_provider=EcbReferenceRateProvider())
    amount = MonetaryAmount(amount=Decimal("100.00"), currency="USD")
    result = svc.normalize(amount, date(2026, 1, 2))

    assert result.status == CurrencyNormalizationStatus.NORMALIZED
    assert result.eur_amount == Decimal("85.47")
    assert result.rate == _ECB_2026_01_02_USD_RATE
    assert result.rate_source == "provider"
    assert result.original == amount
