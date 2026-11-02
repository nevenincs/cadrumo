"""The day-or-next rule of LIVA art. 163 noniesdecies over the real provider's backward fallback."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....domain.currency.models import EurRateLookupStatus
from .....domain.currency.service import published_eur_rate_on_day_or_next
from .....tests.ecb_stub import ecb_csv_fetch
from ..ecb_provider import EcbReferenceRateProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FRIDAY = date(2026, 5, 29)
_SUNDAY = date(2026, 5, 31)
_MONDAY = date(2026, 6, 1)


def _provider(quotes: dict[date, Decimal]) -> EcbReferenceRateProvider:
    return EcbReferenceRateProvider(fetch=ecb_csv_fetch({"PLN": quotes}))


def test_a_published_day_answers_with_its_own_rate() -> None:
    lookup = published_eur_rate_on_day_or_next(
        "PLN", _MONDAY, rate_provider=_provider({_MONDAY: Decimal("4"), date(2026, 6, 2): Decimal("5")})
    )
    assert (lookup.rate, lookup.observation_date) == (Decimal("0.25"), _MONDAY)


def test_an_unpublished_day_takes_the_next_day_and_not_the_last_prior_publication() -> None:
    lookup = published_eur_rate_on_day_or_next(
        "PLN", _SUNDAY, rate_provider=_provider({_FRIDAY: Decimal("10"), _MONDAY: Decimal("4")})
    )
    assert (lookup.rate, lookup.observation_date) == (Decimal("0.25"), _MONDAY)


def test_neither_day_publishing_is_a_missing_rate_even_with_a_prior_publication() -> None:
    saturday = date(2026, 5, 30)
    lookup = published_eur_rate_on_day_or_next(
        "PLN", saturday, rate_provider=_provider({_FRIDAY: Decimal("10"), _MONDAY: Decimal("4")})
    )
    assert lookup.status is EurRateLookupStatus.MISSING_RATE
    assert lookup.rate is None


def test_a_series_the_authority_does_not_publish_stays_unsupported() -> None:
    lookup = published_eur_rate_on_day_or_next("XXX", _MONDAY, rate_provider=_provider({_MONDAY: Decimal("4")}))
    assert lookup.status is EurRateLookupStatus.UNSUPPORTED_CURRENCY
