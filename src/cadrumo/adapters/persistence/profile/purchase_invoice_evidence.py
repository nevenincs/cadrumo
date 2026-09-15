"""Concrete persistence bindings for the ledger evidence application ports."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, override

from ....application.ledger.evidence import PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceDocument
from ....application.ledger.evidence_ports import EvidenceAttachmentIngestRequest
from ....core.classification.policies import SensitivityClass
from ....core.identity.digest import ContentDigest
from ....domain.attachments.enums import AttachmentKind, AttachmentSource
from ....domain.attachments.service import AttachmentFileContent, AttachmentIngestionRequest, add_attachment
from ..storage.attachment import AttachmentStore
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
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


class LedgerEvidenceRepositoryAdapter:
    """Translate encrypted evidence documents into application record tuples."""

    def __init__(self, *, objects: SecureObjectRepository) -> None:
        """Bind the encrypted purchase-evidence object repository."""
        self._repository = PurchaseInvoiceEvidenceRepository(objects=objects)

    def load(self, *, bucket_id: str) -> tuple[PurchaseInvoiceEvidence, ...]:
        """Load evidence records for one bucket."""
        document = self._repository.load(bucket_id)
        return () if document is None else tuple(document.records)

    def save(self, *, bucket_id: str, records: Sequence[PurchaseInvoiceEvidence]) -> None:
        """Persist evidence records for one bucket."""
        self._repository.save(
            PurchaseInvoiceEvidenceDocument(bucket_id=bucket_id, records=tuple(records)),
        )


class LedgerEvidenceAttachmentIngestor:
    """Translate application ingestion facts into attachment-service inputs."""

    def __init__(self, *, store: AttachmentStore) -> None:
        """Bind the attachment store used for evidence ingestion."""
        self._store = store

    def ingest(self, request: EvidenceAttachmentIngestRequest) -> ContentDigest:
        """Ingest one evidence file and return its content digest."""
        if request.media_kind == "pdf":
            kind = AttachmentKind.INVOICE_PDF
        elif request.media_kind == "image":
            kind = AttachmentKind.RECEIPT_IMAGE
        else:
            raise ValueError(f"unsupported evidence media kind: {request.media_kind!r}")
        attachment = add_attachment(
            self._store,
            content=AttachmentFileContent(path=request.source_path),
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
