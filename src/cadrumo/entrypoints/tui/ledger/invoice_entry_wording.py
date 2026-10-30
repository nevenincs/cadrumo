"""Localized invoice line and supplemental review wording."""

from __future__ import annotations

from typing import Final

from ....core.i18n.render import tr
from ....domain.invoices.business_premises import SituacionInmueble
from ....domain.invoices.models import InvoiceLine
from .models import LedgerInvoiceEntryV1, LedgerInvoiceLineEntryV1


def invoice_line_row(index: int, line: InvoiceLine | LedgerInvoiceLineEntryV1) -> str:
    """Render one invoice line as its numbered row, for entry review and the detail view alike."""
    return tr(
        "tui.ledger.invoice.line.row",
        index=str(index),
        description=line.description,
        quantity=format(line.quantity, "f"),
        unit_price=format(line.unit_price, "f"),
        subtotal=format(line.subtotal, "f"),
        rate=str(line.iva_rate),
        amount=format(line.iva_amount, "f"),
    )


def _operation_summary_line(entry: LedgerInvoiceEntryV1) -> str | None:
    if entry.operation_type is not None or entry.operation_date is not None:
        return tr(
            "tui.ledger.invoice.summary.operation",
            code="-" if entry.operation_type is None else entry.operation_type.value,
            date="-" if entry.operation_date is None else entry.operation_date.isoformat(),
        )
    return None


def _recargo_summary_line(entry: LedgerInvoiceEntryV1) -> str | None:
    if entry.recargo_amount is not None:
        return tr(
            "tui.ledger.invoice.summary.recargo",
            amount=format(entry.recargo_amount, "f"),
            currency=entry.currency,
        )
    return None


def _rectifies_summary_line(entry: LedgerInvoiceEntryV1) -> str | None:
    if entry.rectifies_invoice_number is not None:
        return tr("tui.ledger.invoice.summary.rectifies", number=entry.rectifies_invoice_number)
    return None


def _retention_summary_line(entry: LedgerInvoiceEntryV1) -> str | None:
    if entry.retention_rate is not None or entry.retention_amount is not None:
        return tr(
            "tui.ledger.invoice.summary.retention",
            rate="-" if entry.retention_rate is None else format(entry.retention_rate, "f"),
            amount="-" if entry.retention_amount is None else format(entry.retention_amount, "f"),
        )
    return None


#: The label of each premises situation, shown instead of its form code.
SITUACION_LOCALE_KEYS: Final[dict[SituacionInmueble, str]] = {
    SituacionInmueble.SPAIN_OTHER_THAN_BASQUE_NAVARRE: "tui.ledger.invoice.situacion.1",
    SituacionInmueble.BASQUE_COUNTRY_OR_NAVARRE: "tui.ledger.invoice.situacion.2",
    SituacionInmueble.SPAIN_WITHOUT_CATASTRAL_REFERENCE: "tui.ledger.invoice.situacion.3",
    SituacionInmueble.ABROAD: "tui.ledger.invoice.situacion.4",
}


def _lease_summary_line(entry: LedgerInvoiceEntryV1) -> str | None:
    if entry.arrendamiento_local_negocio:
        return tr(
            "tui.ledger.invoice.summary.lease",
            situacion="-" if entry.situacion_inmueble is None else tr(SITUACION_LOCALE_KEYS[entry.situacion_inmueble]),
            referencia=entry.referencia_catastral or "-",
        )
    return None


def supplemental_summary_lines(entry: LedgerInvoiceEntryV1) -> list[str]:
    """Render the optional invoice facts in their established order."""
    lines: list[str] = []
    for render_line in (
        _operation_summary_line,
        _recargo_summary_line,
        _rectifies_summary_line,
        _retention_summary_line,
        _lease_summary_line,
    ):
        line = render_line(entry)
        if line is not None:
            lines.append(line)
    return lines
