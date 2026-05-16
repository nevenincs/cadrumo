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

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ._enums import InvoiceKind, IvaRate, PaymentStatus
from ._models import Invoice, InvoiceCatalogue, InvoiceLine
from ._repository import InvoiceCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_invoice(invoice_number: str = "F-2025-001") -> Invoice:
    """Build a typed Invoice with every field set to a non-default value."""

    return Invoice(
        kind=InvoiceKind.ISSUED,
        invoice_number=invoice_number,
        issued_at=date(2025, 3, 15),
        counterparty_name="Test Counterparty GmbH",
        # German VAT id; bypasses the AEAT CIF checksum since the
        # invoice domain accepts any non-Spanish counterparty.
        counterparty_tax_id="DE123456789",
        counterparty_country="DE",
        base_total=Decimal("1000.00"),
        iva_total=Decimal("210.00"),
        grand_total=Decimal("1210.00"),
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Consultoría tecnológica",
                quantity=Decimal("10"),
                unit_price=Decimal("100.00"),
                subtotal=Decimal("1000.00"),
                iva_rate=IvaRate.RATE_21,
                iva_amount=Decimal("210.00"),
                category_id="consultoria",
            ),
        ),
        payment_status=PaymentStatus.PENDING,
        linked_transaction_ids=("a" * 64,),
        notes="Test invoice for roundtrip coverage.",
    )


def test_invoice_catalogue_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A populated InvoiceCatalogue saved through the repository loads back equal."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "invoice-catalogue-roundtrip.db"
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)

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
        # Per-field witnesses: line tuple, Decimal precision,
        # enum identity, and the linked_transaction_ids tuple all
        # survive the JSON + column-encryption cycle.
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
        assert loaded_line.category_id == "consultoria"
    finally:
        engine.dispose()
        override_master_key_provider(None)
