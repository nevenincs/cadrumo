"""Tests for the ECB euro reference-rate provider."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....domain.currency.errors import ExchangeRateProviderError
from .....domain.currency.models import CurrencyNormalizationStatus, MonetaryAmount
from .....domain.currency.service import CurrencyNormalizationService
from .....tests.ecb_stub import ecb_csv_fetch
from .._ecb_provider import EcbReferenceRateProvider, _observation_url, default_ecb_rate_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# Published ECB euro reference rates (EUR-base: 1 EUR = quote CCY).
# Source: ECB Data Portal series D.<CCY>.EUR.SP00.A.
# 2025-03-14 was a Friday; 2025-03-15/16 fell on a weekend, so the ECB published
# no rate on either -- the fallback dates below rely on that real calendar gap.
_ECB_QUOTES = {
    "USD": {
        date(2025, 3, 13): Decimal("1.0830"),
        date(2025, 3, 14): Decimal("1.0889"),
    },
    "GBP": {
        date(2025, 3, 13): Decimal("0.83778"),
        date(2025, 3, 14): Decimal("0.84183"),
    },
}


@pytest.fixture
def provider() -> EcbReferenceRateProvider:
    return EcbReferenceRateProvider(fetch=ecb_csv_fetch(_ECB_QUOTES))


def test_eur_is_identity(provider: EcbReferenceRateProvider) -> None:
    assert provider.get_eur_rate("EUR", date(2025, 3, 14)) == Decimal("1")


def test_get_eur_rate_inverts_ecb_eur_base_quote(provider: EcbReferenceRateProvider) -> None:
    # 1 EUR = 1.0889 USD -> USD->EUR = 1/1.0889.
    assert provider.get_eur_rate("USD", date(2025, 3, 14)) == Decimal("1") / Decimal("1.0889")
    # 1 EUR = 0.84183 GBP -> GBP->EUR = 1/0.84183 (>1, since GBP is stronger).
    rate = provider.get_eur_rate("GBP", date(2025, 3, 14))
    assert rate is not None
    assert rate == Decimal("1") / Decimal("0.84183")
    assert rate > Decimal("1")


def test_non_publication_date_falls_back_to_prior_working_day(
    provider: EcbReferenceRateProvider,
) -> None:
    # 2025-03-16 was a Sunday; the ECB published no rate, so the most recent
    # prior publication (Friday the 14th) applies -- not Thursday the 13th.
    on_sunday = provider.get_eur_rate("USD", date(2025, 3, 16))
    assert on_sunday == Decimal("1") / Decimal("1.0889")
    assert on_sunday != Decimal("1") / Decimal("1.0830")


def test_currency_the_ecb_does_not_publish_returns_none(
    provider: EcbReferenceRateProvider,
) -> None:
    assert provider.get_eur_rate("XYZ", date(2025, 3, 14)) is None


def test_date_outside_the_lookback_window_returns_none(
    provider: EcbReferenceRateProvider,
) -> None:
    # Far earlier than any published observation: the widened window is empty.
    assert provider.get_eur_rate("USD", date(2024, 12, 1)) is None


@pytest.mark.parametrize("currency", ("usd", " usd "))
def test_observation_url_normalises_currency_before_constructing_the_ecb_path(currency: str) -> None:
    assert _observation_url(currency, date(2025, 3, 1), date(2025, 3, 14)) == (
        "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
        "?startPeriod=2025-03-01&endPeriod=2025-03-14&format=csvdata"
    )


@pytest.mark.parametrize("currency", ("USD/../../EVIL", "USD?evil=1", "US D", "US", "USDD"))
def test_observation_url_refuses_malformed_currency_before_constructing_the_ecb_path(currency: str) -> None:
    with pytest.raises(ExchangeRateProviderError, match="three-letter ISO 4217 code"):
        _observation_url(currency, date(2025, 3, 1), date(2025, 3, 14))


def _transport_that_must_not_be_reached(url: str) -> str:
    """A :data:`RateFetch` proving the currency refusal precedes any transport call."""
    raise AssertionError(f"provider issued a request for a refused currency: {url!r}")


@pytest.mark.parametrize("currency", ("USD/../../EVIL", "USD?evil=1"))
def test_provider_refuses_path_containing_currency_before_lookup(currency: str) -> None:
    provider = EcbReferenceRateProvider(fetch=_transport_that_must_not_be_reached)

    with pytest.raises(ExchangeRateProviderError, match="three-letter ISO 4217 code"):
        provider.get_eur_rate(currency, date(2025, 3, 14))


def test_resolved_rates_are_memoized_per_currency_and_date() -> None:
    calls: list[str] = []
    inner = ecb_csv_fetch(_ECB_QUOTES)

    def counting_fetch(url: str) -> str:
        calls.append(url)
        return inner(url)

    provider = EcbReferenceRateProvider(fetch=counting_fetch)
    first = provider.get_eur_rate("USD", date(2025, 3, 14))
    second = provider.get_eur_rate("USD", date(2025, 3, 14))

    assert first == second
    assert len(calls) == 1, "a repeated (currency, date) lookup must not re-query the ECB"


def test_transport_failure_raises_rather_than_reporting_a_missing_rate() -> None:
    # A network fault must be distinguishable from "the ECB publishes no such
    # rate": collapsing the two would silently book the row at zero EUR.
    def failing_fetch(url: str) -> str:
        msg = "connection reset"
        raise ExchangeRateProviderError(msg)

    provider = EcbReferenceRateProvider(fetch=failing_fetch)
    with pytest.raises(ExchangeRateProviderError):
        provider.get_eur_rate("USD", date(2025, 3, 14))


def test_default_provider_is_cached() -> None:
    assert default_ecb_rate_provider() is default_ecb_rate_provider()


def test_normalizer_converts_gbp_to_eur_via_provider() -> None:
    # End-to-end: the service multiplies amount * get_eur_rate, so a GBP amount
    # converts to a larger EUR amount (GBP stronger than EUR).
    service = CurrencyNormalizationService(rate_provider=EcbReferenceRateProvider(fetch=ecb_csv_fetch(_ECB_QUOTES)))
    result = service.normalize(MonetaryAmount(amount=Decimal("1000.00"), currency="GBP"), date(2025, 3, 14))
    assert result.status is CurrencyNormalizationStatus.NORMALIZED
    assert result.eur_amount == (Decimal("1000.00") * (Decimal("1") / Decimal("0.84183"))).quantize(Decimal("0.01"))
    assert result.eur_amount > Decimal("1000.00")
