"""Currency normalization to euro, so aggregation works from one currency.

Inert namespace. Each contract is reached at its own defining module:
:mod:`~cadrumo.domain.currency.models` for :class:`~MonetaryAmount`,
:class:`~NormalizedAmount` and :class:`~CurrencyNormalizationStatus`,
``service`` for :class:`~CurrencyNormalizationService` and the
:class:`~ExchangeRateProvider` protocol it depends on, and ``errors`` for
the refusal hierarchy.

The provider contract is ``original_amount * rate = eur_amount``. ECB
EUR-base quote inversion and most-recent-prior-publication fallback live in
:mod:`cadrumo.adapters.outbound.fx`, not in this pure domain package -- the
service records a status rather than silently assuming EUR or writing zero
into a filing-grade fact.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
