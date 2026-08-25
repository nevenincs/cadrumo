"""Public facade for currency normalization to euro.

Normalizes :class:`MonetaryAmount` records to EUR through an injected
:class:`ExchangeRateProvider`, so downstream tax aggregation works from a single
currency while source currency evidence remains intact. The provider contract is
``original_amount * rate = eur_amount``; ECB EUR-base quote inversion and
most-recent-prior-publication fallback live in :mod:`adapters.outbound.fx`,
not in this pure domain package.

The service returns :class:`NormalizedAmount` with a
:class:`CurrencyNormalizationStatus` rather than silently assuming EUR or writing
zero into filing-grade facts. Ledger import persists successful normalization as
``fx_rate`` / ``value_in_eur`` on :class:`domain.transactions.Transaction`
records before application aggregation consumes the row.

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

See Also:
    :mod:`adapters.outbound.fx`
        Bundled ECB :class:`adapters.outbound.fx.EcbReferenceRateProvider`
        adapter that implements :class:`ExchangeRateProvider`.
    :mod:`application.ledger`
        Import path that applies this service and persists ``fx_rate`` /
        ``value_in_eur`` on transactions.
    :mod:`domain.transactions`
        Transaction model coupling invariants for foreign-currency rate
        provenance and EUR projection fields.
    :mod:`application.aggregation`
        Source-resolution predicates and amount projections that reject
        unconverted foreign rows instead of silently treating them as EUR.
"""

from .errors import (
    CurrencyError,
    ExchangeRateProviderError,
    MissingExchangeRateError,
    StaleExchangeRateError,
    UnsupportedCurrencyError,
)
from ._models import (
    CurrencyNormalizationStatus,
    FxConversionStamp,
    MonetaryAmount,
    NormalizedAmount,
)
from ._service import CurrencyNormalizationService, ExchangeRateProvider, resolve_fx_conversion_stamp

__all__ = [
    "CurrencyError",
    "CurrencyNormalizationService",
    "CurrencyNormalizationStatus",
    "ExchangeRateProvider",
    "ExchangeRateProviderError",
    "FxConversionStamp",
    "MissingExchangeRateError",
    "MonetaryAmount",
    "NormalizedAmount",
    "StaleExchangeRateError",
    "UnsupportedCurrencyError",
    "resolve_fx_conversion_stamp",
]
