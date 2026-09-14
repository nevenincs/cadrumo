"""Inward tests for catalogue-invoice lifecycle validation.

Encrypted persistence integration for create, update, and remove lives in the
profile-persistence adapter test owner. This module keeps the application
resolution rules and the structural patch contract independent of storage.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.invoices.errors import InvoiceNotFoundError, InvoiceValidationError
from ....domain.invoices.models import Invoice, InvoiceCatalogue
from ....domain.iva.classification import InvoiceKind
from ..catalogue_creation import build_catalogue_invoice
from ..catalogue_lifecycle import CatalogueInvoicePatch, resolve_catalogue_invoice

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "20202020-2020-4202-8202-202020202020"
_COUNTERPARTY_CIF = "A58818501"


def _build(invoice_number: str) -> Invoice:
    return build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id=_COUNTERPARTY_CIF,
        counterparty_country="ES",
        invoice_number=invoice_number,
        issued_at=date(2026, 3, 10),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
    )


def test_resolve_catalogue_invoice_by_full_id_and_unambiguous_prefix() -> None:
    """An exact id wins, and a prefix matching exactly one invoice resolves."""
    invoice = _build("2026-0142")
    catalogue = InvoiceCatalogue.from_invoices([invoice])

    assert resolve_catalogue_invoice(catalogue, invoice.invoice_id) == invoice
    assert resolve_catalogue_invoice(catalogue, invoice.invoice_id[:8]) == invoice


def test_resolve_catalogue_invoice_blank_id_refused() -> None:
    """A blank id is refused with the typed required-id error, not a miss."""
    catalogue = InvoiceCatalogue.from_invoices([_build("2026-0142")])
    with pytest.raises(InvoiceNotFoundError) as exc:
        resolve_catalogue_invoice(catalogue, "   ")
    assert exc.value.translated_message == "application.invoices.lifecycle.errors.invoice_id_required"


def test_resolve_catalogue_invoice_not_found_names_the_id() -> None:
    """An id matching no invoice raises the localized not-found error with context."""
    catalogue = InvoiceCatalogue.from_invoices([_build("2026-0142")])
    with pytest.raises(InvoiceNotFoundError) as exc:
        resolve_catalogue_invoice(catalogue, "deadbeefdeadbeef")
    assert exc.value.translated_message == "application.invoices.lifecycle.errors.invoice_not_found"
    assert exc.value.context == {"invoice_id": "deadbeefdeadbeef"}


def test_resolve_catalogue_invoice_ambiguous_prefix_names_candidates() -> None:
    """A prefix matching more than one invoice is refused, never first-wins."""
    members: list[Invoice] = []
    seen: dict[str, Invoice] = {}
    for index in range(64):
        invoice = _build(f"2026-{index:04d}")
        head = invoice.invoice_id[0]
        members.append(invoice)
        if head in seen:
            shared_char = head
            break
        seen[head] = invoice
    else:
        raise AssertionError("could not generate two invoices sharing a leading hex character")

    with pytest.raises(InvoiceValidationError) as exc:
        resolve_catalogue_invoice(InvoiceCatalogue.from_invoices(members), shared_char)
    assert exc.value.translated_message == "application.invoices.lifecycle.errors.ambiguous_invoice_prefix"
    assert exc.value.context is not None
    candidates = exc.value.context["candidates"]
    assert isinstance(candidates, str)
    assert all(invoice.invoice_id in candidates for invoice in members if invoice.invoice_id.startswith(shared_char))


def test_the_patch_model_cannot_express_an_identity_change() -> None:
    """Identity-bearing fields are absent from the correction payload."""
    identity_fields = {
        "kind",
        "invoice_number",
        "issued_at",
        "counterparty_tax_id",
        "currency",
        "base_total",
        "iva_total",
        "grand_total",
        "recargo_amount",
        "lines",
    }

    assert identity_fields.isdisjoint(set(CatalogueInvoicePatch.model_fields))
