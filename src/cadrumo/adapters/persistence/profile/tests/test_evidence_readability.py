"""The readability fact on purchase-invoice evidence, over real secure storage.

Evidence add keeps the shape the probe recognised; a record written before the
fact was kept still loads and reads as never checked; the person's check decrypts
the stored bytes once, probes them with the real probe and keeps the finding,
readable or not; and the list serves the kept fact without opening any bytes.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.inbound.einvoice.shape import probe_document_shape
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.purchase_invoice_evidence import (
    LedgerEvidenceAttachmentIngestor,
    LedgerEvidenceRepositoryAdapter,
)
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.evidence import MediaKind, PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceService
from cadrumo.application.ledger.evidence_ports import LedgerEvidencePorts, LedgerEvidenceVerifyPorts
from cadrumo.application.ledger.evidence_read_operation import (
    LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
    LedgerEvidenceListExecutionResult,
    LedgerEvidenceListExecutor,
    LedgerEvidenceListRequest,
    LedgerEvidenceRecordProjection,
)
from cadrumo.application.ledger.evidence_readability import EvidenceUnreadableCause
from cadrumo.application.ledger.evidence_verify_operation import (
    LEDGER_EVIDENCE_VERIFY_NOT_FOUND_REFUSAL_CODE,
    LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
    LedgerEvidenceVerifyChecked,
    LedgerEvidenceVerifyExecutionResult,
    LedgerEvidenceVerifyExecutor,
    LedgerEvidenceVerifyRefusal,
    LedgerEvidenceVerifyRequest,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
from cadrumo.core.document_shape import DocumentShape
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.operations import OperationEffect, profile_operation_subject
from cadrumo.domain.attachments.enums import AttachmentKind, AttachmentSource
from cadrumo.domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.tests.pdf_fixtures import text_pdf_bytes

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "47474747-4747-4747-8747-474747474747"
_PROFILE = UUID(_BUCKET)
_AT = datetime(2026, 3, 2, 9, 30, tzinfo=UTC)
# A PDF header over bytes no reader recognises: the add path refuses these, so
# only a record written before that refusal existed can hold them.
_UNREADABLE = b"%PDF-1.7\nsynthetic bytes that are not a document body"


@pytest.fixture
def objects(tmp_path: Path) -> Generator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path / "profile", bucket_id=_BUCKET) as profile:
        yield profile.repository


def _stored_bytes(objects: SecureObjectRepository, data: bytes) -> str:
    attachment = add_attachment(
        AttachmentStore(objects=objects),
        content=AttachmentBytesContent(data=data),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="synthetic-legacy-evidence",
            mime_type="application/pdf",
            captured_at=_AT,
            bucket_id=_BUCKET,
        ),
    )
    return attachment.attachment_id


def _legacy_record(evidence_id: str, digest: str) -> PurchaseInvoiceEvidence:
    """A record as written before the readability fact was kept: no ``readability`` member."""
    return PurchaseInvoiceEvidence.model_validate(
        {
            "evidence_id": evidence_id,
            "bucket_id": _BUCKET,
            "source_path": "legacy/invoice.pdf",
            "source_sha256": digest,
            "attachment_id": digest,
            "media_kind": MediaKind.PDF,
            "created_at": _AT,
            "updated_at": _AT,
        }
    )


def _evidence_ports(objects: SecureObjectRepository) -> LedgerEvidencePorts:
    """The production evidence adapters, over the isolated profile's own custody."""
    return LedgerEvidencePorts(
        evidence_repository=LedgerEvidenceRepositoryAdapter(objects=objects),
        attachment_ingestor=LedgerEvidenceAttachmentIngestor(store=AttachmentStore(objects=objects)),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        document_shape_probe=probe_document_shape,
    )


def _save_legacy(objects: SecureObjectRepository, *records: PurchaseInvoiceEvidence) -> None:
    LedgerEvidenceRepositoryAdapter(objects=objects).save(bucket_id=_BUCKET, records=records)


def _stored(objects: SecureObjectRepository, evidence_id: str) -> PurchaseInvoiceEvidence:
    rows = LedgerEvidenceRepositoryAdapter(objects=objects).load(bucket_id=_BUCKET)
    return next(row for row in rows if row.evidence_id == evidence_id)


