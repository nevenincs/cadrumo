"""Tests for the ECB euro reference-rate provider."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....domain.currency import CurrencyNormalizationService, CurrencyNormalizationStatus, MonetaryAmount
from .._ecb_provider import EcbReferenceRateProvider, default_ecb_rate_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.fixture
def provider() -> EcbReferenceRateProvider:
    return EcbReferenceRateProvider()


def test_eur_is_identity(provider: EcbReferenceRateProvider) -> None:
    assert provider.get_eur_rate("EUR", date(2026, 1, 2)) == Decimal("1")


def test_get_eur_rate_inverts_ecb_eur_base_quote(provider: EcbReferenceRateProvider) -> None:
    # Bundled 2026-01-02: 1 EUR = 1.1700 USD -> USD->EUR = 1/1.1700.
    assert provider.get_eur_rate("USD", date(2026, 1, 2)) == Decimal("1") / Decimal("1.1700")
    # 1 EUR = 0.8600 GBP -> GBP->EUR = 1/0.8600 (>1, since GBP is stronger).
    rate = provider.get_eur_rate("GBP", date(2026, 1, 2))
    assert rate is not None
    assert rate == Decimal("1") / Decimal("0.8600")
    assert rate > Decimal("1")


def test_non_publication_date_falls_back_to_prior_working_day(provider: EcbReferenceRateProvider) -> None:
    # 2026-01-15 is not in the bundled snapshot; must use 2026-01-02's rate.
    on_15 = provider.get_eur_rate("USD", date(2026, 1, 15))
    on_02 = provider.get_eur_rate("USD", date(2026, 1, 2))
    assert on_15 == on_02


def test_unknown_currency_returns_none(provider: EcbReferenceRateProvider) -> None:
    assert provider.get_eur_rate("JPY", date(2026, 1, 2)) is None


def test_date_before_first_published_returns_none(provider: EcbReferenceRateProvider) -> None:
    assert provider.get_eur_rate("USD", date(2024, 12, 1)) is None


def test_default_provider_is_cached() -> None:
    assert default_ecb_rate_provider() is default_ecb_rate_provider()


def test_normalizer_converts_gbp_to_eur_via_provider() -> None:
    # End-to-end: the service multiplies amount * get_eur_rate, so a GBP amount
    # converts to a larger EUR amount (GBP stronger than EUR).
    service = CurrencyNormalizationService(rate_provider=EcbReferenceRateProvider())
    result = service.normalize(MonetaryAmount(amount=Decimal("1000.00"), currency="GBP"), date(2026, 1, 15))
    assert result.status is CurrencyNormalizationStatus.NORMALIZED
    assert result.eur_amount == (Decimal("1000.00") * (Decimal("1") / Decimal("0.8600"))).quantize(Decimal("0.01"))
    assert result.eur_amount > Decimal("1000.00")
