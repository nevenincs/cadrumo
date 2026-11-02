"""Drafts, rate sources and constants the invoice figures-preview tests share."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from ....domain.currency.models import EurRateLookup, EurRateLookupStatus
from ....domain.iva.schema import InvoiceKind
from ...operations.public_scalar import PublicDecimal
from ..catalogue_creation_ports import CatalogueInvoiceRateError
from ..figures_preview_contracts import InvoiceFiguresPreviewLine, InvoiceFiguresPreviewRequest

PROFILE = UUID("5aa00000-0000-4000-8000-0000000000bb")
APRIL = date(2026, 4, 15)


class NoRate:
    rate_source_id = "synthetic"

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        return EurRateLookup(status=EurRateLookupStatus.MISSING_RATE, rate_date=rate_date, source="synthetic")


class Unreachable:
    """A rate source whose lookup fails the way the host adapter reports an unreachable provider."""

    rate_source_id = "synthetic"

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        raise CatalogueInvoiceRateError("exchange_rate_lookup")


def public_decimal(value: str | None) -> PublicDecimal | None:
    return None if value is None else PublicDecimal(decimal=value)


def preview_line(
    key: str = "a",
    *,
    description: str | None = "Synthetic service",
    quantity: str | None = "1",
    unit_price: str | None = "100.00",
    iva_rate: str | None = "RATE_21",
    subtotal: str | None = None,
    iva_amount: str | None = None,
) -> InvoiceFiguresPreviewLine:
    return InvoiceFiguresPreviewLine(
        key=key,
        description=description,
        quantity=public_decimal(quantity),
        unit_price=public_decimal(unit_price),
        iva_rate=iva_rate,
        subtotal=public_decimal(subtotal),
        iva_amount=public_decimal(iva_amount),
    )


def preview_draft(*lines: InvoiceFiguresPreviewLine, **overrides: object) -> InvoiceFiguresPreviewRequest:
    values: dict[str, object] = {
        "profile_id": PROFILE,
        "kind": InvoiceKind.RECEIVED,
        "invoice_number": "SYN-2026-001",
        "issued_at": APRIL,
        "counterparty_name": "Synthetic supplier",
        "counterparty_tax_id": "A58818501",
        "counterparty_country": "ES",
        "currency": "EUR",
        "lines": lines or (preview_line(),),
    }
    values.update(overrides)
    return InvoiceFiguresPreviewRequest.model_validate(values)
