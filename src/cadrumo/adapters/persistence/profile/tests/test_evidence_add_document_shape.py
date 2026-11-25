"""Evidence is admitted by what its bytes are: unreadable documents never reach custody.

Every case runs the real evidence service over encrypted secure-object storage
with the production document-shape probe. A refusal must leave no attachment
blob, no manifest, no catalogue row and no bucket event behind.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cadrumo.adapters.inbound.einvoice.shape import probe_document_shape
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.purchase_invoice_evidence import (
    LedgerEvidenceAttachmentIngestor,
    LedgerEvidenceRepositoryAdapter,
)
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger import tests as ledger_application_tests
from cadrumo.application.ledger.evidence import (
    MediaKind,
    admit_evidence_file,
    ingest_evidence_file,
    require_readable_evidence_file,
)
from cadrumo.application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from cadrumo.application.ledger.evidence_ports import LedgerEvidencePorts
from cadrumo.application.ledger.preconditions import LedgerPreconditionCondition
from cadrumo.core.config import Settings
from cadrumo.core.time.clock import now
from cadrumo.domain.attachments.errors import AttachmentNotFoundError
from cadrumo.tests.llm_vision_evidence_support import png_image
from cadrumo.tests.pdf_fixtures import text_pdf_bytes

from .evidence_test_support import (
    BUCKET_ID,
    isolated_settings,
    make_svc,
    pdf_file,
    secure_objects,
)
from .evidence_test_support import runtime_profile as runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "pdf_file", "runtime_profile", "secure_objects"]

_CORPUS = Path(ledger_application_tests.__file__).parent / "_evidence_corpus"


def _event_ids(secure_objects: SecureObjectRepository) -> set[str]:
    return set(BucketEventHistoryRepository(objects=secure_objects).load().events)


def _assert_nothing_was_written(
    secure_objects: SecureObjectRepository, source: Path, *, events_before: set[str]
) -> None:
    """Prove the refused file reached neither custody, the catalogue nor the event history."""
    store = AttachmentStore(objects=secure_objects)
    assert tuple(store.iter_manifests()) == ()
    with pytest.raises(AttachmentNotFoundError):
        store.read_bytes(hashlib.sha256(source.read_bytes()).hexdigest())
    assert LedgerEvidenceRepositoryAdapter(objects=secure_objects).load(bucket_id=BUCKET_ID) == ()
    assert _event_ids(secure_objects) == events_before


def _assert_bytes_refusal(refusal: pytest.ExceptionInfo[PurchaseInvoiceEvidenceInputError]) -> None:
    error = refusal.value
    assert error.translated_message == "errors.refused.refused_ledger_evidence_input"
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == LedgerPreconditionCondition.EVIDENCE_BYTES_READABLE.value
    assert [evidence.values for evidence in verdict.evidence] == [{"document_shape_recognized": False}]


@pytest.mark.parametrize("name", ["adversarial_malformed.pdf", "adversarial_empty.pdf"])
def test_add_refuses_a_pdf_whose_bytes_are_not_a_readable_document(
    isolated_settings: Settings, secure_objects: SecureObjectRepository, tmp_path: Path, name: str
) -> None:
    source = tmp_path / name
    source.write_bytes((_CORPUS / name).read_bytes())
    svc = make_svc(isolated_settings, secure_objects)
    events_before = _event_ids(secure_objects)

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as refusal:
        svc.add(bucket_id=BUCKET_ID, source_path=source)

    _assert_bytes_refusal(refusal)
    _assert_nothing_was_written(secure_objects, source, events_before=events_before)


def test_add_refuses_bytes_whose_extension_names_another_type(
    isolated_settings: Settings, secure_objects: SecureObjectRepository, tmp_path: Path
) -> None:
    """A suffix admits a file; it cannot turn plain text into an image."""
    source = tmp_path / "receipt.png"
    source.write_bytes(b"plain text, not an image")
    svc = make_svc(isolated_settings, secure_objects)
    events_before = _event_ids(secure_objects)

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as refusal:
        svc.add(bucket_id=BUCKET_ID, source_path=source)

    _assert_bytes_refusal(refusal)
    _assert_nothing_was_written(secure_objects, source, events_before=events_before)


def test_a_retry_under_an_idempotency_key_is_refused_each_time_and_writes_nothing(
    isolated_settings: Settings, secure_objects: SecureObjectRepository, tmp_path: Path
) -> None:
    source = tmp_path / "adversarial_malformed.pdf"
    source.write_bytes((_CORPUS / source.name).read_bytes())
    svc = make_svc(isolated_settings, secure_objects)
    events_before = _event_ids(secure_objects)

    for _attempt in range(2):
        with pytest.raises(PurchaseInvoiceEvidenceInputError) as refusal:
            svc.add(bucket_id=BUCKET_ID, source_path=source, idempotency_key="retry-key")
        _assert_bytes_refusal(refusal)
    _assert_nothing_was_written(secure_objects, source, events_before=events_before)


def test_add_stores_a_readable_pdf_and_records_the_digest_of_the_probed_bytes(
    isolated_settings: Settings, secure_objects: SecureObjectRepository, pdf_file: Path
) -> None:
    svc = make_svc(isolated_settings, secure_objects)

    result = svc.add(bucket_id=BUCKET_ID, source_path=pdf_file, supplier="Acme S.L.")

    expected_digest = hashlib.sha256(pdf_file.read_bytes()).hexdigest()
    assert result.record.source_sha256 == expected_digest
    assert result.record.attachment_id == expected_digest
    assert result.record.media_kind is MediaKind.PDF
    assert AttachmentStore(objects=secure_objects).read_bytes(expected_digest) == pdf_file.read_bytes()
    assert len(result.bucket_event_ids) == 1


def test_add_stores_a_readable_image(
    isolated_settings: Settings, secure_objects: SecureObjectRepository, tmp_path: Path
) -> None:
    source = tmp_path / "receipt.png"
    source.write_bytes(png_image())
    svc = make_svc(isolated_settings, secure_objects)

    result = svc.add(bucket_id=BUCKET_ID, source_path=source)

    assert result.record.media_kind is MediaKind.IMAGE
    assert AttachmentStore(objects=secure_objects).read_bytes(result.record.attachment_id) == source.read_bytes()


def test_add_stores_a_readable_structured_document(
    isolated_settings: Settings, secure_objects: SecureObjectRepository, tmp_path: Path
) -> None:
    source = tmp_path / "factura.xml"
    source.write_bytes((_CORPUS / "facturae_32_recargo_invoice.xml").read_bytes())
    svc = make_svc(isolated_settings, secure_objects)

    result = svc.add(bucket_id=BUCKET_ID, source_path=source)

    assert result.record.source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()


def test_add_refuses_a_file_that_differs_from_the_planned_digest_before_custody(
    isolated_settings: Settings, secure_objects: SecureObjectRepository, pdf_file: Path
) -> None:
    svc = make_svc(isolated_settings, secure_objects)
    events_before = _event_ids(secure_objects)
    planned = hashlib.sha256(text_pdf_bytes(("a different document",))).hexdigest()

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as refusal:
        svc.add(bucket_id=BUCKET_ID, source_path=pdf_file, expected_content_digest=planned)

    verdict = refusal.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == LedgerPreconditionCondition.EVIDENCE_DOCUMENT_BYTES_AVAILABLE.value
    _assert_nothing_was_written(secure_objects, pdf_file, events_before=events_before)


def test_custody_only_ingestion_refuses_an_unreadable_file_before_any_write(
    secure_objects: SecureObjectRepository, tmp_path: Path
) -> None:
    """The inventory and invoice-document paths share the refusal, with no catalogue row involved."""
    source = tmp_path / "adversarial_malformed.pdf"
    source.write_bytes((_CORPUS / source.name).read_bytes())
    ports = _ports(secure_objects)
    admitted = admit_evidence_file(source.name, tmp_path)
    events_before = _event_ids(secure_objects)

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as preflight:
        require_readable_evidence_file(ports=ports, admitted=admitted)
    with pytest.raises(PurchaseInvoiceEvidenceInputError) as ingestion:
        ingest_evidence_file(ports=ports, bucket_id=BUCKET_ID, admitted=admitted, now=now(), actor="cli")

    _assert_bytes_refusal(preflight)
    _assert_bytes_refusal(ingestion)
    _assert_nothing_was_written(secure_objects, source, events_before=events_before)


def _ports(secure_objects: SecureObjectRepository) -> LedgerEvidencePorts:
    return LedgerEvidencePorts(
        evidence_repository=LedgerEvidenceRepositoryAdapter(objects=secure_objects),
        attachment_ingestor=LedgerEvidenceAttachmentIngestor(store=AttachmentStore(objects=secure_objects)),
        bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        document_shape_probe=probe_document_shape,
    )
