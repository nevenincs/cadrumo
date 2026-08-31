"""Real-behaviour tests for evidence resolution into in-memory EvidenceInput.

Exercises the secure-storage byte path end to end with real adapters: the
purchase-invoice ``add`` verb stores bytes in the encrypted ``AttachmentStore``,
and the resolver reads them back into an in-memory :class:`EvidenceInput`. No
mocks, no temp files, no bytes written outside secure storage.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....core.document_shape import PDF_CONTAINER_SHAPES, DocumentShape
from ....domain.attachments.enums import AttachmentKind, AttachmentSource
from ....domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from ..evidence import MediaKind, PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceDocument
from ..evidence_errors import PurchaseInvoiceEvidenceInputError
from ..evidence_input import (
    EvidenceInput,
    resolve_attachment_evidence_input,
    resolve_purchase_invoice_evidence_input,
)
from ..preconditions import LedgerPreconditionCondition
from ._evidence_input_test_support import _BUCKET_ID, _PDF_BYTES, _added_record, _make_svc, pdf_file
from ._evidence_input_test_support import runtime_profile as runtime_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "pdf_file", "runtime_profile", "secure_objects"]


def test_add_stores_bytes_in_secure_storage_under_attachment_id(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    pdf_file: Path,
) -> None:
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    # The bytes now live in the encrypted attachment store, content-addressed.
    assert record.attachment_id == hashlib.sha256(_PDF_BYTES).hexdigest()
    assert record.source_sha256 == record.attachment_id
    assert record.attachment_id is not None
    store = AttachmentStore(objects=secure_objects)
    assert store.read_bytes(record.attachment_id) == _PDF_BYTES


def test_add_with_nonexistent_path_refuses_with_path_oriented_guidance(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """A typo'd / missing --file path must surface a PATH problem, not a
    'evidence list' suggestion irrelevant to the file the operator named.

    The refusal names the offending path in its context and tells the operator
    to fix the path, then re-run ``evidence add`` — never to list existing
    records, which does not address a wrong path at all.
    """
    svc = _make_svc(isolated_settings, secure_objects)
    bogus = tmp_path / "does-not-exist.pdf"

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as exc_info:
        svc.add(bucket_id=_BUCKET_ID, source_path=bogus)

    error = exc_info.value
    assert error.terminal_precondition_verdict is not None
    assert error.terminal_precondition_verdict.failed_condition_id == (
        LedgerPreconditionCondition.EVIDENCE_FILE_READABLE.value
    )
    assert error.terminal_precondition_verdict.evidence[0].values == {"source_file_readable": False}
    # The offending path is named in structured context for the operator.
    assert error.context is not None
    assert str(bogus) == error.context["source_path"]
    assert "resolved_path" in error.context


def test_resolve_purchase_invoice_evidence_reads_secure_storage_into_memory(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    pdf_file: Path,
) -> None:
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    store = AttachmentStore(objects=secure_objects)

    resolved = resolve_purchase_invoice_evidence_input(record, store=store)

    assert isinstance(resolved, EvidenceInput)
    assert resolved.data == _PDF_BYTES
    assert resolved.content_sha256 == hashlib.sha256(_PDF_BYTES).hexdigest()
    assert resolved.document_shape in PDF_CONTAINER_SHAPES
    assert resolved.mime_type == "application/pdf"
    assert resolved.evidence_id == record.evidence_id
    assert resolved.attachment_id == record.attachment_id


def test_resolve_attachment_evidence_input_round_trips_bytes(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    pdf_file: Path,
) -> None:
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    assert record.attachment_id is not None
    store = AttachmentStore(objects=secure_objects)

    resolved = resolve_attachment_evidence_input(record.attachment_id, store=store)

    assert resolved.data == _PDF_BYTES
    assert resolved.attachment_id == record.attachment_id


def _stored_attachment_id(
    secure_objects: SecureObjectRepository,
    *,
    data: bytes,
    mime_type: str,
    kind: AttachmentKind = AttachmentKind.INVOICE_PDF,
) -> str:
    """Store real bytes under a caller-chosen declared MIME type, and return the id."""
    attachment = add_attachment(
        AttachmentStore(objects=secure_objects),
        content=AttachmentBytesContent(data=data),
        request=AttachmentIngestionRequest(
            kind=kind,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="operator-evidence",
            mime_type=mime_type,
            captured_at=datetime(2026, 8, 1, tzinfo=UTC),
            bucket_id=_BUCKET_ID,
        ),
    )
    return attachment.attachment_id


@pytest.mark.parametrize(
    ("mime_type", "kind"),
    (
        ("Application/PDF; charset=binary", AttachmentKind.INVOICE_PDF),
        ("IMAGE/PNG; profile=receipt", AttachmentKind.RECEIPT_IMAGE),
    ),
)
def test_resolution_reads_the_bytes_while_the_declared_media_type_is_preserved_verbatim(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    mime_type: str,
    kind: AttachmentKind,
) -> None:
    """The stored label decides nothing; the bytes decide, and the label survives intact.

    Both parametrizations carry the SAME PDF bytes. The second announces them as
    ``IMAGE/PNG``, a label that disagrees with its own payload -- the only case
    where the two mechanisms can give different answers, and therefore the only
    case worth parametrizing. The retired derivation read the label and called
    those bytes an image; the probe opens them and answers PDF for both.

    ``mime_type`` is still carried through unnormalised, because it is
    provenance: what the producer declared, preserved exactly, casing and
    parameters included.
    """
    attachment_id = _stored_attachment_id(secure_objects, data=_PDF_BYTES, mime_type=mime_type, kind=kind)

    resolved = resolve_attachment_evidence_input(attachment_id, store=AttachmentStore(objects=secure_objects))

    assert resolved.document_shape in PDF_CONTAINER_SHAPES
    assert resolved.mime_type == mime_type


def test_a_readable_document_is_admitted_even_when_its_declared_type_is_opaque(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
) -> None:
    """A truthful document must not be refused for wearing an unhelpful label.

    The retired derivation refused anything whose MIME type was not PDF, XML or
    ``image/*``, so a genuine invoice PDF stored as ``application/octet-stream``
    -- the type a producer supplies when it simply does not know -- was rejected
    at the read boundary while its bytes were perfectly readable. Admission is
    now decided by the probe, so the opaque label costs nothing.

    This assertion reds against the retired derivation, which is the point: it
    is one of the two directions in which label and bytes disagree.
    """
    attachment_id = _stored_attachment_id(
        secure_objects,
        data=_PDF_BYTES,
        mime_type="application/octet-stream",
    )

    resolved = resolve_attachment_evidence_input(attachment_id, store=AttachmentStore(objects=secure_objects))

    assert resolved.document_shape in PDF_CONTAINER_SHAPES
    assert resolved.mime_type == "application/octet-stream"


def test_unreadable_bytes_are_refused_however_respectable_the_declared_type(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
) -> None:
    """The other direction: a trustworthy-looking label over bytes nothing can read.

    These bytes match no recognised shape, yet they are announced as
    ``application/pdf``. The retired derivation asked only the label, admitted
    them, and left the failure to surface further down the read path. The probe
    answers :attr:`DocumentShape.UNKNOWN`, which is never guessed into a
    neighbouring shape, so the refusal happens at the boundary and names what is
    actually wrong.
    """
    junk = b"\x00\x01\x02 not a document in any recognised shape"
    attachment_id = _stored_attachment_id(secure_objects, data=junk, mime_type="application/pdf")
    store = AttachmentStore(objects=secure_objects)

    assert DocumentShape.UNKNOWN not in PDF_CONTAINER_SHAPES, "the control below would be vacuous"

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as excinfo:
        resolve_attachment_evidence_input(attachment_id, store=store)

    assert "no readable document shape" in str(excinfo.value)


def test_record_without_in_store_attachment_is_unconstructable() -> None:
    """A record whose bytes are not in secure storage must not exist at all.

    ``attachment_id`` is required, so the byte-less shape is refused at model
    validation rather than at read time: there is no record a reader could be
    tempted to satisfy from the cleartext ``source_path``
    (sensitive-financial-data-secure-storage-only). The read path therefore
    carries no byte-custody guard, because it cannot be reached.
    """
    with pytest.raises(ValidationError) as excinfo:
        PurchaseInvoiceEvidence(  # type: ignore[call-arg]  # ty: ignore[missing-argument]  # reason: omitting attachment_id is the refusal under test
            evidence_id="ev-orphan",
            bucket_id=_BUCKET_ID,
            source_path="/some/cleartext/path.pdf",
            source_sha256=hashlib.sha256(_PDF_BYTES).hexdigest(),
            media_kind=MediaKind.PDF,
            created_at=datetime(2026, 6, 10, tzinfo=UTC),
            updated_at=datetime(2026, 6, 10, tzinfo=UTC),
        )

    assert "attachment_id" in str(excinfo.value)


def test_persisted_record_stripped_of_its_attachment_is_refused_on_load(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    pdf_file: Path,
) -> None:
    """Anti-tautology proof: delete the field from a real stored payload and reload.

    Stores a genuine record through the real encrypted repository, drops
    ``attachment_id`` from the persisted payload, and asserts the strict model
    refuses it. If this ever passes with the field absent, the required-field
    contract is not actually enforced at the persistence boundary.
    """
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    stripped = record.model_dump()
    del stripped["attachment_id"]

    with pytest.raises(ValidationError):
        PurchaseInvoiceEvidence.model_validate(stripped)

    document = PurchaseInvoiceEvidenceDocument(bucket_id=_BUCKET_ID, records=(record,))
    payload = document.model_dump()
    del payload["records"][0]["attachment_id"]
    with pytest.raises(ValidationError):
        PurchaseInvoiceEvidenceDocument.model_validate(payload)
