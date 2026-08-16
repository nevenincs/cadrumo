"""ECB euro reference-rate exchange-rate provider.

Implements the :class:`domain.currency.ExchangeRateProvider` protocol against the
European Central Bank Data Portal, resolving each rate from the published series
at lookup time. The ECB rates are the official exchange rate of Spanish law (Ley
46/1998 art. 36) accepted for IRPF, IVA, and PGC conversion.

The ECB publishes EUR-base quotes (``1 EUR = rate CCY``). The
:class:`domain.currency.CurrencyNormalizationService` expects ``get_eur_rate`` to
return CCY->EUR (so ``eur = amount * rate``), so this provider returns
``1 / ecb_rate``.

The ECB publishes only on TARGET working days and the Data Portal answers a
non-publication date with an empty result set, so a lookup widens its query
window backwards by :data:`LOOKBACK_DAYS` and takes the most recent published
observation on or before the requested date.

A transport or protocol failure raises
:exc:`domain.currency.ExchangeRateProviderError` rather than returning ``None``:
an unreachable ECB must not be indistinguishable from a currency the ECB does
not publish, which would silently degrade ledger rows to a zero EUR value.

The default transport (:func:`_https_fetch`) reaches the live European Central
Bank host unconditionally, because reaching it is what this adapter is for.
Holding a deterministic suite off that host is a TEST concern, carried by the
``aeat_live`` marker rather than by a production branch: a deterministic suite
injects a :data:`RateFetch` transport (``tests.ecb_stub.ecb_csv_fetch``), and a
test that genuinely wants the published series declares ``aeat_live`` and is
selected only by the live lane.
"""

from __future__ import annotations

import csv
import io
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from urllib.parse import urlparse

from ....core.config import load_settings
from ....core.errors import CoreValidationError
from ....core.external_constants import DEFAULT_CURRENCY, UTF_8_ENCODING
from ....core.parsing import normalise_iso_4217_currency, parse_iso8601_date
from ....domain.currency import ExchangeRateProviderError

ECB_DATA_API_HOST = "data-api.ecb.europa.eu"
ECB_EXR_ENDPOINT = f"https://{ECB_DATA_API_HOST}/service/data/EXR"

# The longest ECB non-publication run is the TARGET year-end closure plus its
# adjacent weekends, comfortably under a week; 14 days leaves margin without
# ever reaching back into a materially different rate.
LOOKBACK_DAYS = 14

#: Transport contract: given a URL, return the response body as text.
RateFetch = Callable[[str], str]

#: Identifier stamped on every record this provider converts. Names the ECB euro
#: reference-rate series specifically, not merely "an exchange-rate provider",
#: because the stamp's job is to let a later reader re-fetch the same published
#: observation and re-derive the stored euro figure (Ley 46/1998 art. 36).
ECB_RATE_SOURCE_ID = "ecb_reference"


class EcbReferenceRateProvider:
    """EUR reference-rate provider backed by the live ECB Data Portal series."""

    def __init__(
        self,
        *,
        fetch: RateFetch | None = None,
        lookback_days: int = LOOKBACK_DAYS,
    ) -> None:
        """Construct the provider.

        Args:
            fetch: Transport returning a response body for a URL. Defaults to a
                guarded HTTPS reader bound to the ECB Data Portal host; tests
                inject a fake so no suite depends on the network.
            lookback_days: How far back a lookup may reach for the most recent
                prior publication when the requested date is not a TARGET
                working day.
        """
        self._fetch = fetch or _https_fetch
        self._lookback = timedelta(days=lookback_days)
        # Resolved results are memoized per (currency, date) so a ledger import
        # spanning many rows on few distinct dates issues few requests.
        self._resolved: dict[tuple[str, date], Decimal | None] = {}

    @property
    def rate_source_id(self) -> str:
        """Return :data:`ECB_RATE_SOURCE_ID`, the stamped rate authority."""
        return ECB_RATE_SOURCE_ID

    def get_eur_rate(self, currency: str, rate_date: date) -> Decimal | None:
        """Return the CCY->EUR rate for ``rate_date`` (or most-recent prior).

        Returns ``None`` when the ECB publishes no series for ``currency``, or
        no observation within the lookback window ending at ``rate_date``.

        Raises:
            ExchangeRateProviderError: When the ECB Data Portal cannot be
                reached or returns an unusable response.
        """
        code = _normalise_ecb_currency(currency)
        if code == DEFAULT_CURRENCY:
            return Decimal("1")
        key = (code, rate_date)
        if key not in self._resolved:
            self._resolved[key] = self._resolve(code, rate_date)
        return self._resolved[key]

    def _resolve(self, code: str, rate_date: date) -> Decimal | None:
        url = _observation_url(code, rate_date - self._lookback, rate_date)
        observations = _parse_observations(self._fetch(url))
        if not observations:
            return None
        # The window ends at rate_date, so the latest observation in it is the
        # operation-date rate or the most recent prior publication. Every
        # observation the parser yields is finite and strictly positive, so
        # the inversion below cannot divide by zero or by a non-finite value
        # and no second usability test is needed here. The check that used to
        # live at this line was the weaker of the two: it ran only on the
        # LATEST observation, so a single unusable quote at the end of the
        # window discarded the valid earlier ones behind it and reported no
        # rate at all.
        _, ecb_rate = max(observations, key=lambda row: row[0])
        # ECB quotes EUR-base (1 EUR = ecb_rate CCY); CCY->EUR is the inverse.
        return Decimal("1") / ecb_rate


