from datetime import date
from decimal import Decimal

import pytest

from ....adapters.outbound.fx._ecb_provider import ECB_RATE_SOURCE_ID, EcbReferenceRateProvider
from ....tests.ecb_stub import ecb_csv_fetch
from ..models import (
    CurrencyNormalizationStatus,
    MonetaryAmount,
)
from ..service import CurrencyNormalizationService

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# Published ECB euro reference rate for 2025-03-14 (EUR-base: 1 EUR = 1.0889 USD).
_ECB_2025_03_14_USD_QUOTE = Decimal("1.0889")
_ECB_2025_03_14_USD_RATE = Decimal("1") / _ECB_2025_03_14_USD_QUOTE
_RATE_DATE = date(2025, 3, 14)


def _provider() -> EcbReferenceRateProvider:
    return EcbReferenceRateProvider(fetch=ecb_csv_fetch({"USD": {_RATE_DATE: _ECB_2025_03_14_USD_QUOTE}}))


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
    # A currency the ECB publishes no series for resolves to no rate at all.
    svc = CurrencyNormalizationService(rate_provider=_provider())
    amount = MonetaryAmount(amount=Decimal("100.00"), currency="XYZ")
    result = svc.normalize(amount, _RATE_DATE)

    assert result.status == CurrencyNormalizationStatus.MISSING_RATE
    assert result.eur_amount == Decimal("0.0")
    assert result.original == amount


def test_currency_normalization_success() -> None:
    svc = CurrencyNormalizationService(rate_provider=_provider())
    amount = MonetaryAmount(amount=Decimal("100.00"), currency="USD")
    result = svc.normalize(amount, _RATE_DATE)

    assert result.status == CurrencyNormalizationStatus.NORMALIZED
    assert result.eur_amount == (Decimal("100.00") * _ECB_2025_03_14_USD_RATE).quantize(Decimal("0.01"))
    assert result.rate == _ECB_2025_03_14_USD_RATE
    # The rate authority by name, not the bare fact that a provider answered:
    # "provider" duplicated the NORMALIZED status and named nothing an auditor
    # could re-fetch the observation from.
    assert result.rate_source == ECB_RATE_SOURCE_ID
    assert result.original == amount


@pytest.mark.parametrize("raw_currency", ["eur", " eur ", "Eur"])
def test_monetary_amount_normalises_lowercase_and_padded_currency_on_construction(raw_currency: str) -> None:
    # The field itself carries the canonical token from construction, so any
    # later raw-equality comparison (CurrencyNormalizationService.normalize's
    # DEFAULT_CURRENCY check) cannot misclassify it as a foreign currency.
    amount = MonetaryAmount(amount=Decimal("100.00"), currency=raw_currency)
    assert amount.currency == "EUR"


@pytest.mark.parametrize("raw_currency", ["eur", " eur ", "Eur"])
def test_currency_normalization_lowercase_and_padded_native_eur(raw_currency: str) -> None:
    svc = CurrencyNormalizationService()
    amount = MonetaryAmount(amount=Decimal("100.00"), currency=raw_currency)
    result = svc.normalize(amount, date(2026, 1, 1))

    assert result.status == CurrencyNormalizationStatus.NATIVE_EUR
    assert result.eur_amount == Decimal("100.00")
    assert result.rate == Decimal("1.0")
    assert result.rate_source == "native"


def test_currency_normalization_padded_foreign_currency_resolves_the_same_rate() -> None:
    svc = CurrencyNormalizationService(rate_provider=_provider())
    canonical = svc.normalize(MonetaryAmount(amount=Decimal("100.00"), currency="USD"), _RATE_DATE)
    padded = svc.normalize(MonetaryAmount(amount=Decimal("100.00"), currency=" usd "), _RATE_DATE)

    assert padded.status == CurrencyNormalizationStatus.NORMALIZED
    assert padded.original.currency == "USD"
    assert padded.rate == canonical.rate
    assert padded.eur_amount == canonical.eur_amount
