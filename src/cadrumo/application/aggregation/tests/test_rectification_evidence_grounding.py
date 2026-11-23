"""A received factura rectificativa is the writer of the ``rectification_evidence`` authority.

Fact 0085 requires that authority of a rectificación de deducciones, and until
the rectificativa could be recorded no path wrote it, so every such row was
refused as a document this application cannot hold. The document now exists in
the catalogue, and it grounds the authority on exactly the LIVA art. 97 test an
ordinary received invoice passes: a stored document belonging to the invoice, or
a movement paying it that carries registered purchase-invoice evidence. The
received side adds the ``document_received_on`` the art. 114.Dos period rule
consumes, because a row with no reception date is the Libro entry rather than
the document.

Real-behaviour: real invoices and real movements through the real art. 97
document test. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.invoice_legal_classification import (
    resolve_invoice_legal_classification_catalogue,
)
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.invoices.enums import InvoiceClass, IvaRate, PaymentStatus
from ....domain.invoices.models import INVOICE_WRITE_ADMISSION, Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..invoice_iva_source import (
    invoices_missing_source_document,
    rectification_evidence_grounding_invoices,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "5e5e5e5e-5e5e-4e5e-8e5e-5e5e5e5e5e5e"
_YEAR = filing_year_envelope().horizon
_ISSUED_AT = date(_YEAR, 5, 12)
_RECEIVED_ON = date(_YEAR, 5, 20)
_NOW = datetime(_YEAR, 5, 20, 12, tzinfo=UTC)
_RATE_21 = IvaRate.from_registry("RATE_21")
_BASE = Decimal("100.00")
_CUOTA = Decimal("21.00")
_NO_DOCUMENTS = frozenset[str]()
_NO_MOVEMENTS = TransactionCatalogue.from_transactions(())


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Read invoices under the generation-pinned authority production uses."""
    with bundled_indexed_authority().operation():
        yield


def _invoice(**overrides: Any) -> Invoice:
    payload: dict[str, Any] = {
        "bucket_id": _BUCKET_ID,
        "kind": InvoiceKind.RECEIVED,
        "invoice_class": InvoiceClass.from_registry("ORDINARIA"),
        "invoice_number": "2026/F-0001",
        "issued_at": _ISSUED_AT,
        "counterparty_name": "Proveedor SL",
        "counterparty_tax_id": "B00015016",
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA,
        "currency": "EUR",
        "lines": (
            InvoiceLine(
                description="Servicios profesionales",
                quantity=Decimal("1"),
                unit_price=_BASE,
                subtotal=_BASE,
                iva_rate=_RATE_21,
                iva_amount=_CUOTA,
            ),
        ),
        "payment_status": PaymentStatus.PENDING,
    }
    payload.update(overrides)
    return Invoice.model_validate(payload, context=INVOICE_WRITE_ADMISSION)


def _rectificativa(**overrides: Any) -> Invoice:
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    payload: dict[str, Any] = {
        "invoice_class": InvoiceClass.from_registry("RECTIFICATIVA"),
        "series": "R",
        "invoice_number": "2026/R-0001",
        "rectifies_invoice_number": "2026/F-0001",
        "rectification_method": str(catalogue.diferencia_token),
        "rectification_cause": "art_80_dos",
        "rectification_direction": str(catalogue.minoracion_token),
        "document_received_on": _RECEIVED_ON,
    }
    payload.update(overrides)
    return _invoice(**payload)


def _paying_movement(*, invoice_id: str, evidence_id: str | None) -> Transaction:
    """A movement that pays the rectificativa, with or without registered invoice evidence."""
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="rectificativa-refund",
                booked_date=_RECEIVED_ON,
                amount=_BASE + _CUOTA,
                currency="EUR",
                description="Abono de la factura rectificativa",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="b" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=_NOW,
                    provider_name="manual",
                ),
                raw_fields={},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "invoice_id": invoice_id,
            "purchase_invoice_evidence_id": evidence_id,
        }
    )


def test_a_received_rectificativa_holding_its_document_and_its_reception_date_grounds_the_authority() -> None:
    """The stored document plus the art. 114.Dos reception date is the whole test."""
    rectificativa = _rectificativa()

    grounding = rectification_evidence_grounding_invoices(
        (rectificativa,),
        documented=frozenset({rectificativa.invoice_id}),
        window=_NO_MOVEMENTS,
    )

    assert grounding == (rectificativa,)


def test_a_paying_movement_carrying_registered_purchase_invoice_evidence_grounds_it_too() -> None:
    """The second half of the LIVA art. 97 test the ordinary received invoice already passes."""
    rectificativa = _rectificativa()
    window = TransactionCatalogue.from_transactions(
        (_paying_movement(invoice_id=rectificativa.invoice_id, evidence_id="a" * 64),)
    )

    grounding = rectification_evidence_grounding_invoices(
        (rectificativa,),
        documented=_NO_DOCUMENTS,
        window=window,
    )

    assert tuple(invoice.invoice_id for invoice in grounding) == (rectificativa.invoice_id,)


def test_a_rectificativa_whose_document_the_records_do_not_hold_grounds_nothing_and_is_named_to_attach() -> None:
    """The row is the Libro entry, and the art. 97 gate names the invoice to attach the document to."""
    rectificativa = _rectificativa()
    window = TransactionCatalogue.from_transactions(
        (_paying_movement(invoice_id=rectificativa.invoice_id, evidence_id=None),)
    )

    assert (
        rectification_evidence_grounding_invoices(
            (rectificativa,),
            documented=_NO_DOCUMENTS,
            window=window,
        )
        == ()
    )
    missing = invoices_missing_source_document((rectificativa,), documented=_NO_DOCUMENTS, window=window)
    assert tuple(invoice.invoice_id for invoice in missing) == (rectificativa.invoice_id,)


def test_a_received_rectificativa_with_no_reception_date_grounds_nothing() -> None:
    """Art. 114.Dos places the recipient's modification by the date the document arrived."""
    rectificativa = _rectificativa(document_received_on=None)

    grounding = rectification_evidence_grounding_invoices(
        (rectificativa,),
        documented=frozenset({rectificativa.invoice_id}),
        window=_NO_MOVEMENTS,
    )

    assert grounding == ()


def test_an_issued_rectificativa_and_an_ordinary_received_invoice_ground_nothing() -> None:
    """The authority is the recipient's deduction evidence; neither of these establishes one."""
    issued = _rectificativa(kind=InvoiceKind.ISSUED, document_received_on=None)
    ordinary = _invoice()

    grounding = rectification_evidence_grounding_invoices(
        (issued, ordinary),
        documented=frozenset({issued.invoice_id, ordinary.invoice_id}),
        window=_NO_MOVEMENTS,
    )

    assert grounding == ()
