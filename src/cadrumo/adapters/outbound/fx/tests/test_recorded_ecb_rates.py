"""The recorded ECB answers convert what they hold and refuse what they do not."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from .....domain.currency.errors import ExchangeRateProviderError
from .....tests.recorded_ecb_rates import recorded_ecb_answers, recorded_ecb_fetch, recorded_ecb_rate_provider
from ..ecb_provider import LOOKBACK_DAYS, EcbReferenceRateProvider, _observation_url, _parse_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _recorded_pair() -> tuple[str, date]:
    """Return one (currency, date) whose window the recording holds with an observation."""
    for url, body in sorted(recorded_ecb_answers().items()):
        if _parse_observations(body):
            currency = url.split("/EXR/D.", 1)[1].split(".", 1)[0]
            end = date.fromisoformat(url.split("endPeriod=", 1)[1].split("&", 1)[0])
            return currency, end
    raise AssertionError("the recording holds no window with a published observation")


def test_a_recorded_window_converts_through_the_real_provider() -> None:
    currency, rate_date = _recorded_pair()

    rate = EcbReferenceRateProvider(fetch=recorded_ecb_fetch).get_eur_rate(currency, rate_date)

    assert isinstance(rate, Decimal)
    assert rate > 0


def test_an_unrecorded_date_refuses_instead_of_borrowing_a_neighbour() -> None:
    currency, rate_date = _recorded_pair()
    unrecorded = rate_date + timedelta(days=1)
    assert _observation_url(currency, unrecorded - timedelta(days=LOOKBACK_DAYS), unrecorded) not in (
        recorded_ecb_answers()
    ), "the probe date must fall outside the recording for this refusal to mean anything"

    with pytest.raises(ExchangeRateProviderError, match="no recorded ECB answer"):
        EcbReferenceRateProvider(fetch=recorded_ecb_fetch).get_eur_rate(currency, unrecorded)


def test_an_unrecorded_currency_refuses() -> None:
    _, rate_date = _recorded_pair()

    with pytest.raises(ExchangeRateProviderError, match="no recorded ECB answer"):
        EcbReferenceRateProvider(fetch=recorded_ecb_fetch).get_eur_rate("ZAR", rate_date)


def test_the_host_provider_is_the_recorded_one() -> None:
    provider = recorded_ecb_rate_provider()

    assert provider is recorded_ecb_rate_provider()
    assert provider.rate_source_id == EcbReferenceRateProvider().rate_source_id
