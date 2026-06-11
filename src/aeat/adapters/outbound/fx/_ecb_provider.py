"""ECB euro reference-rate exchange-rate provider.

Implements the :class:`aeat.domain.currency.ExchangeRateProvider` protocol over a
bundled snapshot of the European Central Bank euro foreign-exchange reference
rates (``eurofxref`` XML). The ECB rates are the official exchange rate of
Spanish law (Ley 46/1998 art. 36) accepted for IRPF, IVA, and PGC conversion —
see the ``ledger-fx-conversion`` ADR.

The ECB publishes EUR-base quotes (``1 EUR = rate CCY``). The
:class:`aeat.domain.currency.CurrencyNormalizationService` expects
``get_eur_rate`` to return CCY->EUR (so ``eur = amount * rate``), so this provider
returns ``1 / ecb_rate``. The ECB publishes only on TARGET working days, so a
lookup for a non-publication date falls back to the most-recent prior published
date.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from defusedxml import ElementTree

from ....core.external_constants import UTF_8_ENCODING
from ....core.parsing import parse_iso8601_date

_BUNDLED_RATES = Path(__file__).resolve().parents[3] / "_data" / "fx" / "eurofxref-bundled.xml"


class EcbReferenceRateProvider:
    """EUR reference-rate provider backed by a bundled ECB ``eurofxref`` snapshot."""

    def __init__(self, *, rates_path: Path | None = None) -> None:
        path = rates_path or _BUNDLED_RATES
        # date -> {currency: ecb_eur_base_rate}; sorted date index for fallback.
        self._by_date: dict[date, dict[str, Decimal]] = _parse_eurofxref(path)
        self._dates: list[date] = sorted(self._by_date)

    def get_eur_rate(self, currency: str, rate_date: date) -> Decimal | None:
        """Return the CCY->EUR rate for ``rate_date`` (or most-recent prior).

        Returns ``None`` for EUR (handled natively upstream) or an unknown
        currency / a date earlier than the snapshot's first published date.
        """
        code = currency.upper()
        if code == "EUR":
            return Decimal("1")
        effective = self._effective_date(rate_date)
        if effective is None:
            return None
        ecb_rate = self._by_date[effective].get(code)
        if ecb_rate is None or ecb_rate == 0:
            return None
        # ECB quotes EUR-base (1 EUR = ecb_rate CCY); CCY->EUR is the inverse.
        return Decimal("1") / ecb_rate

    def _effective_date(self, rate_date: date) -> date | None:
        """Most-recent published date on or before ``rate_date`` (working-day fallback)."""
        index = bisect_right(self._dates, rate_date)
        if index == 0:
            return None
        return self._dates[index - 1]


def _parse_eurofxref(path: Path) -> dict[date, dict[str, Decimal]]:
    """Parse an ECB ``eurofxref`` XML file into ``{date: {currency: rate}}``.

    Namespace-agnostic: the ECB feed uses default + ``gesmes`` namespaces, so
    elements are matched by the local ``Cube`` tag name rather than a fixed
    qualified name.
    """
    root = ElementTree.fromstring(path.read_text(encoding=UTF_8_ENCODING))
    by_date: dict[date, dict[str, Decimal]] = {}
    for node in root.iter():
        if not node.tag.endswith("Cube"):
            continue
        time_attr = node.get("time")
        if time_attr is None:
            continue
        day = parse_iso8601_date(time_attr)
        if day is None:
            continue
        rates: dict[str, Decimal] = {}
        for child in node:
            if not child.tag.endswith("Cube"):
                continue
            currency = child.get("currency")
            rate = child.get("rate")
            if currency and rate:
                rates[currency.upper()] = Decimal(rate)
        if rates:
            by_date[day] = rates
    return by_date


@lru_cache(maxsize=1)
def default_ecb_rate_provider() -> EcbReferenceRateProvider:
    """Return the process-wide :class:`EcbReferenceRateProvider` over the bundled ECB snapshot (cached)."""
    return EcbReferenceRateProvider()


__all__ = ["EcbReferenceRateProvider", "default_ecb_rate_provider"]
