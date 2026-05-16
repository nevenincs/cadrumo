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


def test_invoice_catalogue_tampered_identity_field_surfaces_at_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    import json as _json

    from sqlalchemy import select

    from ...adapters.persistence.storage.sql._orm import SecureObjectRow
    from ...adapters.persistence.storage.sql.session import session_scope
    from ._repository import _INVOICE_NAMESPACE

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "invoice-anti-tautology.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)
        invoice = _populated_invoice(invoice_number="F-2025-001")
        catalogue = InvoiceCatalogue(invoices={invoice.invoice_id: invoice})
        repo = InvoiceCatalogueRepository()
        repo.save(catalogue)

        with session_scope(engine) as session:
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == _INVOICE_NAMESPACE,
            )
            row = session.execute(stmt).scalar_one()
            envelope = _json.loads(row.payload.decode("utf-8"))
            invoices = envelope["payload"]["invoices"]
            invoice_dict = invoices[invoice.invoice_id]
            assert invoice_dict["invoice_number"] == "F-2025-001", (
                "fixture must serialise the invoice_number for this "
                "proof test to be meaningful"
            )
            # Mutate the identity-bearing invoice_number without
            # recomputing invoice_id. The derive-id check must trip.
            invoice_dict["invoice_number"] = "F-2025-999"
            row.payload = _json.dumps(envelope).encode("utf-8")

        regression_caught = False
        try:
            repo.load()
        except Exception:  # noqa: BLE001 - boundary may raise different types
            regression_caught = True
        assert regression_caught, (
            "anti-tautology proof failed: mutating invoice_number "
            "without recomputing invoice_id did NOT surface on load. "
            "The invoice catalogue boundary is tautological and the "
            "content-addressed identity is not actually enforced "
            "post-persistence."
        )
    finally:
        engine.dispose()
        override_master_key_provider(None)
