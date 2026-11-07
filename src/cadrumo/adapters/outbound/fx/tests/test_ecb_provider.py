"""Tests for the ECB euro reference-rate provider."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest

from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.currency.errors import ExchangeRateProviderError
from .....domain.currency.models import CurrencyNormalizationStatus, EurRateLookupStatus, MonetaryAmount
from .....domain.currency.service import CurrencyNormalizationService
from .....tests.ecb_stub import ecb_csv_fetch
from .. import ecb_provider
from ..ecb_provider import EcbReferenceRateProvider, default_ecb_rate_provider, observation_url

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# Euro reference rates in the shape the ECB Data Portal publishes them (EUR-base: 1 EUR = quote CCY).
# The ECB publishes on working days only. The Friday below is followed by a weekend with no
# publication, so the fallback dates rely on that calendar gap; the Friday is found from the
# calendar rather than assumed to keep its weekday from year to year.
_YEAR = filing_year_envelope().horizon


def _friday_on_or_after(day: date) -> date:
    return day + timedelta(days=(4 - day.weekday()) % 7)


_FRIDAY = _friday_on_or_after(date(_YEAR, 3, 14))
_THURSDAY = _FRIDAY - timedelta(days=1)
_SUNDAY = _FRIDAY + timedelta(days=2)
_MONTH_START = _FRIDAY.replace(day=1)
_ECB_QUOTES = {
    "USD": {
        _THURSDAY: Decimal("1.0830"),
        _FRIDAY: Decimal("1.0889"),
    },
    "GBP": {
        _THURSDAY: Decimal("0.83778"),
        _FRIDAY: Decimal("0.84183"),
    },
}


@pytest.fixture
def provider() -> EcbReferenceRateProvider:
    return EcbReferenceRateProvider(fetch=ecb_csv_fetch(_ECB_QUOTES))


def test_eur_is_identity(provider: EcbReferenceRateProvider) -> None:
    lookup = provider.lookup_eur_rate("EUR", _FRIDAY)

    assert lookup.status is EurRateLookupStatus.FOUND
    assert lookup.rate == Decimal("1")
    assert lookup.observation_date == _FRIDAY


def test_lookup_inverts_ecb_eur_base_quote(provider: EcbReferenceRateProvider) -> None:
    # 1 EUR = 1.0889 USD -> USD->EUR = 1/1.0889.
    assert provider.lookup_eur_rate("USD", _FRIDAY).rate == Decimal("1") / Decimal("1.0889")
    # 1 EUR = 0.84183 GBP -> GBP->EUR = 1/0.84183 (>1, since GBP is stronger).
    rate = provider.lookup_eur_rate("GBP", _FRIDAY).rate
    assert rate is not None
    assert rate == Decimal("1") / Decimal("0.84183")
    assert rate > Decimal("1")


def test_non_publication_date_falls_back_to_prior_working_day_and_names_it(
    provider: EcbReferenceRateProvider,
) -> None:
    # The Sunday after the Friday; the ECB published no rate, so the most recent
    # prior publication (the Friday) applies -- not the Thursday before it --
    # and the lookup records Friday as the observation it used.
    on_sunday = provider.lookup_eur_rate("USD", _SUNDAY)

    assert on_sunday.rate == Decimal("1") / Decimal("1.0889")
    assert on_sunday.rate != Decimal("1") / Decimal("1.0830")
    assert on_sunday.rate_date == _SUNDAY
    assert on_sunday.observation_date == _FRIDAY


def test_currency_the_ecb_does_not_publish_is_unsupported_not_missing(
    provider: EcbReferenceRateProvider,
) -> None:
    lookup = provider.lookup_eur_rate("XYZ", _FRIDAY)

    assert lookup.status is EurRateLookupStatus.UNSUPPORTED_CURRENCY
    assert lookup.rate is None
    assert lookup.observation_date is None


def test_date_outside_the_lookback_window_is_a_missing_rate(
    provider: EcbReferenceRateProvider,
) -> None:
    # Far earlier than any published observation: the widened window is empty.
    lookup = provider.lookup_eur_rate("USD", date(_YEAR - 1, 12, 1))

    assert lookup.status is EurRateLookupStatus.MISSING_RATE
    assert lookup.rate is None


@pytest.mark.parametrize("currency", ("usd", " usd "))
def test_observation_url_normalises_currency_before_constructing_the_ecb_path(currency: str) -> None:
    assert observation_url(currency, _MONTH_START, _FRIDAY) == (
        "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
        f"?startPeriod={_MONTH_START.isoformat()}&endPeriod={_FRIDAY.isoformat()}&format=csvdata"
    )


@pytest.mark.parametrize("currency", ("USD/../../EVIL", "USD?evil=1", "US D", "US", "USDD"))
def test_observation_url_refuses_malformed_currency_before_constructing_the_ecb_path(currency: str) -> None:
    with pytest.raises(ExchangeRateProviderError, match="three-letter ISO 4217 code"):
        observation_url(currency, _MONTH_START, _FRIDAY)


def _transport_that_must_not_be_reached(url: str) -> str:
    """A :data:`RateFetch` proving the currency refusal precedes any transport call."""
    raise AssertionError(f"provider issued a request for a refused currency: {url!r}")


@pytest.mark.parametrize("currency", ("USD/../../EVIL", "USD?evil=1"))
def test_provider_refuses_path_containing_currency_before_lookup(currency: str) -> None:
    provider = EcbReferenceRateProvider(fetch=_transport_that_must_not_be_reached)

    with pytest.raises(ExchangeRateProviderError, match="three-letter ISO 4217 code"):
        provider.lookup_eur_rate(currency, _FRIDAY)


def test_resolved_rates_are_memoized_per_currency_and_date() -> None:
    calls: list[str] = []
    inner = ecb_csv_fetch(_ECB_QUOTES)

    def counting_fetch(url: str) -> str | None:
        calls.append(url)
        return inner(url)

    provider = EcbReferenceRateProvider(fetch=counting_fetch)
    first = provider.lookup_eur_rate("USD", _FRIDAY)
    second = provider.lookup_eur_rate("USD", _FRIDAY)

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
        provider.lookup_eur_rate("USD", _FRIDAY)


@pytest.mark.parametrize(("status", "outcome"), ((404, None), (200, "body")))
def test_the_live_transport_reports_an_unpublished_series_as_none(
    monkeypatch: pytest.MonkeyPatch, status: int, outcome: str | None
) -> None:
    """The Data Portal answers HTTP 404 for a series it does not publish; that is an answer, not a fault."""
    real_client = httpx.Client

    def scripted_client(**kwargs: object) -> httpx.Client:
        return real_client(transport=httpx.MockTransport(lambda request: httpx.Response(status, text="body")))

    monkeypatch.setattr(httpx, "Client", scripted_client)

    url = observation_url("XYZ", _MONTH_START, _FRIDAY)
    assert ecb_provider.https_fetch(url) == outcome


def test_the_live_transport_still_raises_on_a_server_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    real_client = httpx.Client

    def scripted_client(**kwargs: object) -> httpx.Client:
        return real_client(transport=httpx.MockTransport(lambda request: httpx.Response(503)))

    monkeypatch.setattr(httpx, "Client", scripted_client)

    with pytest.raises(ExchangeRateProviderError):
        ecb_provider.https_fetch(observation_url("USD", _MONTH_START, _FRIDAY))


def test_default_provider_is_cached() -> None:
    assert default_ecb_rate_provider() is default_ecb_rate_provider()


def test_normalizer_converts_gbp_to_eur_via_provider() -> None:
    # End-to-end: the service multiplies amount * rate, so a GBP amount converts
    # to a larger EUR amount (GBP stronger than EUR).
    service = CurrencyNormalizationService(rate_provider=EcbReferenceRateProvider(fetch=ecb_csv_fetch(_ECB_QUOTES)))
    result = service.normalize(MonetaryAmount(amount=Decimal("1000.00"), currency="GBP"), _FRIDAY)
    assert result.status is CurrencyNormalizationStatus.NORMALIZED
    assert result.eur_amount == (Decimal("1000.00") * (Decimal("1") / Decimal("0.84183"))).quantize(Decimal("0.01"))
    assert result.eur_amount is not None
    assert result.eur_amount > Decimal("1000.00")
    assert result.rate_observation_date == _FRIDAY


def test_normalizer_reports_an_unpublished_currency_without_a_euro_amount() -> None:
    service = CurrencyNormalizationService(rate_provider=EcbReferenceRateProvider(fetch=ecb_csv_fetch(_ECB_QUOTES)))

    result = service.normalize(MonetaryAmount(amount=Decimal("1000.00"), currency="XYZ"), _FRIDAY)

    assert result.status is CurrencyNormalizationStatus.UNSUPPORTED_CURRENCY
    assert result.eur_amount is None
