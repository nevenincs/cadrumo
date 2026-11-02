"""The day-or-next-publication rule of Directive 2006/112 art. 369h(2) over the real provider's backward fallback."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from .....domain.currency.models import EurRateLookupStatus
from .....domain.currency.service import published_eur_rate_on_day_or_next_publication
from .....tests.ecb_stub import ecb_csv_fetch
from ..ecb_provider import EcbReferenceRateProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FRIDAY = date(2026, 5, 29)
_SUNDAY = date(2026, 5, 31)
_MONDAY = date(2026, 6, 1)


def _provider(quotes: dict[date, Decimal]) -> EcbReferenceRateProvider:
    return EcbReferenceRateProvider(fetch=ecb_csv_fetch({"PLN": quotes}))


def test_a_published_day_answers_with_its_own_rate() -> None:
    lookup = published_eur_rate_on_day_or_next_publication(
        "PLN", _MONDAY, rate_provider=_provider({_MONDAY: Decimal("4"), date(2026, 6, 2): Decimal("5")})
    )
    assert (lookup.rate, lookup.observation_date) == (Decimal("0.25"), _MONDAY)


def test_an_unpublished_day_takes_the_next_publication_and_not_the_last_prior_publication() -> None:
    lookup = published_eur_rate_on_day_or_next_publication(
        "PLN", _SUNDAY, rate_provider=_provider({_FRIDAY: Decimal("10"), _MONDAY: Decimal("4")})
    )
    assert (lookup.rate, lookup.observation_date) == (Decimal("0.25"), _MONDAY)


def test_a_saturday_period_end_takes_mondays_rate_not_fridays() -> None:
    saturday = date(2026, 5, 30)
    lookup = published_eur_rate_on_day_or_next_publication(
        "PLN", saturday, rate_provider=_provider({_FRIDAY: Decimal("10"), _MONDAY: Decimal("4")})
    )
    assert (lookup.rate, lookup.observation_date) == (Decimal("0.25"), _MONDAY)


def test_a_closure_walks_forward_to_the_next_publication() -> None:
    good_friday = date(2024, 3, 29)
    after_easter = date(2024, 4, 2)
    lookup = published_eur_rate_on_day_or_next_publication(
        "PLN",
        good_friday,
        rate_provider=_provider({date(2024, 3, 28): Decimal("10"), after_easter: Decimal("5")}),
    )
    assert (lookup.rate, lookup.observation_date) == (Decimal("0.2"), after_easter)


def test_no_publication_after_the_day_is_a_missing_rate_even_with_prior_ones() -> None:
    lookup = published_eur_rate_on_day_or_next_publication(
        "PLN", date(2026, 5, 30), rate_provider=_provider({_FRIDAY: Decimal("10")})
    )
    assert lookup.status is EurRateLookupStatus.MISSING_RATE
    assert lookup.rate is None


def test_a_publication_beyond_the_bound_is_a_missing_rate() -> None:
    day = date(2026, 5, 30)
    lookup = published_eur_rate_on_day_or_next_publication(
        "PLN", day, rate_provider=_provider({day + timedelta(days=8): Decimal("4")})
    )
    assert lookup.status is EurRateLookupStatus.MISSING_RATE
    assert lookup.rate is None


def test_a_publication_on_the_last_day_of_the_bound_is_taken() -> None:
    day = date(2026, 5, 30)
    last = day + timedelta(days=7)
    lookup = published_eur_rate_on_day_or_next_publication("PLN", day, rate_provider=_provider({last: Decimal("4")}))
    assert (lookup.rate, lookup.observation_date) == (Decimal("0.25"), last)


def test_a_series_the_authority_does_not_publish_stays_unsupported() -> None:
    lookup = published_eur_rate_on_day_or_next_publication(
        "XXX", _MONDAY, rate_provider=_provider({_MONDAY: Decimal("4")})
    )
    assert lookup.status is EurRateLookupStatus.UNSUPPORTED_CURRENCY
