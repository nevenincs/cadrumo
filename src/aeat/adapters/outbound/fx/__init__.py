"""Outbound foreign-exchange rate adapters.

Provides the production :class:`EcbReferenceRateProvider`, an
:class:`aeat.domain.currency.ExchangeRateProvider` backed by the European
Central Bank euro foreign-exchange reference rates (the official rate of Spanish
law per Ley 46/1998 art. 36). See the ``ledger-fx-conversion`` ADR.
"""

from __future__ import annotations

from ._ecb_provider import EcbReferenceRateProvider, default_ecb_rate_provider

__all__ = ["EcbReferenceRateProvider", "default_ecb_rate_provider"]
