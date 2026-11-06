"""Pure printed-total notice checks over the closed confirmation projection."""

from __future__ import annotations

import pytest

from ....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from ....application.ledger.invoice_evidence_operation_dtos import (
    InvoiceConfirmationProjectionV1,
    InvoiceDraftProjectionV1,
    PrintedTotalDiscrepancyProjectionV1,
)
from ....application.operations.public_scalar import PublicDecimal
from ....core.json_contract import NoticeSeverity
from ..ledger_evidence_commands import evidence_confirm_notices
from .ledger_invoice_snapshot_support import received_invoice_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MISMATCH_NOTICE_CODE = "ledger.evidence.confirm.printed_total_mismatch"


def _invoice() -> CatalogueInvoiceSnapshot:
    """Build a complete snapshot whose recorded total stays canonical."""
    return received_invoice_snapshot(counterparty_tax_id="ESB00015016")


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

    notices = evidence_confirm_notices(confirmation)
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

    assert all(notice.code != _MISMATCH_NOTICE_CODE for notice in evidence_confirm_notices(confirmation))
