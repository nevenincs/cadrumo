"""Strict roundtrip across the encrypted InvoiceCatalogue boundary.

:class:`InvoiceCatalogueRepository` persists :class:`InvoiceCatalogue`
(a keyed mapping of typed :class:`Invoice` records) through
:class:`SecureObjectRepository` at ``SensitivityClass.FINANCIAL``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_path
from .....domain.invoices.enums import IvaRate, PaymentStatus
from .....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from .....domain.iva.classification import InvoiceKind
from .....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ...storage.secure_object_namespaces import INVOICE_CATALOGUE_NAMESPACE
from ..invoices import InvoiceCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _populated_invoice(invoice_number: str = "F-2025-001") -> Invoice:
    """Build a typed Invoice with every field set to a non-default value."""

    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": invoice_number,
            "issued_at": date(2025, 3, 15),
            "counterparty_name": "Test Counterparty GmbH",
            # German IVA id; bypasses the AEAT CIF checksum since the
            # invoice domain accepts any non-Spanish counterparty.
            "counterparty_tax_id": "DE123456789",
            "counterparty_country": "DE",
            "base_total": Decimal("1000.00"),
            "iva_total": Decimal("210.00"),
            "grand_total": Decimal("1210.00"),
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="Consultoría tecnológica",
                    quantity=Decimal("10"),
                    unit_price=Decimal("100.00"),
                    subtotal=Decimal("1000.00"),
                    iva_rate=IvaRate.RATE_21,
                    iva_amount=Decimal("210.00"),
                    spending_category_id="consultoria",
                ),
            ),
            "payment_status": PaymentStatus.PENDING,
            "linked_transaction_ids": ("a" * 64,),
            "notes": "Test invoice for roundtrip coverage.",
        },
    )


def test_invoice_catalogue_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A populated InvoiceCatalogue saved through the repository loads back equal."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        invoice_a = _populated_invoice(invoice_number="F-2025-001")
        invoice_b = _populated_invoice(invoice_number="F-2025-002")
        original = InvoiceCatalogue(
            invoices={
                invoice_a.invoice_id: invoice_a,
                invoice_b.invoice_id: invoice_b,
            },
        )

        repo = InvoiceCatalogueRepository()
        repo.save(original)
        loaded = repo.load()

        assert loaded == original
        assert set(loaded.invoices) == {invoice_a.invoice_id, invoice_b.invoice_id}
        loaded_a = loaded.invoices[invoice_a.invoice_id]
        assert loaded_a.kind is InvoiceKind.ISSUED
        assert loaded_a.payment_status is PaymentStatus.PENDING
        assert loaded_a.base_total == Decimal("1000.00")
        assert loaded_a.iva_total == Decimal("210.00")
        assert loaded_a.grand_total == Decimal("1210.00")
        assert loaded_a.linked_transaction_ids == ("a" * 64,)
        assert len(loaded_a.lines) == 1
        loaded_line = loaded_a.lines[0]
        assert loaded_line.iva_rate is IvaRate.RATE_21
        assert loaded_line.quantity == Decimal("10")
        assert loaded_line.iva_amount == Decimal("210.00")
        assert loaded_line.spending_category_id == "consultoria"


def test_invoice_catalogue_persists_only_to_the_secure_database_object(
    tmp_path: Path,
) -> None:
    """A saved catalogue never reaches the plaintext ``financial/invoices`` directory.

    :data:`StorageCategory.INVOICES` now declares
    no consumer at all. Its only one was the master-key rotation sweep,
    deleted with the shared-master model it belonged to, and even then that
    module only walked the directory looking for ``.envelope.json`` files to
    re-encrypt -- it was a sweep, never a writer. :class:`InvoiceCatalogueRepository`'s own module
    docstring states "no plaintext invoice row, JSON catalogue, or
    envelope file lands on disk"; this proves it, mirroring
    ``test_put_file_reads_source_but_persists_only_secure_database_object``
    for the attachments store. The assertion routes through
    :func:`storage_path` rather than a literal so a future taxonomy subpath
    move is tracked automatically instead of silently passing vacuously
    against a stale path.
    """

    with isolated_runtime_profile(tmp_path=tmp_path):
        invoice = _populated_invoice(invoice_number="F-2025-DORMANCY")
        original = InvoiceCatalogue(invoices={invoice.invoice_id: invoice})
        repo = InvoiceCatalogueRepository()
        repo.save(original)

        assert repo.load() == original
        assert not storage_path(StorageCategory.INVOICES).exists()


def test_invoice_catalogue_tampered_identity_field_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology proof: mutating an identity-bearing invoice field must surface.

    :class:`Invoice` derives ``invoice_id`` from the identity tuple
    (kind, invoice_number, issued_at, counterparty_tax_id, currency,
    grand_total) via :func:`derive_invoice_id`. The model's
    construction-time validator re-derives the id and refuses any
    record whose stored ``invoice_id`` doesn't match.

    Persists a catalogue, reaches into ``SecureObjectRow`` via
    ``session_scope``, surgically mutates the persisted
    ``invoice_number`` from ``"F-2025-001"`` to ``"F-2025-999"``
    without recomputing ``invoice_id``, and asserts the load path
    catches the drift via the content-addressed id check.

    If this test passes silently with a tampered invoice_number,
    the invoice catalogue boundary is tautological and the
    content-addressed identity is not actually enforced
    post-persistence.
    """

    from sqlalchemy import select

    from ...storage.sql import SecureObjectRow

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        invoice = _populated_invoice(invoice_number="F-2025-001")
        catalogue = InvoiceCatalogue(invoices={invoice.invoice_id: invoice})
        repo = InvoiceCatalogueRepository()
        repo.save(catalogue)

        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == INVOICE_CATALOGUE_NAMESPACE.namespace,
        )

        def mutate(envelope):
            invoices = envelope["payload"]["invoices"]
            invoice_dict = invoices[invoice.invoice_id]
            assert invoice_dict["invoice_number"] == "F-2025-001", (
                "fixture must serialise the invoice_number for this proof test to be meaningful"
            )
            invoice_dict["invoice_number"] = "F-2025-999"

        mutate_encrypted_secure_object_json(profile.repository._engine, row_statement=stmt, mutate=mutate)

        with pytest.raises(ValidationError):
            repo.load()
