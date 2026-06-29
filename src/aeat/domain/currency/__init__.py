"""Currency normalization: convert foreign amounts to euro for tax use.

Normalizes monetary amounts to euro through an injected exchange-rate
provider, so downstream tax aggregation always works in a single currency.
Pure value logic; the rate source is a boundary. The domain service consumes an
:class:`ExchangeRateProvider` protocol and returns :class:`NormalizedAmount`
records. Concrete ECB reference-rate loading lives in
:mod:`aeat.adapters.outbound.fx`, not in this domain package.

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
    - :mod:`aeat.adapters.outbound.fx` for the bundled ECB
      :class:`~aeat.adapters.outbound.fx.EcbReferenceRateProvider` adapter that
      implements :class:`ExchangeRateProvider`.
    - :mod:`aeat.application.aggregation` for ledger import and source-resolution
      paths that consume euro-normalized amounts.
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
