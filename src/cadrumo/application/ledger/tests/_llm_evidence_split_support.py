"""Shared support for evidence-driven LLM split application tests."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.categories import SpendingCategory
from ....domain.invoices import Invoice, InvoiceCatalogue, InvoiceLine, IvaRate, PaymentStatus
from ....domain.iva import InvoiceKind, IvaCategory
from ....domain.transactions import (
    LLMSplitChild,
    LLMSplitResponse,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    prompt_spec_with_saturation_fields,
)
from ....tests.secure_sql import isolated_runtime_profile
from ._subprocess_classifier_support import SubprocessLLMClassifier

_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
_BUCKET = "c8bef9e4-b162-4bea-b33d-332c607f0ed1"  # was 'bucket-split'


def _split_subprocess_proposer(*, response: LLMSplitResponse, model: str = "test-model") -> SubprocessLLMClassifier:
    response_json = response.model_dump_json()
    script = f"""
import sys

sys.stdin.read()
print({response_json!r})
"""
    return SubprocessLLMClassifier(
        name="claude",
        command=(sys.executable, "-c", script),
        model=model,
        spec=prompt_spec_with_saturation_fields(),
    )


def _two_line_proposal() -> LLMSplitResponse:
    """A 60/40 two-child proposal, both domestic-general 21% business lines."""
    return LLMSplitResponse(
        children=(
            LLMSplitChild(
                proportion=Decimal("0.6"),
                category=SpendingCategory.MATERIAL_OFICINA,
                iva_category=IvaCategory.DOMESTIC_GENERAL,
                evidence_citation="material de oficina",
            ),
            LLMSplitChild(
                proportion=Decimal("0.4"),
                category=SpendingCategory.SOFTWARE_SUSCRIPCION,
                iva_category=IvaCategory.DOMESTIC_GENERAL,
                evidence_citation="licencia software",
            ),
        ),
        reason="invoice has two distinct line items",
    )


def _single_line_proposal() -> LLMSplitResponse:
    """A single-child proposal: the model's no-split warranted verdict."""
    return LLMSplitResponse(
        children=(
            LLMSplitChild(
                proportion=Decimal("1.0"),
                category=SpendingCategory.MATERIAL_OFICINA,
                iva_category=IvaCategory.DOMESTIC_GENERAL,
                evidence_citation="material de oficina",
            ),
        ),
        reason="invoice is a single line at one rate",
    )


@pytest.fixture
def repositories(
    tmp_path: Path,
) -> Iterator[tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository]]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        objects = profile.repository
        yield (
            TransactionCatalogueRepository(bucket_id=_BUCKET, objects=objects),
            BucketEventHistoryRepository(objects=objects),
            objects,
        )


def _seed_received_invoice(objects: SecureObjectRepository, *, invoice_number: str = "P-2026-001") -> str:
    """Persist one RECEIVED purchase invoice in the bucket and return its id."""
    line = InvoiceLine(
        description="Material oficina",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    invoice = Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": _BUCKET,
            "invoice_number": invoice_number,
            "issued_at": date(2026, 5, 2),
            "counterparty_name": "Proveedor Mixto SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
        },
    )
    InvoiceCatalogueRepository(objects=objects).save(InvoiceCatalogue.from_invoices((invoice,)))
    return invoice.invoice_id


def _seed_parent(
    repository: TransactionCatalogueRepository,
    *,
    amount: Decimal = Decimal("121.00"),
    evidence_id: str | None = None,
) -> str:
    """Persist one ACTIVE parent transaction and return its id."""
    raw = RawTransaction(
        provider_transaction_id="row-split-parent",
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=amount,
        currency="EUR",
        counterparty="Proveedor Mixto SL",
        description="mixed supplier invoice",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=_NOW,
            provider_name="csv",
        ),
        raw_fields={"Concepto": "mixed supplier invoice"},
    )
    fields: dict[str, object] = {
        "raw": raw,
        "direction": TransactionDirection.OUTGOING,
        "source_jurisdiction": "ES",
        "group_label": None,
    }
    if evidence_id is not None:
        fields["purchase_invoice_evidence_id"] = evidence_id
    tx = Transaction.model_validate(fields)
    repository.save(TransactionCatalogue.from_transactions([tx]))
    return tx.transaction_id
