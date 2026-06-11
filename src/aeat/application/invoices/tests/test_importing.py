"""Invoice import service tests."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.invoices import InvoiceCatalogue, InvoiceValidationError
from ....domain.iva import InvoiceKind
from .. import import_invoices_from_path, merge_invoice_import, parse_invoice_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _invoice_payload(invoice_number: str) -> dict[str, object]:
    return {
        "invoice_number": invoice_number,
        "issued_at": date(2026, 4, 1).isoformat(),
        "counterparty_tax_id": "B12345674",
        "base_total": "100.00",
        "iva_total": "21.00",
        "grand_total": "121.00",
        "iva_rate": "21",
    }


def test_parse_json_payload_synthesises_valid_invoice_line() -> None:
    invoices = parse_invoice_payload(json.dumps([_invoice_payload("INV-001")]), default_kind=InvoiceKind.ISSUED)

    assert len(invoices) == 1
    invoice = invoices[0]
    assert invoice.kind is InvoiceKind.ISSUED
    assert invoice.currency == "EUR"
    assert invoice.counterparty_country == "ES"
    assert invoice.counterparty_name == "B12345674"
    assert invoice.lines[0].subtotal == Decimal("100.00")
    assert invoice.lines[0].iva_amount == Decimal("21.00")


def test_parse_csv_payload_uses_same_backend_import_contract_as_json() -> None:
    csv_payload = "\n".join(
        [
            "invoice_number,issued_at,counterparty_tax_id,base_total,iva_total,grand_total,iva_rate",
            "INV-002,2026-04-02,B12345674,200.00,20.00,220.00,10",
        ],
    )

    invoices = parse_invoice_payload(csv_payload, default_kind="received")

    assert len(invoices) == 1
    invoice = invoices[0]
    assert invoice.kind is InvoiceKind.RECEIVED
    assert invoice.lines[0].iva_rate.value == "RATE_10"
    assert invoice.grand_total == Decimal("220.00")


def test_invoice_import_merge_is_idempotent_across_repeated_cycles() -> None:
    payloads = [_invoice_payload("INV-003"), _invoice_payload("INV-004")]
    invoices = parse_invoice_payload(json.dumps(payloads), default_kind=InvoiceKind.ISSUED)

    catalogue = InvoiceCatalogue()
    first = merge_invoice_import(catalogue, invoices)
    assert first.catalogue is not None
    assert first.imported == 2
    assert first.skipped == 0

    second = merge_invoice_import(first.catalogue, invoices)
    assert second.catalogue is not None
    assert second.imported == 0
    assert second.skipped == 2
    assert second.catalogue == first.catalogue

    serialised = second.catalogue.model_dump_json()
    restored = InvoiceCatalogue.model_validate_json(serialised)
    third = merge_invoice_import(restored, invoices)
    assert third.imported == 0
    assert third.skipped == 2
    assert third.catalogue == restored


def test_import_from_missing_path_reports_localized_read_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing-invoices.csv"

    with pytest.raises(InvoiceValidationError) as exc_info:
        import_invoices_from_path(missing, kind=InvoiceKind.RECEIVED, dry_run=True)

    assert exc_info.value.translated_message == "application.invoices.importing.errors.import_file_read_failed"
    assert exc_info.value.context == {"path_name": "missing-invoices.csv", "error_type": "FileNotFoundError"}