def _observation_url(currency: str, start: date, end: date) -> str:
    """Build the ECB Data Portal daily-spot observation URL for one currency."""
    code = _normalise_ecb_currency(currency)
    return (
        f"{ECB_EXR_ENDPOINT}/D.{code}.EUR.SP00.A"
        f"?startPeriod={start.isoformat()}&endPeriod={end.isoformat()}&format=csvdata"
    )


def _normalise_ecb_currency(currency: str) -> str:
    """Return a canonical currency code safe to embed in an ECB series path."""
    try:
        return normalise_iso_4217_currency(currency)
    except CoreValidationError as exc:
        msg = f"ECB exchange-rate currency must be a three-letter ISO 4217 code; got {currency!r}"
        raise ExchangeRateProviderError(msg) from exc


def _parse_observations(payload: str) -> list[tuple[date, Decimal]]:
    """Parse an ECB ``csvdata`` response into ``[(date, ecb_eur_base_rate)]``.

    A non-publication window yields an empty body, and the ECB emits rows with a
    blank ``OBS_VALUE`` for series gaps; both produce no observations rather
    than an error, so the caller reports a missing rate.

    This is the single place that decides whether an ``OBS_VALUE`` is a usable
    quote, and the test is USABILITY rather than convertibility. Only
    ``InvalidOperation`` used to be caught, so ``Decimal`` conversion success
    stood in for the question — and ``Decimal`` converts ``NaN`` and the
    infinities happily. Two failures followed, both downstream of here and
    neither visible as a parse problem: ``NaN`` reached the caller's ``<= 0``
    comparison, which raises :exc:`~decimal.InvalidOperation` for a quiet NaN,
    so a corrupted response escaped as a raw decimal exception instead of the
    provider's promised typed error; and ``Infinity`` passed that comparison
    and inverted to an effectively-zero exchange rate, converting every amount
    to nothing at all.

    A non-finite or non-positive value is therefore treated exactly as a
    malformed one — no observation — which keeps this function's documented
    "unusable value is a gap" policy single-valued rather than splitting it
    into a parse rule and a separate caller-side rule that disagreed about
    which values count.
    """
    if not payload.strip():
        return []
    observations: list[tuple[date, Decimal]] = []
    for row in csv.DictReader(io.StringIO(payload)):
        period = (row.get("TIME_PERIOD") or "").strip()
        value = (row.get("OBS_VALUE") or "").strip()
        if not period or not value:
            continue
        day = parse_iso8601_date(period)
        if day is None:
            continue
        try:
            quote = Decimal(value)
        except InvalidOperation:
            continue
        if not quote.is_finite() or quote <= 0:
            continue
        observations.append((day, quote))
    return observations


def _https_fetch(url: str) -> str:
    """Read ``url`` over HTTPS, constrained to the ECB Data Portal host.

    Carries no test-awareness. Keeping a deterministic suite off the live host is
    enforced by the ``aeat_live`` marker contract, not by a production branch
    reading a pytest-only opt-in.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != ECB_DATA_API_HOST:
        msg = f"refusing non-https or non-ECB exchange-rate URL: {url!r}"
        raise ExchangeRateProviderError(msg)
    settings = load_settings()
    timeout = settings.cadrumo_fx_rate_lookup_timeout_s
    # URL is constrained to the canonical ECB Data Portal HTTPS host above.
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # nosemgrep
            payload = response.read()
            if not isinstance(payload, bytes):
                raise ExchangeRateProviderError("ECB euro reference-rate response was not bytes")
            return payload.decode(UTF_8_ENCODING)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        msg = f"ECB euro reference-rate lookup failed for {url!r}: {exc}"
        raise ExchangeRateProviderError(msg) from exc


@lru_cache(maxsize=1)
def default_ecb_rate_provider() -> EcbReferenceRateProvider:
    """Return the process-wide :class:`EcbReferenceRateProvider` (cached).

    Caching the instance keeps its per-(currency, date) memo shared across every
    lookup in the process, so a multi-row ledger import re-uses resolved rates.
    """
    return EcbReferenceRateProvider()


__all__ = [
    "ECB_DATA_API_HOST",
    "ECB_EXR_ENDPOINT",
    "LOOKBACK_DAYS",
    "EcbReferenceRateProvider",
    "RateFetch",
    "default_ecb_rate_provider",
]
