"""Unit coverage for invoice-source approval-basis fingerprints.

See Also:
    :func:`~application.filing._review._invoice_catalogue_fingerprint`
        Order-independent digest helper under test for invoice source changes.
    :class:`~domain.invoices.InvoiceCatalogue`
        Typed invoice collection whose normalized records feed the approval
        basis.
    :func:`~application.invoices.build_catalogue_invoice`
        Application helper used to build real invoice records for the digest
        tests.
    :class:`~domain.iva.InvoiceKind`
        IVA invoice axis carried by the catalogue invoices under test.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.invoices import Invoice, InvoiceCatalogue
from ....domain.iva import InvoiceKind
from ...invoices import build_catalogue_invoice
from .._review import _invoice_catalogue_fingerprint

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RUNTIME_BUCKET_ID = "0fab7c94-777c-4598-ae8f-c4b539f300c3"  # was 'filing-test'
_COUNTERPARTY_CIF = "A58818501"


def _invoice(invoice_number: str, *, taxable_base: Decimal, bucket_id: str = _RUNTIME_BUCKET_ID) -> Invoice:
    return build_catalogue_invoice(
        bucket_id=bucket_id,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id=_COUNTERPARTY_CIF,
        counterparty_country="ES",
        invoice_number=invoice_number,
        issued_at=date(2026, 3, 10),
        taxable_base=taxable_base,
        iva_rate=Decimal("21"),
        currency="EUR",
    )


def test_invoice_catalogue_fingerprint_changes_when_an_invoice_changes() -> None:
    before = InvoiceCatalogue.from_invoices([_invoice("2026-0001", taxable_base=Decimal("100.00"))])
    after = InvoiceCatalogue.from_invoices([_invoice("2026-0001", taxable_base=Decimal("250.00"))])

    assert _invoice_catalogue_fingerprint(before) != _invoice_catalogue_fingerprint(after)


def test_invoice_catalogue_fingerprint_is_deterministic_and_order_independent() -> None:
    invoice_a = _invoice("2026-0001", taxable_base=Decimal("100.00"))
    invoice_b = _invoice("2026-0002", taxable_base=Decimal("200.00"))
    one_order = InvoiceCatalogue.from_invoices([invoice_a, invoice_b])
    other_order = InvoiceCatalogue.from_invoices([invoice_b, invoice_a])

    assert _invoice_catalogue_fingerprint(one_order) == _invoice_catalogue_fingerprint(other_order)
    rebuilt = InvoiceCatalogue.from_invoices([_invoice("2026-0001", taxable_base=Decimal("100.00")), invoice_b])
    assert _invoice_catalogue_fingerprint(rebuilt) == _invoice_catalogue_fingerprint(one_order)


def test_invoice_catalogue_fingerprint_distinguishes_empty_from_populated() -> None:
    empty = _invoice_catalogue_fingerprint(InvoiceCatalogue())
    populated = _invoice_catalogue_fingerprint(
        InvoiceCatalogue.from_invoices([_invoice("2026-0001", taxable_base=Decimal("100.00"))]),
    )

    assert empty != populated
    assert empty == _invoice_catalogue_fingerprint(InvoiceCatalogue())
