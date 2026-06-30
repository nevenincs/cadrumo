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
    BusinessClassification,
    LLMClassificationResponse,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._evidence import PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceService
from .._llm_classification import _resolve_evidence, suggest_llm_classification

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INVOICE = "Factura Acme SL material de oficina base 100,00 IVA 21,00 total 121,00"
_BUCKET_ID = "32323232-3232-4232-8232-323232323232"


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as p:
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
    payload: dict[str, object] = {
        "raw": raw,
        "direction": TransactionDirection.OUTGOING,
        "source_jurisdiction": "ES",
        "group_label": None,
    }
    if evidence_id is not None:
        payload["purchase_invoice_evidence_id"] = evidence_id
    return Transaction.model_validate(payload)


def _add_evidence(profile: TestRuntimeProfile, tmp_path: Path) -> str:
    svc = PurchaseInvoiceEvidenceService(
        settings=profile.settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
    )
    return svc.add(bucket_id=_BUCKET_ID, source_path=_text_pdf(tmp_path, _INVOICE)).record.evidence_id


def test_no_linked_evidence_returns_none(profile: TestRuntimeProfile) -> None:
    txn = _transaction(evidence_id=None)
    resolved = _resolve_evidence(
        txn,
        bucket_id=_BUCKET_ID,
        settings=profile.settings,
        evidence_acknowledged=True,
    )
    assert resolved is None


def test_consent_off_refuses_text_layer_evidence_read(profile: TestRuntimeProfile, tmp_path: Path) -> None:
    evidence_id = _add_evidence(profile, tmp_path)
    txn = _transaction(evidence_id=evidence_id)
    # A text-layer PDF routes to the cloud subprocess classifier; default posture
    # is cloud upload not permitted -> refuse even when acknowledged.
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _resolve_evidence(txn, bucket_id=_BUCKET_ID, settings=profile.settings, evidence_acknowledged=True)


def test_consented_read_returns_on_host_extracted_text(profile: TestRuntimeProfile, tmp_path: Path) -> None:
    evidence_id = _add_evidence(profile, tmp_path)
    txn = _transaction(evidence_id=evidence_id)
    consenting: Settings = profile.settings.model_copy(update={"aeat_evidence_cloud_upload_permitted": True})

    # Permitted deployment + per-invocation acknowledgement -> on-host text + reference.
    resolved = _resolve_evidence(
        txn,
        bucket_id=_BUCKET_ID,
        settings=consenting,
        evidence_acknowledged=True,
    )
    assert resolved is not None
    assert resolved.text is not None
    assert "Acme SL" in resolved.text
    assert resolved.images == ()
    assert resolved.reference == evidence_id

    # Permitted but not acknowledged this invocation -> refused.
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _resolve_evidence(txn, bucket_id=_BUCKET_ID, settings=consenting, evidence_acknowledged=False)


class _RecordingClassifier:
    """Real ``LLMClassifier`` stand-in for the external provider subprocess.

    Records the ``evidence_text`` it is handed so a test can assert exactly what
    reaches the cloud boundary. The actual provider is an out-of-process CLI that
    cannot run in a unit test; this is the dependency-injection seam the
    production ``classifier=`` parameter already exposes, not a mock of the
    system under test (the evidence-routing logic in ``_llm_classification``).
    """

    def __init__(self) -> None:
        self.seen_evidence_text: str | None = "<<unset>>"

    @property
    def decided_by(self) -> str:
        return "llm:test-provider:test-model"

    def classify(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMClassificationResponse:
        self.seen_evidence_text = evidence_text
        return LLMClassificationResponse(
            classification=BusinessClassification.BUSINESS,
            confidence=Decimal("0.9"),
            reason="recorded classification",
        )


def test_no_evidence_transaction_does_not_trigger_consent_gate_and_uploads_no_evidence(
    profile: TestRuntimeProfile,
) -> None:
    """A no-evidence transaction read with --read-evidence sends nothing sensitive.

    Audit M20: the cloud-upload consent gate governs evidence bytes. When a
    transaction has no linked evidence there is nothing to upload, so the gate
    correctly does not fire even under the default (consent-off, not-acknowledged)
    posture, and the cloud classifier is handed ``evidence_text=None`` -- only the
    transaction row, the documented baseline ``--llm`` input. This locks the
    "no evidence = no upload = no consent needed" invariant.
    """
    txn = _transaction(evidence_id=None)
    repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
    repository.save(TransactionCatalogue.from_transactions((txn,)))

    # Default posture: cloud upload not permitted AND not acknowledged.
    assert profile.settings.aeat_evidence_cloud_upload_permitted is False
    classifier = _RecordingClassifier()

    suggestion = suggest_llm_classification(
        bucket_id=_BUCKET_ID,
        transaction_id=txn.transaction_id,
        provider=None,
        classifier=classifier,
        transaction_repository=repository,
        read_evidence=True,
        evidence_acknowledged=False,
        settings=profile.settings,
    )

    # No refusal raised, and nothing evidence-derived crossed the cloud boundary.
    assert classifier.seen_evidence_text is None
    assert suggestion.evidence_id is None
    assert suggestion.classification is BusinessClassification.BUSINESS