class _Recorder:
    """The operation host's executor surface, recording effects and keeping each operand."""

    def __init__(self, definition_id: str) -> None:
        self.effects: list[OperationEffect] = []
        self.operands: list[BaseModel] = []
        self._definition_id = definition_id

    def context(self) -> OperationExecutorContext:
        recorder = self

        class Cancellation:
            @asynccontextmanager
            async def irreversible_section(self):
                yield

        class Events:
            async def phase(self, phase: str) -> None:
                assert phase == recorder._definition_id

            async def effect(self, effect: OperationEffect) -> None:
                recorder.effects.append(effect)

        class Operands:
            async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
                assert written_at.tzinfo is not None
                recorder.operands.append(operand)
                return "d" * 64

        return cast(
            OperationExecutorContext,
            SimpleNamespace(
                identity=SimpleNamespace(
                    definition_id=self._definition_id, subject_ref=profile_operation_subject(_BUCKET)
                ),
                cancellation=Cancellation(),
                events=Events(),
                operands=Operands(),
            ),
        )


async def _verify(
    objects: SecureObjectRepository, evidence_id: str
) -> tuple[str | OperationRefusalEvidence, _Recorder]:
    recorder = _Recorder(LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID)
    request = OperationRequest[LedgerEvidenceVerifyRequest](
        definition_id=LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(_BUCKET),
        payload=LedgerEvidenceVerifyRequest(profile_id=_PROFILE, evidence_id=evidence_id),
    )

    def verify_ports(*, bucket_id: str) -> LedgerEvidenceVerifyPorts:
        assert bucket_id == _BUCKET
        return LedgerEvidenceVerifyPorts(
            evidence=_evidence_ports(objects), attachment_store=AttachmentStore(objects=objects)
        )

    outcome = await LedgerEvidenceVerifyExecutor(verify_ports).execute(request, recorder.context())
    return outcome, recorder


def _checked(recorder: _Recorder) -> LedgerEvidenceVerifyChecked:
    (operand,) = recorder.operands
    assert isinstance(operand, LedgerEvidenceVerifyExecutionResult)
    assert isinstance(operand.result.outcome, LedgerEvidenceVerifyChecked)
    return operand.result.outcome


def test_add_keeps_the_shape_the_probe_recognised(objects: SecureObjectRepository, tmp_path: Path) -> None:
    source = tmp_path / "invoice.pdf"
    source.write_bytes(text_pdf_bytes(("Factura SINT-1", "Base 100,00")))

    added = PurchaseInvoiceEvidenceService(ports=_evidence_ports(objects)).add(bucket_id=_BUCKET, source_path=source)

    stored = _stored(objects, added.record.evidence_id)
    assert stored.readability is not None
    assert stored.readability.state == "readable"
    assert stored.readability.document_shape is DocumentShape.PDF_TEXT_LAYER
    assert stored.readability.checked_sha256 == stored.attachment_id
    projection = LedgerEvidenceRecordProjection.from_record(stored)
    assert (projection.readability, projection.document_shape) == ("readable", DocumentShape.PDF_TEXT_LAYER)


def test_a_record_written_before_the_fact_loads_and_reads_as_never_checked(objects: SecureObjectRepository) -> None:
    digest = _stored_bytes(objects, text_pdf_bytes(("Factura SINT-2",)))
    _save_legacy(objects, _legacy_record("0123456789abcdef", digest))

    stored = _stored(objects, "0123456789abcdef")

    assert stored.readability is None
    projection = LedgerEvidenceRecordProjection.from_record(stored)
    assert projection.readability == "unchecked"
    assert projection.document_shape is None
    assert projection.unreadable_cause is None
    assert projection.readability_checked_at is None


@pytest.mark.asyncio
async def test_check_keeps_readable_with_its_shape_and_journals_it(objects: SecureObjectRepository) -> None:
    digest = _stored_bytes(objects, text_pdf_bytes(("Factura SINT-3",)))
    _save_legacy(objects, _legacy_record("1111111111111111", digest))

    outcome, recorder = await _verify(objects, "1111111111111111")

    assert outcome == "d" * 64
    assert recorder.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    checked = _checked(recorder)
    assert (checked.record.readability, checked.record.document_shape) == ("readable", DocumentShape.PDF_TEXT_LAYER)
    stored = _stored(objects, "1111111111111111")
    assert stored.readability is not None
    assert stored.readability.state == "readable"
    assert stored.readability.document_shape is DocumentShape.PDF_TEXT_LAYER
    (event_id,) = checked.bucket_event_ids
    event = BucketEventHistoryRepository(objects=objects).load().events[event_id]
    assert event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED
    assert event.object_id == "1111111111111111"
    assert event.payload["mutation_kind"] == "readability_checked"
    assert event.payload["readability"] == "readable"


