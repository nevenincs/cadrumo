"""Outbound foreign-exchange rate adapters for currency normalization.

Provides the production :class:`EcbReferenceRateProvider`, an implementation of
:class:`domain.currency.ExchangeRateProvider` backed by the bundled
European Central Bank ``eurofxref`` snapshot. The ECB euro reference rate is the
official exchange-rate source for ledger-to-modelo conversion (Ley 46/1998 art. 36).

The adapter keeps runtime conversion deterministic and offline: ECB EUR-base
quotes are inverted into the ``CCY -> EUR`` multiplier expected by
:class:`domain.currency.CurrencyNormalizationService`, and non-publication
dates fall back to the most recent prior ECB publication date. Ledger import and
aggregation consume this through the domain protocol; this package does not own
transaction persistence or modelo binding projection.
"""

from __future__ import annotations

from ._ecb_provider import EcbReferenceRateProvider, default_ecb_rate_provider

__all__ = ["EcbReferenceRateProvider", "default_ecb_rate_provider"]
