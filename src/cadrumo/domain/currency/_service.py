"""Currency normalization service: convert foreign amounts to EUR.

Provides :class:`ExchangeRateProvider` — the protocol an exchange-rate
backend must implement — and :class:`CurrencyNormalizationService`, which
applies a provider-supplied rate to produce a :class:`NormalizedAmount`
(from ``._models``).  When no provider is configured or no rate is
available the service returns a ``NormalizedAmount`` with
``status = CurrencyNormalizationStatus.MISSING_RATE`` so callers can
surface a human-readable warning rather than silently propagating a zero
amount into a filing (modelo = an AEAT tax form).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol

from ...core.external_constants import DEFAULT_CURRENCY
from ._models import (
    CurrencyNormalizationStatus,
    MonetaryAmount,
    NormalizedAmount,
)


class ExchangeRateProvider(Protocol):
    """Protocol for fetching exchange rates."""

    def get_eur_rate(self, currency: str, rate_date: date) -> Decimal | None:
        """Get the exchange rate to EUR for a given currency and date.

        Returns the rate such that original_amount * rate = eur_amount.
        Returns None if no rate is available.
        """
        ...


class CurrencyNormalizationService:
    """Service to normalize foreign currencies to EUR."""

    def __init__(self, rate_provider: ExchangeRateProvider | None = None) -> None:
        self._rate_provider = rate_provider

    def normalize(self, amount: MonetaryAmount, rate_date: date) -> NormalizedAmount:
        """Normalize an amount to EUR using the rate for the given date.

        Returns:
            A :class:`NormalizedAmount` with the EUR-equivalent and conversion metadata.
        """
        if amount.currency == DEFAULT_CURRENCY:
            return NormalizedAmount(
                original=amount,
                eur_amount=amount.amount,
                status=CurrencyNormalizationStatus.NATIVE_EUR,
                rate=Decimal("1.0"),
                rate_source="native",
                rate_date=rate_date,
            )

        if not self._rate_provider:
            return NormalizedAmount(
                original=amount,
                eur_amount=Decimal("0.0"),
                status=CurrencyNormalizationStatus.MISSING_RATE,
            )

        rate = self._rate_provider.get_eur_rate(amount.currency, rate_date)
        if rate is None:
            return NormalizedAmount(
                original=amount,
                eur_amount=Decimal("0.0"),
                status=CurrencyNormalizationStatus.MISSING_RATE,
            )

        eur_amount = amount.amount * rate

        return NormalizedAmount(
            original=amount,
            eur_amount=eur_amount.quantize(Decimal("0.01")),
            status=CurrencyNormalizationStatus.NORMALIZED,
            rate=rate,
            rate_source="provider",
            rate_date=rate_date,
        )
