"""Unit tests for the invoice catalogue service layer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ...iva import InvoiceKind
from .._enums import IvaRate, PaymentStatus
from .._errors import (
    InvoiceCatalogueError,
    InvoiceLinkError,
    InvoiceNotFoundError,
    InvoicePersistenceError,
)
from .._models import Invoice, InvoiceCatalogue, InvoiceLine
from .._service import (
    find_invoice,
    find_unmatched,
    link_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _valid_invoice(
    *,
    invoice_number: str = "INV-001",
    kind: InvoiceKind = InvoiceKind.ISSUED,
    counterparty_name: str = "Cliente SL",
    counterparty_tax_id: str = "B12345674",
    counterparty_country: str = "ES",
    linked_transaction_ids: tuple[str, ...] = (),
) -> Invoice:
    line = InvoiceLine.model_validate(
        {
            "description": "Servicios",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        },
    )
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": invoice_number,
            "issued_at": date(2026, 4, 1),
            "counterparty_name": counterparty_name,
            "counterparty_tax_id": counterparty_tax_id,
            "counterparty_country": counterparty_country,
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": linked_transaction_ids,
        },
    )


def test_persistence_round_trip_preserves_catalogue(tmp_path: Path) -> None:
    """Serialising then deserialising should round-trip the full catalogue."""
    del tmp_path
    catalogue = InvoiceCatalogue.from_invoices(
        [
            _valid_invoice(invoice_number="INV-001"),
            _valid_invoice(invoice_number="INV-002", kind=InvoiceKind.RECEIVED),
        ],
    )
    restored = InvoiceCatalogue.model_validate_json(catalogue.model_dump_json())
    assert restored == catalogue


def test_load_raises_typed_error_for_invalid_json() -> None:
    """Invalid JSON must surface a typed persistence error."""
    with pytest.raises(ValidationError, match=r"json|JSON|Invalid"):
        InvoiceCatalogue.model_validate_json("{not-valid")


def test_find_invoice_returns_none_for_missing_id() -> None:
    """Missing IDs return None rather than raising."""
    catalogue = InvoiceCatalogue.from_invoices([_valid_invoice()])
    assert find_invoice(catalogue, "missing") is None


def test_find_unmatched_filters_by_kind() -> None:
    """find_unmatched returns empty-link invoices, filtered by kind when requested."""
    hex_a = "a" * 64
    issued_unlinked = _valid_invoice(invoice_number="INV-001")
    issued_linked = _valid_invoice(invoice_number="INV-002", linked_transaction_ids=(hex_a,))
    received_unlinked = _valid_invoice(invoice_number="INV-003", kind=InvoiceKind.RECEIVED)
    catalogue = InvoiceCatalogue.from_invoices([issued_unlinked, issued_linked, received_unlinked])

    assert set(find_unmatched(catalogue)) == {issued_unlinked, received_unlinked}
    assert find_unmatched(catalogue, kind=InvoiceKind.ISSUED) == (issued_unlinked,)
    assert find_unmatched(catalogue, kind=InvoiceKind.RECEIVED) == (received_unlinked,)


def test_link_transaction_appends_id_and_returns_new_catalogue() -> None:
    """link_transaction must return a fresh catalogue with the transaction appended."""
    invoice = _valid_invoice()
    catalogue = InvoiceCatalogue.from_invoices([invoice])
    hex_a = "a" * 64

    updated = link_transaction(catalogue, invoice.invoice_id, hex_a)
    assert updated is not catalogue
    original = find_invoice(catalogue, invoice.invoice_id)
    after = find_invoice(updated, invoice.invoice_id)
    assert original is not None and original.linked_transaction_ids == ()
    assert after is not None and after.linked_transaction_ids == (hex_a,)


def test_link_transaction_is_idempotent_on_duplicate() -> None:
    """Re-linking an already-present transaction returns a value-equal catalogue."""
    hex_a = "a" * 64
    invoice = _valid_invoice(linked_transaction_ids=(hex_a,))
    catalogue = InvoiceCatalogue.from_invoices([invoice])
    updated = link_transaction(catalogue, invoice.invoice_id, hex_a)
    assert updated == catalogue


def test_link_transaction_rejects_non_hex_transaction_id() -> None:
    """Invalid transaction IDs must raise a typed link error."""
    invoice = _valid_invoice()
    catalogue = InvoiceCatalogue.from_invoices([invoice])
    with pytest.raises(InvoiceLinkError, match=r"transaction_id|hex"):
        link_transaction(catalogue, invoice.invoice_id, "not-hex")


def test_link_transaction_raises_typed_not_found() -> None:
    """Missing invoice IDs must raise InvoiceNotFoundError."""
    catalogue = InvoiceCatalogue.from_invoices([_valid_invoice()])
    with pytest.raises(InvoiceNotFoundError, match=r"invoice|not|found"):
        link_transaction(catalogue, "nonexistent", "a" * 64)


def test_catalogue_rejects_mapping_with_mismatched_keys() -> None:
    """Mapping keys must match each nested invoice's ``invoice_id``."""
    invoice = _valid_invoice()
    payload = {"invoices": {"wrong-key": invoice}}
    with pytest.raises(ValidationError, match=r"invoice_id|key|mismatch"):
        InvoiceCatalogue.model_validate(payload)


def test_catalogue_error_hierarchy_reachable() -> None:
    """Error subclasses must be catchable through a single parent."""
    with pytest.raises(InvoiceCatalogueError, match=r"surface test"):
        raise InvoicePersistenceError("surface test")
