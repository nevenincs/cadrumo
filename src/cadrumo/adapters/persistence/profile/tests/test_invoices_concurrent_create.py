"""Concurrent invoice-catalogue writes do not discard each other.

The invoice catalogue is a SINGLETON row, so adding one invoice is really
read-whole-catalogue, rebuild, write-whole-catalogue. Performed unguarded, two
operators creating DIFFERENT invoices both read the same catalogue and the later
write silently discards the earlier invoice.

Nothing reports it. The duplicate-identity check in the creation service cannot
see an invoice it never read, so the two invoices never meet and no uniqueness
constraint fires. On a financial catalogue the lost row is a dropped invoice,
which under-declares -- the failure this whole surface exists to prevent.

The sibling ledgers reached this guard first: the assets, inventory and
bienes-inversion documents compose the BARE model persistence, which carried the
guarded seam. The invoice catalogue composes the ENVELOPED one, which had only a
blind save, so it was the singleton the fix had not reached.

Observed deterministically, by landing the interloping write inside the guarded
unit of work's read-to-write window rather than by racing threads.

Real behaviour throughout: a real isolated bucket runtime, the real encrypted
SQL backend, independent repository instances. Nothing is mocked.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....domain.invoices.enums import IvaRate, PaymentStatus
from .....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from .....domain.iva.classification import InvoiceKind
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..invoices import InvoiceCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "5c5c5c5c-5c5c-45c5-8c5c-5c5c5c5c5c5c"

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def _invoice(invoice_number: str) -> Invoice:
    """Build one minimal catalogue invoice attributed to this test's bucket.

    Mirrors the shape the sibling round-trip module builds; the bucket
    attribution is the addition, because the repository refuses a catalogue
    carrying an invoice owned by another bucket on both read and write.
    """
    line = InvoiceLine.model_validate(
        {
            "description": "Consultoría",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        },
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": invoice_number,
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PENDING,
            "linked_transaction_ids": (),
            "bucket_id": _BUCKET_ID,
        },
    )


def _numbers() -> list[str]:
    return sorted(item.invoice_number for item in InvoiceCatalogueRepository().load().invoices.values())


def test_sequential_creates_through_independent_instances_accumulate() -> None:
    """Baseline: two repository instances do not lose an invoice on their own."""
    for number in ("INV-001", "INV-002"):
        repo = InvoiceCatalogueRepository()
        invoice = _invoice(number)
        repo.mutate(
            lambda current, invoice=invoice: InvoiceCatalogue.model_validate(
                {"invoices": {**current.invoices, invoice.invoice_id: invoice}},
            ),
        )

    assert _numbers() == ["INV-001", "INV-002"]


def test_a_concurrent_create_does_not_discard_the_other_invoice() -> None:
    """DISCRIMINATING: the interleaving that used to lose an invoice.

    The interloper lands a SECOND invoice inside the first mutation's
    read-to-write window. Unguarded, the first write would rebuild from the
    catalogue it read before the interloper existed and overwrite it away.
    """
    repo = InvoiceCatalogueRepository()
    interloper_written = False
    first = _invoice("INV-FIRST")

    def _create_one_while_another_lands(current: InvoiceCatalogue) -> InvoiceCatalogue:
        nonlocal interloper_written
        if not interloper_written:
            interloper_written = True
            interloper = _invoice("INV-INTERLOPER")
            InvoiceCatalogueRepository().mutate(
                lambda inner: InvoiceCatalogue.model_validate(
                    {"invoices": {**inner.invoices, interloper.invoice_id: interloper}},
                ),
            )
        return InvoiceCatalogue.model_validate({"invoices": {**current.invoices, first.invoice_id: first}})

    repo.mutate(_create_one_while_another_lands)

    assert _numbers() == ["INV-FIRST", "INV-INTERLOPER"]


def test_the_mutation_is_re_applied_to_the_catalogue_that_actually_won() -> None:
    """The retry re-reads rather than replaying a decision made against a stale catalogue.

    A mutation that inspects what it was handed must see the CURRENT catalogue on
    every attempt. If the guard merely retried the same rebuilt document, a
    duplicate-identity check -- the creation service's, among others -- would be
    judged against a catalogue the write never lands on.
    """
    repo = InvoiceCatalogueRepository()
    seen_counts: list[int] = []
    interloper_written = False
    first = _invoice("INV-FIRST")

    def _record_what_each_attempt_sees(current: InvoiceCatalogue) -> InvoiceCatalogue:
        nonlocal interloper_written
        seen_counts.append(len(current.invoices))
        if not interloper_written:
            interloper_written = True
            interloper = _invoice("INV-INTERLOPER")
            InvoiceCatalogueRepository().mutate(
                lambda inner: InvoiceCatalogue.model_validate(
                    {"invoices": {**inner.invoices, interloper.invoice_id: interloper}},
                ),
            )
        return InvoiceCatalogue.model_validate({"invoices": {**current.invoices, first.invoice_id: first}})

    repo.mutate(_record_what_each_attempt_sees)

    # First attempt saw an empty catalogue; the retry saw the interloper's write.
    assert seen_counts == [0, 1]
    assert _numbers() == ["INV-FIRST", "INV-INTERLOPER"]
