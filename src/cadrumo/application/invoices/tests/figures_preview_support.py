"""Drafts, rate sources and constants the invoice figures-preview tests share."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from typing import Any
from uuid import UUID

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.currency.models import EurRateLookup, EurRateLookupStatus
from ....domain.iva.schema import InvoiceKind
from ...operations.public_scalar import PublicDecimal
from ..catalogue_creation_ports import CatalogueInvoiceRateError
from ..figures_preview_contracts import InvoiceFiguresPreviewLine, InvoiceFiguresPreviewRequest
from ..figures_preview_operation import preview_invoice_figures

_YEAR = filing_year_envelope().horizon

PROFILE = UUID("5aa00000-0000-4000-8000-0000000000bb")
APRIL = date(_YEAR, 4, 15)
RECORDING_PROFILE = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


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
        "counterparty_tax_id": "B00010157",
        "counterparty_country": "ES",
        "currency": "EUR",
        "lines": lines or (preview_line(),),
    }
    values.update(overrides)
    return InvoiceFiguresPreviewRequest.model_validate(values)


def recorded_preview_result(request: Mapping[str, Any], operation: PinnedAuthorityOperation) -> dict[str, Any]:
    """What the preview answers for the draft ``request`` states, as the desktop recording holds it.

    A recorded draft names no line key, so the lines are keyed by their place the way the command
    that asks the preview keys them.
    """
    lines = [{"key": f"line-{place}", **line} for place, line in enumerate(request.get("lines", ()), start=1)]
    draft = InvoiceFiguresPreviewRequest.model_validate_json(
        json.dumps({**request, "profile_id": str(RECORDING_PROFILE), "lines": lines})
    )
    answer = preview_invoice_figures(draft, operation=operation, rate_provider=NoRate())
    return answer.model_dump(mode="json", exclude={"profile_id"})
