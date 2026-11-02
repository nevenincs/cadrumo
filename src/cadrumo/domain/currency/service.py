"""Currency normalization service: convert foreign amounts to EUR.

Provides :class:`ExchangeRateProvider` — the protocol an exchange-rate
backend must implement — and :class:`CurrencyNormalizationService`, which
applies a provider-supplied rate to produce a :class:`NormalizedAmount`.
When no provider is configured, no rate is available, or the rate authority
publishes no series for the currency, the result carries the matching status
and no euro amount, so a caller can never read a zero into a filing.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Protocol

from ...core.external_constants import DEFAULT_CURRENCY
from ...core.money.rounding import round_to_cents
from .models import (
    CurrencyNormalizationStatus,
    EurRateLookup,
    EurRateLookupStatus,
    FxConversionStamp,
    MonetaryAmount,
    NormalizedAmount,
)

# The ECB's longest closure is Good Friday through Easter Monday (four days
# without a publication); the bound adds margin so the walk cannot run unbounded.
_MAX_DAYS_TO_NEXT_PUBLICATION = 7


class ExchangeRateProvider(Protocol):
    """Protocol for fetching exchange rates."""

    @property
    def rate_source_id(self) -> str:
        """Stable identifier for the rate authority this provider speaks for.

        Stamped onto every converted record so a stored euro figure names the
        series it came from. Required rather than optional: a provider that
        cannot say who it is produces conversions nothing can later audit, and
        a default here would put that anonymity one attribute away.
        """
        ...

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        """Look up the currency-to-EUR rate for a date.

        A found rate satisfies ``original_amount * rate = eur_amount`` and names
        the observation it came from. A transport failure raises
        :exc:`~domain.currency.errors.ExchangeRateProviderError` rather than
        answering, so an unreachable authority is never mistaken for a missing
        rate.
        """
        ...


class CurrencyNormalizationService:
    """Service to normalize foreign currencies to EUR."""

    def __init__(self, rate_provider: ExchangeRateProvider | None = None) -> None:
        """Bind the rate source; without one the service can only report a missing rate."""
        self._rate_provider = rate_provider

    def normalize(self, amount: MonetaryAmount, rate_date: date) -> NormalizedAmount:
        """Normalize an amount to EUR using the rate for the given date.

        Returns:
            A :class:`NormalizedAmount` with the EUR-equivalent and conversion metadata.
        """
        if amount.currency == DEFAULT_CURRENCY:
            return NormalizedAmount(
                original=amount,
                eur_amount=amount.amount,
                status=CurrencyNormalizationStatus.NATIVE_EUR,
                rate=Decimal("1.0"),
                rate_source="native",
                rate_date=rate_date,
            )

        if not self._rate_provider:
            return NormalizedAmount(
                original=amount,
                eur_amount=None,
                status=CurrencyNormalizationStatus.MISSING_RATE,
            )

        lookup = self._rate_provider.lookup_eur_rate(amount.currency, rate_date)
        if lookup.status is EurRateLookupStatus.UNSUPPORTED_CURRENCY:
            return NormalizedAmount(
                original=amount,
                eur_amount=None,
                status=CurrencyNormalizationStatus.UNSUPPORTED_CURRENCY,
            )
        if lookup.status is not EurRateLookupStatus.FOUND or lookup.rate is None:
            return NormalizedAmount(
                original=amount,
                eur_amount=None,
                status=CurrencyNormalizationStatus.MISSING_RATE,
            )
        rate = lookup.rate
        eur_amount = amount.amount * rate

        return NormalizedAmount(
            original=amount,
            eur_amount=round_to_cents(eur_amount),
            status=CurrencyNormalizationStatus.NORMALIZED,
            rate=rate,
            # The authority that quoted this rate, not the bare fact that some
            # provider did. "provider" said only "not native", which is already
            # carried by the status, so the ledger row's rate provenance named
            # nothing an auditor could go back to.
            rate_source=self._rate_provider.rate_source_id,
            rate_date=rate_date,
            rate_observation_date=lookup.observation_date,
        )


def published_eur_rate_on_day_or_next_publication(
    currency: str,
    day: date,
    *,
    rate_provider: ExchangeRateProvider,
) -> EurRateLookup:
    """Return the rate published for ``day`` or else for the next day of publication.

    Directive 2006/112/EC arts. 366(2), 369h(2) and 369u(2) convert at the
    exchange rate published by the European Central Bank for the last day of the
    period, "or, if there is no publication on that day, on the next day of
    publication". LIVA arts. 163 noniesdecies.Uno.c), duovicies.Uno.c) and
    septvicies.Uno.c) say "o, si no hubiera publicación correspondiente a ese
    día, del día siguiente". Read in conformity with the Directive, "del día
    siguiente" means the next day on which a rate is published: taken as the next
    calendar day alone, an unpublished next day would leave no rate at all, which
    the Directive does not.

    A provider's own fallback reaches back to the last prior publication, so its
    answer counts only when its observation is the day asked for; a prior
    publication is never used. The walk forward stops after
    :data:`_MAX_DAYS_TO_NEXT_PUBLICATION` days, and a series with no later
    publication yet is answered as a missing rate.
    """
    for offset in range(_MAX_DAYS_TO_NEXT_PUBLICATION + 1):
        candidate = day + timedelta(days=offset)
        lookup = rate_provider.lookup_eur_rate(currency, candidate)
        if lookup.status is EurRateLookupStatus.UNSUPPORTED_CURRENCY:
            return lookup
        if lookup.status is EurRateLookupStatus.FOUND and lookup.observation_date == candidate:
            return lookup
    return EurRateLookup(
        status=EurRateLookupStatus.MISSING_RATE,
        rate_date=day,
        source=rate_provider.rate_source_id,
    )


def resolve_fx_conversion_stamp(
    *,
    currency: str,
    on_date: date,
    rate_provider: ExchangeRateProvider,
) -> FxConversionStamp | None:
    """Return the euro-conversion stamp for a foreign-currency record, or ``None``.

    The single authority for the *stamping policy*: which date the rate is taken
    at, when a record is left unstamped, and what an unresolvable rate means.
    The rate SOURCE was already centralised behind
    :class:`ExchangeRateProvider`; this centralises the decision made around it,
    which had been hand-declared at two application call sites.

    Conversion happens at the record's own operation date — the issue or invoice
    date — because that is the date Spanish law binds the rate to: for IVA, the
    seller exchange rate fixed by the Banco de España in force at the moment of
    chargeability (LIVA art. 79.Once), where Directive 2006/112 art. 91(2) requires
    Member States to accept the latest ECB rate at chargeability; for the
    income-tax and other filing forms, the official rate published by the ECB
    directly or through the Banco de España (Ley 46/1998 art. 36). Converting once
    at ingest also keeps a stored euro figure stable rather than drifting with
    every later read.

    A euro record is left unstamped: there is nothing to convert, and a
    ``1``-valued stamp would assert a conversion that never happened. A foreign
    record whose rate cannot be resolved is ALSO left unstamped rather than
    defaulted, and that is the load-bearing half of this policy. Without a
    stamp the record reports no euro value and is held back from projection,
    which an operator can see and correct; a fabricated or assumed rate would
    instead flow silently into a filed euro amount, and nothing downstream could
    tell it from a real one.

    Args:
        currency: The record's currency. Compared case-insensitively against
            the euro token, so a caller that has not yet normalised it is safe.
        on_date: The operation date to take the rate at.
        rate_provider: The rate source. Required rather than defaulted: the
            default ECB provider is an outbound adapter, and this layer must not
            reach for it.

    Returns:
        The :class:`FxConversionStamp` to apply, or ``None`` when the record
        must be left unstamped — euro, or no resolvable rate. The stamp names
        the provider's rate authority, so the record says not only what rate was
        applied and when, but on whose published series.
    """
    if currency.strip().upper() == DEFAULT_CURRENCY:
        return None
    lookup = rate_provider.lookup_eur_rate(currency, on_date)
    if lookup.status is not EurRateLookupStatus.FOUND or lookup.rate is None:
        return None
    return FxConversionStamp(
        rate=lookup.rate,
        rate_date=on_date,
        source=rate_provider.rate_source_id,
        observation_date=lookup.observation_date,
    )
