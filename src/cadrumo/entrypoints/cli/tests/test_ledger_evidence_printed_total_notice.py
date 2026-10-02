"""Pure printed-total notice checks over the closed confirmation projection."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest

from ....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot, InvoiceLineSnapshot
from ....application.ledger.invoice_evidence_operation_dtos import (
    InvoiceConfirmationProjectionV1,
    InvoiceDraftProjectionV1,
    PrintedTotalDiscrepancyProjectionV1,
)
from ....application.operations.public_scalar import PublicDecimal
from ....core.json_contract import NoticeSeverity
from ....domain.invoices.enums import PaymentStatus
from ....domain.iva.classification import InvoiceKind
from .._ledger_evidence_cli import _evidence_confirm_notices

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_INVOICE_ID = "d" * 64
_SOURCE_SHA256 = "b" * 64
_MISMATCH_NOTICE_CODE = "ledger.evidence.confirm.printed_total_mismatch"


def _invoice() -> CatalogueInvoiceSnapshot:
    """Build a complete snapshot whose recorded total stays canonical."""
    return CatalogueInvoiceSnapshot(
        invoice_id=_INVOICE_ID,
        bucket_id=str(_PROFILE_ID),
        kind=InvoiceKind.RECEIVED,
        invoice_number="ES-2026-000019",
        issued_at=date(2026, 3, 11),
        counterparty_name="Acme Suministros SL",
        counterparty_tax_id="ESB12345674",
        counterparty_country="ES",
        base_total=PublicDecimal(decimal="100.00"),
        iva_total=PublicDecimal(decimal="21.00"),
        grand_total=PublicDecimal(decimal="121.00"),
        currency="EUR",
        payment_status=PaymentStatus.PENDING,
        linked_transaction_ids=(),
        source_filename="factura.xml",
        source_sha256=_SOURCE_SHA256,
        source_row_index=None,
        notes="",
        retention_rate=None,
        retention_amount=None,
        recargo_amount=None,
        operation_type=None,
        lines=(
            InvoiceLineSnapshot(
                description="Komponenter",
                quantity=PublicDecimal(decimal="1"),
                unit_price=PublicDecimal(decimal="100.00"),
                subtotal=PublicDecimal(decimal="100.00"),
                iva_rate="21",
                iva_amount=PublicDecimal(decimal="21.00"),
            ),
        ),
        invoice_class="ORDINARIA",
        series=None,
        operation_date=None,
        operation_date_role=None,
        iva_category=None,
        rectifies_invoice_number=None,
        fx_rate=None,
        fx_rate_date=None,
        fx_rate_source=None,
        base_total_eur=None,
        iva_total_eur=None,
        grand_total_eur=None,
    )


def _confirmation(*, printed_total_discrepancy: bool) -> InvoiceConfirmationProjectionV1:
    return InvoiceConfirmationProjectionV1(
        invoice=_invoice(),
        draft=InvoiceDraftProjectionV1(),
        created=True,
        confirmation_id="1" * 16,
        total_discrepancy=(
            PrintedTotalDiscrepancyProjectionV1(
                printed_total=PublicDecimal(decimal="126.20"),
                recorded_total=PublicDecimal(decimal="121.00"),
                difference=PublicDecimal(decimal="5.20"),
            )
            if printed_total_discrepancy
            else None
        ),
    )


def test_mismatch_notice_keeps_printed_and_recorded_totals_distinct() -> None:
    confirmation = _confirmation(printed_total_discrepancy=True)

    notices = _evidence_confirm_notices(confirmation)
    notice = next(row for row in notices if row.code == _MISMATCH_NOTICE_CODE)

    assert confirmation.invoice.grand_total.decimal == "121.00"
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.context == {
        "printed_total": "126.20",
        "recorded_total": "121.00",
        "difference": "5.20",
        "currency": "EUR",
    }


def test_coherent_confirmation_has_no_printed_total_warning() -> None:
    confirmation = _confirmation(printed_total_discrepancy=False)

    assert all(notice.code != _MISMATCH_NOTICE_CODE for notice in _evidence_confirm_notices(confirmation))
