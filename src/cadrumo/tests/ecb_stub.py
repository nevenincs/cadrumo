"""In-memory ECB Data Portal transport for exchange-rate tests.

:class:`~adapters.outbound.fx.EcbReferenceRateProvider` resolves every rate from
the live ECB Data Portal, so each suite injects a transport instead of reaching
the network. :func:`ecb_csv_fetch` builds one from a declared observation table.

The stub parses ``startPeriod``/``endPeriod`` out of the requested URL and emits
only observations inside that window, exactly as the ECB does. Honouring the
window keeps the provider's TARGET working-day fallback under test: a stub that
returned every seeded observation regardless of range would make the fallback
assertions tautological.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from ..core.parsing.dates import parse_iso8601_date

if TYPE_CHECKING:
    from ..adapters.outbound.fx.ecb_provider import RateFetch

_CSV_HEADER = "KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE"


def ecb_csv_fetch(quotes: Mapping[str, Mapping[date, Decimal]]) -> RateFetch:
    """Return a :data:`~adapters.outbound.fx.RateFetch` over declared quotes.

    Args:
        quotes: ``{currency: {publication_date: ecb_eur_base_quote}}`` in the
            ECB's own EUR-base direction (``1 EUR = quote CCY``). A currency
            absent from the mapping answers with an empty result set, which is
            how the ECB reports a series it does not publish.

    Returns:
        A transport callable suitable for ``EcbReferenceRateProvider(fetch=...)``.
    """

    def _fetch(url: str) -> str:
        parsed = urlparse(url)
        currency = parsed.path.rsplit("/", 1)[-1].split(".")[1]
        params = parse_qs(parsed.query)
        start = parse_iso8601_date(params["startPeriod"][0])
        end = parse_iso8601_date(params["endPeriod"][0])
        if start is None or end is None:
            raise AssertionError(f"provider issued an unparseable observation window: {url!r}")
        rows = [
            f"EXR.D.{currency}.EUR.SP00.A,D,{currency},EUR,SP00,A,{day.isoformat()},{quote}"
            for day, quote in sorted(quotes.get(currency, {}).items())
            if start <= day <= end
        ]
        if not rows:
            # The ECB answers an empty window with a 200 and no body at all.
            return ""
        return "\n".join([_CSV_HEADER, *rows]) + "\n"

    return _fetch


__all__ = ["ecb_csv_fetch"]