@pytest.mark.asyncio
async def test_check_keeps_unrecognised_bytes_as_unreadable_not_as_an_error(objects: SecureObjectRepository) -> None:
    digest = _stored_bytes(objects, _UNREADABLE)
    _save_legacy(objects, _legacy_record("2222222222222222", digest))

    outcome, recorder = await _verify(objects, "2222222222222222")

    assert outcome == "d" * 64
    assert recorder.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    checked = _checked(recorder)
    assert checked.record.readability == "unreadable"
    assert checked.record.unreadable_cause is EvidenceUnreadableCause.BYTES_UNRECOGNIZED
    assert checked.record.document_shape is None
    stored = _stored(objects, "2222222222222222")
    assert stored.readability is not None
    assert stored.readability.unreadable_cause is EvidenceUnreadableCause.BYTES_UNRECOGNIZED
    assert EvidenceUnreadableCause.BYTES_UNRECOGNIZED.value == "ledger.evidence.bytes_readable"


@pytest.mark.asyncio
async def test_check_keeps_bytes_custody_does_not_hold_as_unavailable(objects: SecureObjectRepository) -> None:
    absent = sha256_hex(b"synthetic bytes never stored")
    _save_legacy(objects, _legacy_record("3333333333333333", absent))

    _outcome, recorder = await _verify(objects, "3333333333333333")

    checked = _checked(recorder)
    assert checked.record.readability == "unreadable"
    assert checked.record.unreadable_cause is EvidenceUnreadableCause.BYTES_UNAVAILABLE


@pytest.mark.asyncio
async def test_check_of_an_unknown_record_is_a_typed_refusal_that_writes_nothing(
    objects: SecureObjectRepository,
) -> None:
    digest = _stored_bytes(objects, text_pdf_bytes(("Factura SINT-4",)))
    _save_legacy(objects, _legacy_record("4444444444444444", digest))
    before = LedgerEvidenceRepositoryAdapter(objects=objects).load_revisioned(bucket_id=_BUCKET)

    outcome, recorder = await _verify(objects, "ffffffffffffffff")

    assert isinstance(outcome, OperationRefusalEvidence)
    assert outcome.refusal_code == LEDGER_EVIDENCE_VERIFY_NOT_FOUND_REFUSAL_CODE
    assert recorder.effects == [OperationEffect.NONE]
    (operand,) = recorder.operands
    assert isinstance(operand, LedgerEvidenceVerifyExecutionResult)
    assert isinstance(operand.result.outcome, LedgerEvidenceVerifyRefusal)
    assert LedgerEvidenceRepositoryAdapter(objects=objects).load_revisioned(bucket_id=_BUCKET) == before


@pytest.mark.asyncio
async def test_list_serves_the_kept_fact_without_opening_any_bytes(objects: SecureObjectRepository) -> None:
    readable = _stored_bytes(objects, text_pdf_bytes(("Factura SINT-5",)))
    _save_legacy(objects, _legacy_record("5555555555555555", readable), _legacy_record("6666666666666666", readable))
    await _verify(objects, "5555555555555555")

    def refusing_probe(data: bytes) -> DocumentShape:
        raise AssertionError("the list must not probe evidence bytes")

    def list_ports(*, bucket_id: str) -> LedgerEvidencePorts:
        # The list's capability bundle holds no byte reader at all; the probe
        # is the one door to the bytes' content, and it refuses here.
        assert bucket_id == _BUCKET
        real = _evidence_ports(objects)
        return LedgerEvidencePorts(
            evidence_repository=real.evidence_repository,
            attachment_ingestor=real.attachment_ingestor,
            bucket_event_repository=real.bucket_event_repository,
            document_shape_probe=refusing_probe,
        )

    recorder = _Recorder(LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID)
    await LedgerEvidenceListExecutor(list_ports).execute(
        OperationRequest[LedgerEvidenceListRequest](
            definition_id=LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(_BUCKET),
            payload=LedgerEvidenceListRequest(profile_id=_PROFILE),
        ),
        recorder.context(),
    )

    (operand,) = recorder.operands
    assert isinstance(operand, LedgerEvidenceListExecutionResult)
    by_id = {row.evidence_id: row for row in operand.result.rows}
    assert by_id["5555555555555555"].readability == "readable"
    assert by_id["5555555555555555"].document_shape is DocumentShape.PDF_TEXT_LAYER
    assert by_id["6666666666666666"].readability == "unchecked"
