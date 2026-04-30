"""Tests for the governed-persistence InvoiceCatalogue repository."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ...storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ...storage.errors import ClassificationError
from ._enums import InvoiceKind, IvaRate, PaymentStatus
from ._models import Invoice, InvoiceCatalogue, InvoiceLine
from ._repository import InvoiceCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


def _sample_invoice(
    *,
    invoice_number: str = "INV-001",
    grand_total: Decimal = Decimal("121.00"),
) -> Invoice:
    line = InvoiceLine(
        description="Consultoría",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
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
            "grand_total": grand_total,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PENDING,
            "linked_transaction_ids": (),
        }
    )


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "invoice-store"


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path) -> Iterator[None]:
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_secret_store(secret_store)
    try:
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)


class TestEmptyState:
    def test_load_returns_empty_catalogue_when_absent(self, store_dir: Path) -> None:
        repo = InvoiceCatalogueRepository(store_dir=store_dir)
        catalogue = repo.load()
        assert len(catalogue) == 0

    def test_envelope_path_is_under_store_dir(self, store_dir: Path) -> None:
        repo = InvoiceCatalogueRepository(store_dir=store_dir)
        assert repo.envelope_path == store_dir / "invoices.envelope.json"


class TestSaveLoad:
    def test_round_trip(self, store_dir: Path) -> None:
        repo = InvoiceCatalogueRepository(store_dir=store_dir)
        catalogue = InvoiceCatalogue.from_invoices((_sample_invoice(),))
        repo.save(catalogue)

        reloaded = InvoiceCatalogueRepository(store_dir=store_dir).load()
        assert len(reloaded) == 1
        assert next(iter(reloaded.values())).invoice_number == "INV-001"


class TestCiphertextOnDisk:
    """The repository's envelope file is a :class:`CipherEnvelope`.

    No plaintext invoice payload survives on disk."""

    def test_envelope_is_cipher_envelope_at_financial_class(self, store_dir: Path) -> None:
        repo = InvoiceCatalogueRepository(store_dir=store_dir)
        catalogue = InvoiceCatalogue.from_invoices((_sample_invoice(invoice_number="LEAK-CANARY-NUMBER"),))
        repo.save(catalogue)

        envelope_text = repo.envelope_path.read_text(encoding="utf-8")
        assert '"classification":"financial"' in envelope_text
        assert '"encryption":' in envelope_text
        assert "LEAK-CANARY-NUMBER" not in envelope_text
        assert "Cliente SL" not in envelope_text

    def test_classification_mismatch_raises(self, store_dir: Path) -> None:
        from datetime import UTC, datetime

        from ...storage import (
            CipherEnvelope,
            Envelope,
            SensitivityClass,
            save_encrypted_envelope,
        )
        from ...storage._encrypted_columns import _resolve_master_key_provider

        store_dir.mkdir(parents=True, exist_ok=True)
        bad = Envelope[InvoiceCatalogue](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.OPERATIONAL,
            payload=InvoiceCatalogue(),
        )
        save_encrypted_envelope(
            bad,
            store_dir / "invoices.envelope.json",
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=b"aeat.financial.invoices.catalogue.v1",
        )
        repo = InvoiceCatalogueRepository(store_dir=store_dir)
        with pytest.raises(ClassificationError):
            repo.load()
        assert (
            CipherEnvelope.model_validate_json(
                (store_dir / "invoices.envelope.json").read_text(encoding="utf-8")
            ).classification
            is SensitivityClass.OPERATIONAL
        )

    def test_foreign_hkdf_context_refused(self, store_dir: Path) -> None:
        """An envelope written under a different consumer's HKDF context must not load."""
        from datetime import UTC, datetime

        from ...storage import (
            Envelope,
            SensitivityClass,
            save_encrypted_envelope,
        )
        from ...storage._encrypted_columns import _resolve_master_key_provider
        from ...storage.errors import DecryptionError

        store_dir.mkdir(parents=True, exist_ok=True)
        foreign = Envelope[InvoiceCatalogue](
            schema_version=1,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.FINANCIAL,
            payload=InvoiceCatalogue(),
        )
        save_encrypted_envelope(
            foreign,
            store_dir / "invoices.envelope.json",
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=b"aeat.financial.transactions.catalogue.v1",
        )
        repo = InvoiceCatalogueRepository(store_dir=store_dir)
        with pytest.raises(DecryptionError):
            repo.load()


class TestIdempotentResave:
    def test_resave_overwrites_atomically(self, store_dir: Path) -> None:
        repo = InvoiceCatalogueRepository(store_dir=store_dir)
        first = InvoiceCatalogue.from_invoices((_sample_invoice(invoice_number="INV-A"),))
        repo.save(first)

        second = InvoiceCatalogue.from_invoices((_sample_invoice(invoice_number="INV-B"),))
        repo.save(second)

        reloaded = repo.load()
        invoice_numbers = {invoice.invoice_number for invoice in reloaded.values()}
        assert invoice_numbers == {"INV-B"}
