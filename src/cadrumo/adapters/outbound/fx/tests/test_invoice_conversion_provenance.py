"""ECB-backed invoice conversion integration at the outbound adapter seam."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.adapters.outbound.fx.ecb_provider import ECB_RATE_SOURCE_ID, EcbReferenceRateProvider
from cadrumo.application.invoices.catalogue_creation import build_catalogue_invoice
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.tests.ecb_stub import ecb_csv_fetch

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

_BUCKET_ID = "39393939-3939-4939-8939-393939393939"
_QUOTE_DATE = date(2025, 3, 14)
_ECB_USD_QUOTE = Decimal("1.0889")
_EXPECTED_USD_RATE = Decimal("1") / _ECB_USD_QUOTE
_BASE = Decimal("1000.00")


def _rated_provider() -> EcbReferenceRateProvider:
    """Use the real ECB adapter over a deterministic transport."""
    return EcbReferenceRateProvider(fetch=ecb_csv_fetch({"USD": {_QUOTE_DATE: _ECB_USD_QUOTE}}))


def _invoice(*, provider: EcbReferenceRateProvider):
    return build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Überseehandel GmbH",
        counterparty_tax_id="DE811907980",
        counterparty_country="DE",
        invoice_number="OS-2025-0031",
        issued_at=_QUOTE_DATE,
        taxable_base=_BASE,
        iva_rate=None,
        currency="USD",
        rate_provider=provider,
    )


def test_a_rated_ecb_conversion_reaches_the_record_with_full_provenance() -> None:
    """A real ECB adapter conversion preserves rate, date, source, and amount."""
    invoice = _invoice(provider=_rated_provider())

    assert invoice.currency == "USD"
    assert invoice.fx_rate == _EXPECTED_USD_RATE
    assert invoice.fx_rate_date == _QUOTE_DATE
    assert invoice.fx_rate_source == ECB_RATE_SOURCE_ID
    assert invoice.base_total_eur == (_BASE * _EXPECTED_USD_RATE).quantize(Decimal("0.01"))
