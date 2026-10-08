"""Modelo 720 valuation: the euro value of one type 2 amount and the rate date it is taken at.

Every type 2 amount is declared "en euros o su contravalor" (Orden HAP/72/2013
Anexo, type 2 positions 432-446 and 447-461). The order fixes the valuation
date per class but no exchange-rate date; the rate is the ECB euro reference
rate (Ley 46/1998 art. 36) and its date follows DGT doctrine:

* a valuation at 31 December converts at the 31 December rate of the declared
  year, whatever the class (V0691-13, V0555-18, V1096-18, V3973-15, V0751-25,
  V1051-26), real-estate acquisition value included (V2669-17);
* an account cancelled during the year converts its cessation balance at the
  cessation-date rate (V1051-26, V2045-23).

Where the sources leave the rate date unsettled the conversion refuses rather
than guessing: an extinction-date rate the ECB did not publish on that day, and
the extinction during the year of anything other than an account (securities,
IIC shares and insurance by analogy only; the acquisition value of a transferred
real estate). A euro amount needs no rate and is never refused on these grounds.

Conversion itself is the canonical :class:`~domain.currency.service.CurrencyNormalizationService`;
this module decides only which date it is asked for and which outcomes a filing
may carry.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.foreign_asset_obligation import M720AssetClassCode
from ..currency.models import CurrencyNormalizationStatus, MonetaryAmount, NormalizedAmount
from ..currency.service import CurrencyNormalizationService


class M720ValuationEvent(StrEnum):
    """The moment a type 2 valuation measures the asset at."""

    YEAR_END = "year_end"
    """31 December of the declared year."""

    EXTINCTION = "extinction"
    """Cessation of an account, or extinction or transfer of the asset, during the year."""


class M720ValuationRefusalReason(StrEnum):
    """Why a type 2 amount has no euro value a filing may carry."""

    MISSING_RATE = "missing_rate"
    """The rate authority published no rate for the currency within its look-back."""

    UNSUPPORTED_CURRENCY = "unsupported_currency"
    """The rate authority publishes no series for the currency at all."""

    EXTINCTION_RATE_UNSETTLED = "extinction_rate_unsettled"
    """No published rule fixes the rate date for this class's extinction record."""

    EXTINCTION_RATE_NOT_PUBLISHED = "extinction_rate_not_published"
    """The ECB published no rate on the extinction date, and no rule settles the fallback."""


class ForeignAssetValuationRefusedError(CadrumoError):
    """Raised when a Modelo 720 amount cannot be converted to a filing-grade euro value."""

    def __init__(
        self,
        *,
        asset_ref: str,
        currency: str,
        rate_date: date,
        reason: M720ValuationRefusalReason,
    ) -> None:
        """Name the asset, currency, rate date and reason the amount was refused for."""
        self.asset_ref = asset_ref
        self.currency = currency
        self.rate_date = rate_date
        self.reason = reason
        super().__init__(
            f"Modelo 720 asset {asset_ref}: no euro value for {currency} at {rate_date.isoformat()} ({reason.value})",
            context={
                "asset_ref": asset_ref,
                "currency": currency,
                "rate_date": rate_date.isoformat(),
                "reason": reason.value,
            },
        )


def m720_valuation_rate_date(
    *,
    event: M720ValuationEvent,
    event_date: date | None,
    filing_year: int,
) -> date:
    """Return the date whose ECB rate converts a valuation measured at ``event``.

    Args:
        event: When the valuation measures the asset.
        event_date: The cessation or extinction date; ``None`` for a year-end valuation.
        filing_year: The declared ejercicio.
    """
    if event is M720ValuationEvent.YEAR_END:
        if event_date is not None:
            raise ValueError("a year-end valuation carries no event date")
        return date(filing_year, 12, 31)
    if event_date is None:
        raise ValueError("an extinction valuation requires its extinction date")
    if event_date.year != filing_year:
        raise ValueError(f"extinction date {event_date.isoformat()} lies outside the declared year {filing_year}")
    return event_date


def normalize_m720_valuation(
    *,
    asset_ref: str,
    asset_class: M720AssetClassCode,
    amount: MonetaryAmount,
    event: M720ValuationEvent,
    event_date: date | None,
    filing_year: int,
    service: CurrencyNormalizationService,
) -> NormalizedAmount:
    """Convert one type 2 amount to euros at its legal rate date, or refuse.

    Returns only a ``NATIVE_EUR`` or ``NORMALIZED`` result; every other outcome
    raises :class:`ForeignAssetValuationRefusedError`, so no caller can read a
    euro amount the rate authority did not produce.
    """
    rate_date = m720_valuation_rate_date(event=event, event_date=event_date, filing_year=filing_year)
    foreign = amount.currency != DEFAULT_CURRENCY
    if foreign and event is M720ValuationEvent.EXTINCTION and asset_class is not M720AssetClassCode.CUENTA:
        raise ForeignAssetValuationRefusedError(
            asset_ref=asset_ref,
            currency=amount.currency,
            rate_date=rate_date,
            reason=M720ValuationRefusalReason.EXTINCTION_RATE_UNSETTLED,
        )
    normalized = service.normalize(amount, rate_date)
    if normalized.status is CurrencyNormalizationStatus.UNSUPPORTED_CURRENCY:
        reason = M720ValuationRefusalReason.UNSUPPORTED_CURRENCY
    elif normalized.status not in {CurrencyNormalizationStatus.NATIVE_EUR, CurrencyNormalizationStatus.NORMALIZED}:
        reason = M720ValuationRefusalReason.MISSING_RATE
    elif foreign and event is M720ValuationEvent.EXTINCTION and normalized.rate_observation_date != rate_date:
        reason = M720ValuationRefusalReason.EXTINCTION_RATE_NOT_PUBLISHED
    else:
        return normalized
    raise ForeignAssetValuationRefusedError(
        asset_ref=asset_ref,
        currency=amount.currency,
        rate_date=rate_date,
        reason=reason,
    )


__all__ = [
    "ForeignAssetValuationRefusedError",
    "M720ValuationEvent",
    "M720ValuationRefusalReason",
    "m720_valuation_rate_date",
    "normalize_m720_valuation",
]
