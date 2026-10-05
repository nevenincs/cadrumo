"""Modelo 720 euro valuation: legal rate dates and the cases that must refuse."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.foreign_asset_obligation import M720AssetClassCode
from ...currency.models import CurrencyNormalizationStatus, EurRateLookup, EurRateLookupStatus, MonetaryAmount
from ...currency.service import CurrencyNormalizationService
from ...currency.tests.fx_lookup import eur_rate_lookup
from ..valuation import (
    ForeignAssetValuationRefusedError,
    M720ValuationEvent,
    M720ValuationRefusalReason,
    m720_valuation_rate_date,
    normalize_m720_valuation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ASSET = "m720a_" + "a" * 32
_SOURCE = "test-reference"
# 2025-12-31 is a Wednesday; 2025-06-14 a Saturday whose last publication is Friday the 13th.
_YEAR_END = date(2025, 12, 31)
_CESSATION = date(2025, 6, 13)
_SATURDAY = date(2025, 6, 14)
_USD_RATE = Decimal("0.85")


class _Rates:
    """Answers USD at the published dates, falling back from a Saturday to Friday."""

    rate_source_id = _SOURCE

    def __init__(self) -> None:
        self.asked: list[date] = []

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        self.asked.append(rate_date)
        if currency != "USD":
            return EurRateLookup(status=EurRateLookupStatus.UNSUPPORTED_CURRENCY, rate_date=rate_date, source=_SOURCE)
        if rate_date in {_YEAR_END, _CESSATION}:
            return eur_rate_lookup(_USD_RATE, rate_date=rate_date, source=_SOURCE)
        if rate_date == _SATURDAY:
            return eur_rate_lookup(_USD_RATE, rate_date=rate_date, source=_SOURCE, observation_date=_CESSATION)
        return eur_rate_lookup(None, rate_date=rate_date, source=_SOURCE)


def _value(
    *,
    currency: str = "USD",
    asset_class: M720AssetClassCode = M720AssetClassCode.CUENTA,
    event: M720ValuationEvent = M720ValuationEvent.YEAR_END,
    event_date: date | None = None,
    rates: _Rates | None = None,
):
    return normalize_m720_valuation(
        asset_ref=_ASSET,
        asset_class=asset_class,
        amount=MonetaryAmount(amount=Decimal("1000.00"), currency=currency),
        event=event,
        event_date=event_date,
        filing_year=2025,
        service=CurrencyNormalizationService(rate_provider=rates or _Rates()),
    )


def test_a_year_end_valuation_converts_at_the_31_december_rate() -> None:
    rates = _Rates()

    result = _value(rates=rates)

    assert rates.asked == [_YEAR_END]
    assert result.status is CurrencyNormalizationStatus.NORMALIZED
    assert result.eur_amount == Decimal("850.00")
    assert (result.rate_date, result.rate_source) == (_YEAR_END, _SOURCE)


def test_an_account_cancelled_mid_year_converts_at_the_cessation_date_rate() -> None:
    rates = _Rates()

    result = _value(event=M720ValuationEvent.EXTINCTION, event_date=_CESSATION, rates=rates)

    assert rates.asked == [_CESSATION]
    assert result.eur_amount == Decimal("850.00")


def test_a_euro_amount_is_native_and_asks_no_rate() -> None:
    rates = _Rates()

    result = _value(
        currency="EUR",
        asset_class=M720AssetClassCode.VALOR,
        event=M720ValuationEvent.EXTINCTION,
        event_date=_SATURDAY,
        rates=rates,
    )

    assert rates.asked == []
    assert result.status is CurrencyNormalizationStatus.NATIVE_EUR
    assert result.eur_amount == Decimal("1000.00")


def test_a_currency_without_a_series_is_refused_and_named() -> None:
    with pytest.raises(ForeignAssetValuationRefusedError) as refused:
        _value(currency="XYZ")

    assert refused.value.reason is M720ValuationRefusalReason.UNSUPPORTED_CURRENCY
    assert (refused.value.asset_ref, refused.value.currency, refused.value.rate_date) == (_ASSET, "XYZ", _YEAR_END)


def test_a_rate_missing_at_the_rate_date_is_refused_and_named() -> None:
    # The stub never published 31 December 2024.
    with pytest.raises(ForeignAssetValuationRefusedError) as refused:
        normalize_m720_valuation(
            asset_ref=_ASSET,
            asset_class=M720AssetClassCode.CUENTA,
            amount=MonetaryAmount(amount=Decimal("1000.00"), currency="USD"),
            event=M720ValuationEvent.YEAR_END,
            event_date=None,
            filing_year=2024,
            service=CurrencyNormalizationService(rate_provider=_Rates()),
        )

    assert refused.value.reason is M720ValuationRefusalReason.MISSING_RATE
    assert refused.value.rate_date == date(2024, 12, 31)


def test_no_provider_refuses_a_foreign_amount_rather_than_reading_zero() -> None:
    with pytest.raises(ForeignAssetValuationRefusedError) as refused:
        normalize_m720_valuation(
            asset_ref=_ASSET,
            asset_class=M720AssetClassCode.CUENTA,
            amount=MonetaryAmount(amount=Decimal("1000.00"), currency="USD"),
            event=M720ValuationEvent.YEAR_END,
            event_date=None,
            filing_year=2025,
            service=CurrencyNormalizationService(rate_provider=None),
        )

    assert refused.value.reason is M720ValuationRefusalReason.MISSING_RATE


@pytest.mark.parametrize(
    "asset_class",
    [
        M720AssetClassCode.VALOR,
        M720AssetClassCode.INSTITUCION_INVERSION_COLECTIVA,
        M720AssetClassCode.SEGURO,
        M720AssetClassCode.BIEN_INMUEBLE,
    ],
)
def test_a_foreign_extinction_outside_accounts_is_refused_as_unsettled(asset_class: M720AssetClassCode) -> None:
    rates = _Rates()

    with pytest.raises(ForeignAssetValuationRefusedError) as refused:
        _value(asset_class=asset_class, event=M720ValuationEvent.EXTINCTION, event_date=_CESSATION, rates=rates)

    assert refused.value.reason is M720ValuationRefusalReason.EXTINCTION_RATE_UNSETTLED
    assert rates.asked == []


def test_an_extinction_on_a_non_publication_day_is_refused_rather_than_falling_back() -> None:
    with pytest.raises(ForeignAssetValuationRefusedError) as refused:
        _value(event=M720ValuationEvent.EXTINCTION, event_date=_SATURDAY)

    assert refused.value.reason is M720ValuationRefusalReason.EXTINCTION_RATE_NOT_PUBLISHED
    assert refused.value.rate_date == _SATURDAY


@pytest.mark.parametrize(
    ("event", "event_date", "message"),
    [
        (M720ValuationEvent.YEAR_END, _CESSATION, "carries no event date"),
        (M720ValuationEvent.EXTINCTION, None, "requires its extinction date"),
        (M720ValuationEvent.EXTINCTION, date(2024, 12, 1), "outside the declared year"),
    ],
)
def test_an_incoherent_valuation_event_is_refused(
    event: M720ValuationEvent, event_date: date | None, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        m720_valuation_rate_date(event=event, event_date=event_date, filing_year=2025)
