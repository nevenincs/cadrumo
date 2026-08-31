"""Outbound foreign-exchange rate adapters for currency normalization.

Provides the production :class:`EcbReferenceRateProvider`, an implementation of
:class:`domain.currency.ExchangeRateProvider` that resolves each rate from the
European Central Bank Data Portal at lookup time. The ECB euro reference rate is
the official exchange-rate source for ledger-to-modelo conversion (Ley 46/1998
art. 36).

Rates are resolved per operation date against the published ECB series: EUR-base
quotes are inverted into the ``CCY -> EUR`` multiplier expected by
:class:`domain.currency.CurrencyNormalizationService`, and a date the ECB did not
publish on resolves to the most recent prior publication. Ledger import and
aggregation consume this through the domain protocol; this package does not own
transaction persistence or modelo binding projection.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
