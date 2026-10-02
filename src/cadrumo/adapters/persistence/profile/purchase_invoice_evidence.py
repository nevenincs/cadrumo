"""Concrete persistence bindings for the ledger evidence application ports.

Core types:
:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`,
:class:`~cadrumo.core.classification.policies.SensitivityClass`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, ClassVar, override

from ....application.ledger.evidence import PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceDocument
from ....application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from ....application.ledger.evidence_ports import (
    EvidenceAttachmentIngestRequest,
    ProfileBoundEvidenceAttachmentIngestorProtocol,
    RevisionGuardedPurchaseInvoiceEvidenceRepositoryProtocol,
)
from ....application.ledger.preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict
from ....core.classification.policies import SensitivityClass
from ....core.hashing import sha256_hex
from ....core.identity.digest import ContentDigest
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID, SecureObjectWrite
from ....domain.attachments.enums import AttachmentKind, AttachmentSource
from ....domain.attachments.service import (
    AttachmentBytesContent,
    AttachmentFileContent,
    AttachmentIngestionRequest,
    add_attachment,
)
from ..storage.attachment import AttachmentStore
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.errors import SecureObjectRowIdentityError
from ..storage.secure_object_namespaces import LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE

if TYPE_CHECKING:
    from ..storage.sql.secure_objects import SecureObjectRepository


class PurchaseInvoiceEvidenceRepository(SecureBoundRepository[PurchaseInvoiceEvidenceDocument]):
    """Encrypted repository for one bucket's evidence catalogue."""

    namespace: ClassVar[str] = LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE.schema_version
    payload_type = PurchaseInvoiceEvidenceDocument

    @override
    def extract_identifier(self, payload: PurchaseInvoiceEvidenceDocument) -> str:
        return payload.bucket_id

    def load_revisioned(self, bucket_id: str) -> tuple[PurchaseInvoiceEvidenceDocument | None, str]:
        """Load one evidence document with the exact encrypted-row revision observed."""
        record = self.secure_object_repository.load(
            self.namespace,
            bucket_id,
            expected_class=self.sensitivity,
            max_supported_version=self.schema_version,
        )
        if record is None:
            return None, ABSENT_SECURE_OBJECT_REVISION_ID
        envelope = self._validate_envelope(record.payload, subject=f"{self.namespace}/{bucket_id}")
        payload = envelope.payload
        payload_identifier = self.extract_identifier(payload)
        if payload_identifier != bucket_id:
            identity_error = SecureObjectRowIdentityError(
                self.namespace,
                expected_identifier=bucket_id,
                payload_identifier=payload_identifier,
            )
            translated = self._translate_row_identity_error(identity_error)
            if translated is identity_error:
                raise translated
            raise translated from identity_error
        return payload, record.revision_id


class LedgerEvidenceRepositoryAdapter(RevisionGuardedPurchaseInvoiceEvidenceRepositoryProtocol):
    """Translate encrypted evidence documents into application record tuples."""

    def __init__(
        self, *, objects: SecureObjectRepository, mutation_writer: Callable[[Callable[[], None]], None] | None = None
    ) -> None:
        """Bind the encrypted purchase-evidence object repository."""
        self._repository = PurchaseInvoiceEvidenceRepository(objects=objects)
        self._mutation_writer = mutation_writer

    @property
    def secure_object_repository(self) -> SecureObjectRepository:
        """Return the secure-object backend shared with sibling profile repositories."""
        return self._repository.secure_object_repository

    @override
    def load(self, *, bucket_id: str) -> tuple[PurchaseInvoiceEvidence, ...]:
        """Load evidence records for one bucket."""
        document = self._repository.load(bucket_id)
        return () if document is None else tuple(document.records)

    @override
    def load_revisioned(self, *, bucket_id: str) -> tuple[tuple[PurchaseInvoiceEvidence, ...], str]:
        """Load the bucket's evidence rows with their singleton revision."""
        document, revision_id = self._repository.load_revisioned(bucket_id)
        return (() if document is None else tuple(document.records), revision_id)

    @override
    def save(self, *, bucket_id: str, records: Sequence[PurchaseInvoiceEvidence]) -> None:
        """Persist evidence records for one bucket."""
        self._repository.save(
            PurchaseInvoiceEvidenceDocument(bucket_id=bucket_id, records=tuple(records)),
        )

    @override
    def save_if_revision_with_secure_object_writes(
        self,
        *,
        bucket_id: str,
        records: Sequence[PurchaseInvoiceEvidence],
        expected_revision_id: str,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Atomically compare-and-swap the catalogue with sibling secure-object writes."""
        evidence_write = self._repository.to_secure_object_write(
            PurchaseInvoiceEvidenceDocument(bucket_id=bucket_id, records=tuple(records)),
            expected_revision_id=expected_revision_id,
        )

        def write() -> None:
            self._repository.secure_object_repository.apply_batch((evidence_write, *extra_writes))

        if self._mutation_writer is None:
            write()
        else:
            self._mutation_writer(write)


class LedgerEvidenceAttachmentIngestor(ProfileBoundEvidenceAttachmentIngestorProtocol):
    """Translate application ingestion facts into attachment-service inputs."""

    def __init__(self, *, store: AttachmentStore) -> None:
        """Bind the attachment store used for evidence ingestion."""
        self._store = store

    @property
    @override
    def secure_object_repository(self) -> SecureObjectRepository | None:
        """Expose the store's injected backend so workers can verify profile custody."""
        return self._store.objects

    @override
    def ingest(self, request: EvidenceAttachmentIngestRequest) -> ContentDigest:
        """Ingest one evidence file and return its content digest."""
        if request.media_kind == "pdf":
            kind = AttachmentKind.INVOICE_PDF
        elif request.media_kind == "image":
            kind = AttachmentKind.RECEIPT_IMAGE
        else:
            raise ValueError(f"unsupported evidence media kind: {request.media_kind!r}")
        content: AttachmentBytesContent | AttachmentFileContent
        if request.expected_content_digest is None:
            content = AttachmentFileContent(path=request.source_path)
        else:
            data = request.source_path.read_bytes()
            if sha256_hex(data) != request.expected_content_digest:
                raise PurchaseInvoiceEvidenceInputError(
                    translated_message="errors.refused.refused_ledger_evidence_input",
                    precondition_verdict=ledger_no_recovery_verdict(
                        LedgerPreconditionCondition.EVIDENCE_DOCUMENT_BYTES_AVAILABLE,
                        facts={"source_content_matches_planned_digest": False},
                    ),
                )
            content = AttachmentBytesContent(data=data)
        attachment = add_attachment(
            self._store,
            content=content,
            request=AttachmentIngestionRequest(
                kind=kind,
                source=AttachmentSource.LOCAL_FILE,
                source_reference=str(request.source_path),
                mime_type=request.mime_type,
                captured_at=request.captured_at,
                bucket_id=request.bucket_id,
                captured_by=request.actor,
                source_command="aeat app ledger evidence add",
            ),
        )
        return attachment.attachment_id


__all__ = [
    "LedgerEvidenceAttachmentIngestor",
    "LedgerEvidenceRepositoryAdapter",
    "PurchaseInvoiceEvidenceRepository",
]
