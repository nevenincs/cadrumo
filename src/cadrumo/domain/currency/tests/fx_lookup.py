"""Typed rate lookups for exchange-rate test doubles.

A fake :class:`~domain.currency.service.ExchangeRateProvider` decides a rate or
none; this builds the :class:`~domain.currency.models.EurRateLookup` the port
answers with, so each double states only its rate policy.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..models import EurRateLookup, EurRateLookupStatus


def eur_rate_lookup(
    rate: Decimal | None,
    *,
    rate_date: date,
    source: str,
    observation_date: date | None = None,
) -> EurRateLookup:
    """Return a found lookup for ``rate``, observed on ``rate_date`` unless stated, or a missing one."""
    if rate is None:
        return EurRateLookup(status=EurRateLookupStatus.MISSING_RATE, rate_date=rate_date, source=source)
    return EurRateLookup(
        status=EurRateLookupStatus.FOUND,
        rate_date=rate_date,
        source=source,
        rate=rate,
        observation_date=rate_date if observation_date is None else observation_date,
    )


__all__ = ["eur_rate_lookup"]
