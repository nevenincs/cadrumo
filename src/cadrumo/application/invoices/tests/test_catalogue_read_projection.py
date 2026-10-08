"""Closed invoice read snapshots retain only the disclosed catalogue facts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.iva.classification import InvoiceKind
from ...exchange_rate_provider import exchange_rate_provider
from ...operations.registry_schema_validation import strict_model_json_schema
from ..catalogue_creation import build_catalogue_invoice
from ..catalogue_read_projection import CatalogueInvoiceSnapshot, InvoiceLineSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _snapshot() -> CatalogueInvoiceSnapshot:
    invoice = build_catalogue_invoice(
        bucket_id="20202020-2020-4202-8202-202020202020",
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="2026-0142",
        issued_at=date(2026, 3, 10),
        taxable_base=Decimal("137.25"),
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=exchange_rate_provider(),
    )
    return CatalogueInvoiceSnapshot.from_invoice(invoice)


def test_snapshot_roundtrip_preserves_amounts_lines_and_absence() -> None:
    snapshot = _snapshot()
    decoded = CatalogueInvoiceSnapshot.model_validate_json(snapshot.model_dump_json())
    assert decoded == snapshot
    assert decoded.base_total.decimal == "137.25"
    assert decoded.grand_total.decimal != decoded.base_total.decimal
    assert decoded.lines[0].description
    assert decoded.lines[0].quantity.decimal == "1"
    assert decoded.fx_rate is None
    assert decoded.retention_amount is None
    assert decoded.source_filename is None
    assert "source_path" not in decoded.model_fields_set
    assert "provenance" not in decoded.model_fields_set
    assert strict_model_json_schema(CatalogueInvoiceSnapshot)


@pytest.mark.parametrize(
    ("field", "value"),
    [("quantity", "0"), ("quantity", "-1"), ("unit_price", "-0.01"), ("iva_amount", "NaN")],
)
def test_line_rejects_invalid_decimal_bounds(field: str, value: str) -> None:
    data = _snapshot().lines[0].model_dump(mode="python")
    data[field] = {"decimal": value}
    with pytest.raises(ValidationError):
        InvoiceLineSnapshot.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("base_total", {"decimal": "-1"}),
        ("fx_rate", {"decimal": "0"}),
        ("source_filename", "C:/private/invoice.csv"),
        ("invoice_number", ""),
        ("counterparty_name", ""),
        ("fx_rate_source", ""),
        ("lines", []),
    ],
)
def test_snapshot_rejects_invalid_public_shape(field: str, value: object) -> None:
    data = _snapshot().model_dump(mode="python")
    data[field] = value
    with pytest.raises(ValidationError):
        CatalogueInvoiceSnapshot.model_validate(data)
