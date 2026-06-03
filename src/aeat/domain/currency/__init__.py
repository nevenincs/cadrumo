"""Currency normalization: convert foreign amounts to euro for tax use.

Normalizes monetary amounts to euro through an injected exchange-rate
provider, so downstream tax aggregation always works in a single currency.
Pure value logic; the rate source is a boundary.

Major declarations:

* :class:`CurrencyNormalizationService` — applies a rate to produce a
  :class:`NormalizedAmount` from a :class:`MonetaryAmount`, recording a
  :class:`CurrencyNormalizationStatus`.
* :class:`ExchangeRateProvider` — the rate-source protocol the service
  depends on.
* :class:`CurrencyError` and its subclasses
  (:class:`MissingExchangeRateError`, :class:`StaleExchangeRateError`,
  :class:`UnsupportedCurrencyError`, :class:`ExchangeRateProviderError`) —
  the failure taxonomy.
"""

from ._errors import (
    CurrencyError,
    ExchangeRateProviderError,
    MissingExchangeRateError,
    StaleExchangeRateError,
    UnsupportedCurrencyError,
)
from ._models import (
    CurrencyNormalizationStatus,
    MonetaryAmount,
    NormalizedAmount,
)
from ._service import CurrencyNormalizationService, ExchangeRateProvider

__all__ = [
    "CurrencyError",
    "CurrencyNormalizationService",
    "CurrencyNormalizationStatus",
    "ExchangeRateProvider",
    "ExchangeRateProviderError",
    "MissingExchangeRateError",
    "MonetaryAmount",
    "NormalizedAmount",
    "StaleExchangeRateError",
    "UnsupportedCurrencyError",
]
