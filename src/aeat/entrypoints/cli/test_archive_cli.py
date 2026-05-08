"""CLI smoke tests for ``aeat archive``.

Drives the export and import verbs end-to-end through Typer to confirm
the bundle file written by ``export`` round-trips through ``import``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_master_key_provider,
    override_secret_store,
)
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...domain.invoices._enums import InvoiceKind, IvaRate, PaymentStatus
from ...domain.invoices._models import Invoice, InvoiceCatalogue, InvoiceLine
from ...domain.invoices._repository import InvoiceCatalogueRepository
from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    previous_db = os.environ.get("AEAT_DATABASE_URL")
    os.environ["AEAT_DATABASE_URL"] = f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}"
    dispose_engine()

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
        dispose_engine()
        if previous_db is None:
            os.environ.pop("AEAT_DATABASE_URL", None)
        else:
            os.environ["AEAT_DATABASE_URL"] = previous_db


def _seed_invoice() -> Invoice:
    line = InvoiceLine.model_validate(
        {
            "description": "Service",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        }
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-CLI-001",
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
        }
    )


def test_archive_export_writes_bundle_file(tmp_path: Path) -> None:
    """`aeat archive export <path>` writes a parseable JSON bundle."""
    InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices([_seed_invoice()]))
    bundle_path = tmp_path / "out.json"

    result = _RUNNER.invoke(app, ["archive", "export", str(bundle_path)])
    assert result.exit_code == 0, result.output
    assert bundle_path.exists()

    parsed = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert parsed["bundle_schema_version"] == 1
    assert any(record["namespace"] == "aeat.domain.invoices" for record in parsed["records"])


def test_archive_import_round_trips_after_overwrite(tmp_path: Path) -> None:
    """`aeat archive import <path> --conflict overwrite` restores prior state."""
    original = InvoiceCatalogue.from_invoices([_seed_invoice()])
    InvoiceCatalogueRepository().save(original)
    bundle_path = tmp_path / "out.json"

    export_result = _RUNNER.invoke(app, ["archive", "export", str(bundle_path)])
    assert export_result.exit_code == 0, export_result.output

    # Drop the live invoice; import should restore it.
    from ...adapters.persistence.storage.sql import SecureObjectRepository

    SecureObjectRepository().delete("aeat.domain.invoices", "catalogue")
    assert InvoiceCatalogueRepository().exists() is False

    import_result = _RUNNER.invoke(
        app,
        ["archive", "import", str(bundle_path), "--conflict", "overwrite"],
    )
    assert import_result.exit_code == 0, import_result.output
    reloaded = InvoiceCatalogueRepository().load()
    assert reloaded == original
