"""Invoice catalogue source-mesh resolver tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from ...adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_secret_store,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.resources import resources
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceKind,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ...domain.iva import IvaCategory
from ..aggregation import CalculationSourceContext
from . import InvoiceCatalogueSourceResolver

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_BUCKET_ID = "bucket-invoices"
_OTHER_BUCKET_ID = "bucket-other"


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[Engine]:
    provider = EphemeralMasterKeyProvider()
    with provider:
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
        engine = create_engine(f"sqlite:///{tmp_path / 'aeat.db'}")
        try:
            yield engine
        finally:
            engine.dispose()
            override_secret_store(None)


def _invoice(
    *,
    bucket_id: str,
    invoice_number: str,
    issued_at: date,
    counterparty_tax_id: str,
    base_total: Decimal,
    iva_category: IvaCategory,
) -> Invoice:
    return Invoice(
        bucket_id=bucket_id,
        kind=InvoiceKind.ISSUED,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_name="EU Customer GmbH",
        counterparty_tax_id=counterparty_tax_id,
        counterparty_country="DE",
        base_total=base_total,
        iva_total=Decimal("0"),
        grand_total=base_total,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Intra-community service",
                quantity=Decimal("1"),
                unit_price=base_total,
                subtotal=base_total,
                iva_rate=IvaRate.RATE_0,
                iva_amount=Decimal("0"),
            ),
        ),
        payment_status=PaymentStatus.PENDING,
        iva_category=iva_category,
        linked_transaction_ids=("1" * 64,),
    )


def test_invoice_catalogue_source_resolver_emits_scalar_values_and_provenance(secure_engine: Engine) -> None:
    repository = InvoiceCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine))
    declarable = _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="F-2026-001",
        issued_at=date(2026, 1, 15),
        counterparty_tax_id="DE123456789",
        base_total=Decimal("1000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    )
    other_bucket = _invoice(
        bucket_id=_OTHER_BUCKET_ID,
        invoice_number="F-2026-002",
        issued_at=date(2026, 1, 16),
        counterparty_tax_id="DE987654321",
        base_total=Decimal("500.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
    )
    domestic = _invoice(
        bucket_id=_BUCKET_ID,
        invoice_number="F-2026-003",
        issued_at=date(2026, 1, 17),
        counterparty_tax_id="DE111111125",
        base_total=Decimal("250.00"),
        iva_category=IvaCategory.DOMESTIC_ZERO,
    )
    repository.save(InvoiceCatalogue.from_invoices((declarable, other_bucket, domestic)))
    snapshot = resources().modelos.authority.snapshot("349", filing_year=2026, period="1T")

    resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period="1T",
            revision=snapshot.revision,
        )
    )

    assert resolution.owned_sources == ("collectible_invoice", "payable_invoice")
    assert resolution.binding_values["vat-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["vat-349-declarante-importe-operaciones"] == Decimal("1000.00")
    assert resolution.source_transaction_ids == ("1" * 64,)
    assert {item.source_kind for item in resolution.provenance} == {"collectible_invoice"}
    assert {item.source_ref for item in resolution.provenance} == {f"collectible_invoice:{declarable.invoice_id}"}
    assert all(item.fingerprint and item.fingerprint.startswith("sha256:") for item in resolution.provenance)
