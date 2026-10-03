from datetime import date
from decimal import Decimal

import pytest

from ..models import (
    CurrencyNormalizationStatus,
    EurRateLookup,
    EurRateLookupStatus,
    MonetaryAmount,
)
from ..service import CurrencyNormalizationService, resolve_fx_conversion_stamp
from .fx_lookup import eur_rate_lookup

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# Published ECB euro reference rate for 2025-03-14 (EUR-base: 1 EUR = 1.0889 USD).
_ECB_2025_03_14_USD_QUOTE = Decimal("1.0889")
_ECB_2025_03_14_USD_RATE = Decimal("1") / _ECB_2025_03_14_USD_QUOTE
_RATE_DATE = date(2025, 3, 14)
_RATE_SOURCE_ID = "test_reference"


class _StaticRateProvider:
    """Domain-protocol fake; ECB transport behaviour belongs to adapter tests."""

    rate_source_id = _RATE_SOURCE_ID

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        return eur_rate_lookup(self._rate(currency, rate_date), rate_date=rate_date, source=self.rate_source_id)

    def _rate(self, currency: str, rate_date: date) -> Decimal | None:
        if currency == "USD" and rate_date == _RATE_DATE:
            return _ECB_2025_03_14_USD_RATE
        return None


def _provider() -> _StaticRateProvider:
    return _StaticRateProvider()


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
    # No euro amount at all: a zero would read as a converted figure.
    assert result.eur_amount is None
    assert result.original == amount


def test_currency_normalization_missing_rate() -> None:
    # A currency the ECB publishes no series for resolves to no rate at all.
    svc = CurrencyNormalizationService(rate_provider=_provider())
    amount = MonetaryAmount(amount=Decimal("100.00"), currency="XYZ")
    result = svc.normalize(amount, _RATE_DATE)

    assert result.status == CurrencyNormalizationStatus.MISSING_RATE
    # No euro amount at all: a zero would read as a converted figure.
    assert result.eur_amount is None
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
    assert result.rate_source == _RATE_SOURCE_ID
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


class _UnsupportedCurrencyProvider:
    rate_source_id = _RATE_SOURCE_ID

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        return EurRateLookup(
            status=EurRateLookupStatus.UNSUPPORTED_CURRENCY, rate_date=rate_date, source=_RATE_SOURCE_ID
        )


class _WeekendProvider:
    """Answers a Sunday request with the Friday publication, as the ECB does."""

    rate_source_id = _RATE_SOURCE_ID

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        return eur_rate_lookup(
            _ECB_2025_03_14_USD_RATE, rate_date=rate_date, source=_RATE_SOURCE_ID, observation_date=_RATE_DATE
        )


def test_an_unsupported_currency_normalizes_to_no_euro_amount() -> None:
    svc = CurrencyNormalizationService(rate_provider=_UnsupportedCurrencyProvider())

    result = svc.normalize(MonetaryAmount(amount=Decimal("100.00"), currency="XYZ"), _RATE_DATE)

    assert result.status == CurrencyNormalizationStatus.UNSUPPORTED_CURRENCY
    assert result.eur_amount is None


def test_a_weekend_conversion_records_the_publication_it_used() -> None:
    sunday = date(2025, 3, 16)
    svc = CurrencyNormalizationService(rate_provider=_WeekendProvider())

    result = svc.normalize(MonetaryAmount(amount=Decimal("100.00"), currency="USD"), sunday)
    stamp = resolve_fx_conversion_stamp(currency="USD", on_date=sunday, rate_provider=_WeekendProvider())

    assert result.rate_date == sunday
    assert result.rate_observation_date == _RATE_DATE
    assert stamp is not None
    assert (stamp.rate_date, stamp.observation_date) == (sunday, _RATE_DATE)


def test_an_unresolvable_rate_leaves_the_record_unstamped() -> None:
    assert (
        resolve_fx_conversion_stamp(currency="XYZ", on_date=_RATE_DATE, rate_provider=_UnsupportedCurrencyProvider())
        is None
    )


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"status": EurRateLookupStatus.FOUND}, "carries its rate and observation date"),
        (
            {"status": EurRateLookupStatus.FOUND, "rate": Decimal("1.1"), "observation_date": date(2025, 3, 15)},
            "cannot postdate",
        ),
        (
            {"status": EurRateLookupStatus.FOUND, "rate": Decimal("0"), "observation_date": _RATE_DATE},
            "strictly positive",
        ),
        ({"status": EurRateLookupStatus.MISSING_RATE, "rate": Decimal("1.1")}, "only a found rate"),
    ],
)
def test_an_incoherent_lookup_is_refused(fields: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        EurRateLookup.model_validate({"rate_date": _RATE_DATE, "source": _RATE_SOURCE_ID, **fields})
