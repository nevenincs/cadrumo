"""Real-behaviour tests for evidence wiring into the classify path.

Exercises the consent gate plus on-host resolution+extraction end to end: an
invoice is added (bytes stored in the encrypted AttachmentStore), linked to a
transaction, and read into prompt text only when the cloud-upload consent gate is
satisfied. No mocks; real secure storage; nothing written outside it.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest

from ....core.config import Settings
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
)
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._evidence import PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceService
from .._llm_classification import _resolve_evidence_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INVOICE = "Factura Acme SL material de oficina base 100,00 IVA 21,00 total 121,00"


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-001") as p:
        yield p


def _text_pdf(tmp_path: Path, line: str) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    page = canvas.Canvas(buf, pagesize=A4)
    page.drawString(72, 720, line)
    page.save()
    out = tmp_path / "invoice.pdf"
    out.write_bytes(buf.getvalue())
    return out


def _transaction(evidence_id: str | None) -> Transaction:
    raw = RawTransaction(
        transaction_id="row-ev",
        booked_date=date(2025, 3, 1),
        value_date=date(2025, 3, 1),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Acme SL",
        description="office supplies",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="manual",
        ),
        raw_fields={"Concepto": "office supplies"},
    )
    payload: dict[str, object] = {"raw": raw, "direction": TransactionDirection.OUTGOING}
    if evidence_id is not None:
        payload["purchase_invoice_evidence_id"] = evidence_id
    return Transaction.model_validate(payload)


def _add_evidence(profile: TestRuntimeProfile, tmp_path: Path) -> str:
    svc = PurchaseInvoiceEvidenceService(
        settings=profile.settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
    )
    return svc.add(bucket_id="bucket-001", source_path=_text_pdf(tmp_path, _INVOICE)).record.evidence_id


def test_no_linked_evidence_returns_none(profile: TestRuntimeProfile) -> None:
    txn = _transaction(evidence_id=None)
    text, reference = _resolve_evidence_text(
        txn, bucket_id="bucket-001", settings=profile.settings, evidence_acknowledged=True,
    )
    assert text is None
    assert reference is None


def test_consent_off_refuses_evidence_read(profile: TestRuntimeProfile, tmp_path: Path) -> None:
    evidence_id = _add_evidence(profile, tmp_path)
    txn = _transaction(evidence_id=evidence_id)
    # Default posture: cloud upload not permitted -> refuse even when acknowledged.
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _resolve_evidence_text(txn, bucket_id="bucket-001", settings=profile.settings, evidence_acknowledged=True)


def test_consented_read_returns_on_host_extracted_text(profile: TestRuntimeProfile, tmp_path: Path) -> None:
    evidence_id = _add_evidence(profile, tmp_path)
    txn = _transaction(evidence_id=evidence_id)
    consenting: Settings = profile.settings.model_copy(update={"aeat_evidence_cloud_upload_permitted": True})

    # Permitted deployment + per-invocation acknowledgement -> on-host text + reference.
    text, reference = _resolve_evidence_text(
        txn, bucket_id="bucket-001", settings=consenting, evidence_acknowledged=True,
    )
    assert text is not None
    assert "Acme SL" in text
    assert reference == evidence_id

    # Permitted but not acknowledged this invocation -> refused.
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _resolve_evidence_text(txn, bucket_id="bucket-001", settings=consenting, evidence_acknowledged=False)
