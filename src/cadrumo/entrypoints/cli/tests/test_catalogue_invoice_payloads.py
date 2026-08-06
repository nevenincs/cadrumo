"""Strict wire-contract tests for rich catalogue-invoice payloads."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....application.invoices import build_catalogue_invoice
from ....domain.iva import InvoiceKind
from .._ledger_business_invoice_cli import _catalogue_invoice_payload
from .._ledger_catalogue_invoice_payloads import (
    BulkInvoiceImportRowFailurePayload,
    CatalogueInvoiceImportResult,
    CatalogueInvoiceRecordPayload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _canonical_invoice_payload() -> dict[str, object]:
    invoice = build_catalogue_invoice(
        bucket_id="bucket-001",
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="2026-STRICT-001",
        issued_at=date(2026, 3, 10),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
    )
    return _catalogue_invoice_payload(invoice)


def test_catalogue_invoice_record_projects_a_canonical_invoice() -> None:
    """The rich domain invoice projects without weakening its wire types."""
    payload = CatalogueInvoiceRecordPayload.model_validate(_canonical_invoice_payload())

    assert payload.kind is InvoiceKind.RECEIVED
    assert payload.issued_at == date(2026, 3, 10)
    assert payload.grand_total == Decimal("121.00")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("invoice_id", "bad"),
        ("kind", "bogus"),
        ("issued_at", "not-a-date"),
        ("base_total", Decimal("-1")),
        ("counterparty_tax_id", "12345678A"),
        ("linked_transaction_ids", ["bad"]),
    ],
)
def test_catalogue_invoice_record_refuses_noncanonical_values(field: str, value: object) -> None:
    """Identity, enum, date, total, and linked-id regressions fail at the CLI boundary."""
    payload = _canonical_invoice_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        CatalogueInvoiceRecordPayload.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rows", -1),
        ("created", -1),
        ("skipped_duplicate", -1),
        ("created_invoice_ids", ["bad"]),
    ],
)
def test_catalogue_import_refuses_invalid_counts_and_created_ids(field: str, value: object) -> None:
    """Bulk-import aggregates preserve their canonical non-negative and ID contracts."""
    payload: dict[str, object] = {
        "bucket_id": "bucket-001",
        "rows": 1,
        "created": 1,
        "skipped_duplicate": 0,
        "created_invoice_ids": [_canonical_invoice_payload()["invoice_id"]],
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        CatalogueInvoiceImportResult.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [("row_number", 0), ("field", ""), ("reason", "")],
)
def test_catalogue_import_refusals_require_actionable_row_details(field: str, value: object) -> None:
    """Every refused row preserves the canonical 1-based actionable failure shape."""
    payload: dict[str, object] = {"row_number": 1, "field": "invoice_date", "reason": "invalid date"}
    payload[field] = value

    with pytest.raises(ValidationError):
        BulkInvoiceImportRowFailurePayload.model_validate(payload)
