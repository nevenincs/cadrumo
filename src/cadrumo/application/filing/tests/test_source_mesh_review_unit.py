"""Unit coverage for invoice-source approval-basis fingerprints.

See Also:
    :func:`~application.filing.draft_review.invoice_catalogue_fingerprint`
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

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.hashing import content_hash_hex
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.models import Invoice
from ....domain.iva.schema import InvoiceKind
from ...exchange_rate_provider import exchange_rate_provider
from ...invoices.catalogue_creation import build_catalogue_invoice
from ..draft_review import invoice_catalogue_fingerprint

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_RUNTIME_BUCKET_ID = "0fab7c94-777c-4598-ae8f-c4b539f300c3"  # was 'filing-test'
_COUNTERPARTY_CIF = "B00010157"


def _invoice(invoice_number: str, *, taxable_base: Decimal, bucket_id: str = _RUNTIME_BUCKET_ID) -> Invoice:
    return build_catalogue_invoice(
        bucket_id=bucket_id,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id=_COUNTERPARTY_CIF,
        counterparty_country="ES",
        invoice_number=invoice_number,
        issued_at=date(filing_year_envelope().horizon, 3, 10),
        taxable_base=taxable_base,
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=exchange_rate_provider(),
    )


def test_invoice_catalogue_fingerprint_changes_when_an_invoice_changes() -> None:
    before = build_invoice_catalogue([_invoice("2026-0001", taxable_base=Decimal("100.00"))])
    after = build_invoice_catalogue([_invoice("2026-0001", taxable_base=Decimal("250.00"))])

    assert invoice_catalogue_fingerprint(before) != invoice_catalogue_fingerprint(after)


def test_invoice_catalogue_fingerprint_is_deterministic_and_order_independent() -> None:
    invoice_a = _invoice("2026-0001", taxable_base=Decimal("100.00"))
    invoice_b = _invoice("2026-0002", taxable_base=Decimal("200.00"))
    one_order = build_invoice_catalogue([invoice_a, invoice_b])
    other_order = build_invoice_catalogue([invoice_b, invoice_a])

    assert invoice_catalogue_fingerprint(one_order) == invoice_catalogue_fingerprint(other_order)
    rebuilt = build_invoice_catalogue([_invoice("2026-0001", taxable_base=Decimal("100.00")), invoice_b])
    assert invoice_catalogue_fingerprint(rebuilt) == invoice_catalogue_fingerprint(one_order)


def test_invoice_catalogue_fingerprint_distinguishes_empty_from_populated() -> None:
    empty = invoice_catalogue_fingerprint(InvoiceCatalogue())
    populated = invoice_catalogue_fingerprint(
        build_invoice_catalogue([_invoice("2026-0001", taxable_base=Decimal("100.00"))]),
    )

    assert empty != populated
    assert empty == invoice_catalogue_fingerprint(InvoiceCatalogue())


def test_invoice_catalogue_fingerprint_has_core_canonical_digest_parity() -> None:
    invoice_a = _invoice("2026-0001", taxable_base=Decimal("100.00"))
    invoice_b = _invoice("2026-0002", taxable_base=Decimal("200.00"))
    catalogue = build_invoice_catalogue([invoice_b, invoice_a])
    payload = [
        invoice.model_dump(mode="json") for invoice in sorted(catalogue.values(), key=lambda item: item.invoice_id)
    ]

    assert invoice_catalogue_fingerprint(catalogue) == content_hash_hex(payload)
