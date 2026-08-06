"""Real-behaviour tests for the printed-vs-recorded total cross-check on confirm.

The confirm path DERIVES an invoice's ``grand_total`` from the taxable base and
the registry-resolved rate slot; the figure printed on the document never
overwrites it. These tests pin the other half of that discipline: when the two
disagree, the disagreement is reported rather than discarded.

Builds real text-bearing PDFs in memory (reportlab), stores them through the
real encrypted evidence path, and confirms them through
:func:`~application.ledger.confirm_invoice_draft_from_evidence`. No mocks.

See Also:
    :class:`~application.ledger.PrintedTotalDiscrepancy`
        The record describing a printed-vs-recorded total disagreement.
    :func:`~application.ledger.printed_total_discrepancy`
        The comparison this module exercises.
    :func:`~application.ledger.confirm_invoice_draft_from_evidence`
        Confirm step that carries the discrepancy on its result.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.iva import InvoiceKind
from .._evidence_draft import confirm_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import isolated_settings as isolated_settings
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import secure_objects as secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects"]

# A real Spanish CIF (AEAT checksum-valid).
_SUPPLIER_CIF = "B12345674"

# base 100,00 + cuota 21,00 = 121,00. The printed total equals the derived one.
_COHERENT_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2026-0142",
    "Fecha: 10/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

# A recargo de equivalencia invoice (LIVA art. 161): the supplier repercutes
# 5,20 on the entrega, so the document totals 126,20 while base + cuota is
# 121,00. The recargo has nowhere to go on the confirm path, so the record
# understates the document by exactly the surcharge -- which is the whole point
# of the cross-check.
_RECARGO_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2026-0199",
    "Fecha: 11/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Recargo de equivalencia 5,2%: 5,20",
    "Total factura: 126,20",
)


def _text_pdf_bytes(lines: tuple[str, ...]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    page = canvas.Canvas(buf, pagesize=A4)
    y = 760
    for line in lines:
        page.drawString(72, y, line)
        y -= 20
    page.save()
    return buf.getvalue()


def _confirm(
    lines: tuple[str, ...],
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    filename: str,
):
    pdf_path = tmp_path / filename
    pdf_path.write_bytes(_text_pdf_bytes(lines))
    svc = _make_svc(isolated_settings, secure_objects)
    record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
    return confirm_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        evidence_id=record.evidence_id,
        counterparty_name="Acme Suministros SL",
        settings=isolated_settings,
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
    )


def test_a_recargo_invoice_reports_the_printed_total_it_could_not_represent(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The document totals 126,20; the record carries 121,00 and says so.

    This is the silent under-declaration the cross-check exists to catch: the
    recargo is a real amount the supplier charged, the record cannot hold it,
    and before this check the 5,20 simply vanished behind a valid-looking
    invoice.
    """
    result = _confirm(
        _RECARGO_INVOICE_LINES,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        filename="factura_recargo.pdf",
    )

    # The derived total still wins -- the printed figure never overwrites it.
    assert result.invoice.grand_total == Decimal("121.00")

    discrepancy = result.total_discrepancy
    assert discrepancy is not None, "a 5,20 recargo must not vanish silently"
    assert discrepancy.printed_total == Decimal("126.20")
    assert discrepancy.recorded_total == Decimal("121.00")
    # Positive difference is the under-declaration direction.
    assert discrepancy.difference == Decimal("5.20")


def test_a_coherent_invoice_reports_no_discrepancy(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """An advisory that fires on a clean document trains operators to ignore it.

    The negative control: base + cuota equals the printed total, so there is
    nothing to report and nothing is reported.
    """
    result = _confirm(
        _COHERENT_INVOICE_LINES,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        filename="factura.pdf",
    )

    assert result.invoice.grand_total == Decimal("121.00")
    assert result.total_discrepancy is None


def test_the_guarded_no_op_retry_still_reports_the_discrepancy(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """A re-confirm must not be a way to clear the alert.

    The second confirm resolves to the same identity and returns the existing
    invoice unchanged (``created=False``). If the discrepancy were computed only
    on the minting branch, an operator who re-ran the command would see a clean
    result for a document that still disagrees with its record.
    """
    pdf_path = tmp_path / "factura_recargo.pdf"
    pdf_path.write_bytes(_text_pdf_bytes(_RECARGO_INVOICE_LINES))
    svc = _make_svc(isolated_settings, secure_objects)
    record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record

    def _run():
        return confirm_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            settings=isolated_settings,
            invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
        )

    first = _run()
    second = _run()

    assert first.created is True
    assert second.created is False, "the retry must be the guarded no-op, not a second row"
    assert second.total_discrepancy is not None, "a retry must not clear the alert"
    assert second.total_discrepancy.difference == Decimal("5.20")
