"""Synthetic inward custody capabilities exercising canonical ingestion services."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Never
from uuid import UUID

from ....core.config import Settings, load_settings
from ....core.document_shape import DocumentShape
from ....core.hashing import sha256_hex
from ....core.secure_object_write import SecureObjectWrite
from ....domain.attachments.enums import AttachmentKind, AttachmentSource
from ....domain.attachments.models import Attachment
from ....domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..evidence import PurchaseInvoiceEvidence
from ..evidence_errors import PurchaseInvoiceEvidenceInputError
from ..evidence_ingestion_operation_ports import LedgerEvidenceIngestionPorts
from ..evidence_input import EvidenceInput, resolve_purchase_invoice_evidence_input
from ..evidence_input_ports import EvidenceInputPorts
from ..evidence_ports import EvidenceAttachmentIngestRequest, LedgerEvidencePorts
from ..evidence_textlayer_ports import EvidenceTextLayerPorts
from ..extraction_draft_store import ExtractionDraftDocument, ExtractionDraftRepositoryProtocol
from ..invoice_draft_extraction_ports import InvoiceDraftExtractionPorts, StructuredInvoiceReadError
from ..structured_invoice_ports import StructuredInvoiceRecord
from .bulk_classify_operation_support import PROFILE_ID
from .export_link_operation_support import Events
from .export_link_operation_support import Subject as ActionSubject


def unused(*args: object, **kwargs: object) -> Never:
    """Detect any unexpected inference or reader route."""
    raise AssertionError("this structured synthetic fixture must not dispatch inference")


class Store:
    """Keep synthetic document bytes in memory and expose actual writer entry."""

    def __init__(self, subject: Subject) -> None:
        self.subject = subject
        self.blobs: dict[str, bytes] = {}
        self.manifests: dict[str, Attachment] = {}
        self.fail_manifest_preparation = False
        self.fail_after_blob_write = False

    def put_bytes(self, data: bytes) -> str:
        digest = sha256_hex(data)
        if digest in self.blobs:
            return digest

        def write() -> None:
            assert self.subject.fence.active
            self.blobs[digest] = data
            if self.fail_after_blob_write:
                raise OSError("synthetic committed blob acknowledgement lost")

        self.subject.write(write)
        return digest

    def put_file(self, source: Path) -> tuple[str, int]:
        data = source.read_bytes()
        return self.put_bytes(data), len(data)

    def read_bytes(self, sha256: str) -> bytes:
        assert not self.subject.fence.active
        return self.blobs[sha256]

    def write_manifest(self, attachment: Attachment) -> None:
        assert not self.subject.fence.active
        if self.fail_manifest_preparation:
            raise ValueError("synthetic known preparation failure")

        def write() -> None:
            assert self.subject.fence.active
            self.manifests[attachment.attachment_id] = attachment

        self.subject.write(write)

    def load_manifest(self, attachment_id: str) -> Attachment:
        assert not self.subject.fence.active
        return self.manifests[attachment_id]

    def iter_manifests(self) -> Iterator[Attachment]:
        return iter(self.manifests.values())

    def verify_blob(self, attachment_id: str) -> None:
        assert sha256_hex(self.read_bytes(attachment_id)) == attachment_id


class Evidence:
    """Revisioned synthetic evidence/event co-commit, with shared custody identity."""

    def __init__(self, subject: Subject) -> None:
        self.subject = subject
        self.secure_object_repository = subject.backend
        self.rows: tuple[PurchaseInvoiceEvidence, ...] = ()
        self.revision = "a" * 64

    def load(self, *, bucket_id: str) -> tuple[PurchaseInvoiceEvidence, ...]:
        assert bucket_id == str(PROFILE_ID) and not self.subject.fence.active
        return self.rows

    def load_revisioned(self, *, bucket_id: str) -> tuple[tuple[PurchaseInvoiceEvidence, ...], str]:
        return self.load(bucket_id=bucket_id), self.revision

    def save(self, *, bucket_id: str, records: Sequence[PurchaseInvoiceEvidence]) -> None:
        raise AssertionError("evidence mutation must use its event CAS")

    def save_if_revision_with_secure_object_writes(
        self,
        *,
        bucket_id: str,
        records: Sequence[PurchaseInvoiceEvidence],
        expected_revision_id: str,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        assert bucket_id == str(PROFILE_ID) and expected_revision_id == self.revision and len(extra_writes) == 1

        def write() -> None:
            assert self.subject.fence.active
            self.rows = tuple(records)
            self.subject.shared_events._catalogue = BucketEventHistoryCatalogue.model_validate_json(
                extra_writes[0].payload
            )
            self.revision = "b" * 64

        self.subject.write(write)


class Ingestor:
    """Canonical attachment service over the synthetic inward store."""

    def __init__(self, subject: Subject) -> None:
        self.subject = subject
        self.secure_object_repository = subject.backend

    def ingest(self, request: EvidenceAttachmentIngestRequest) -> str:
        data = request.source_path.read_bytes()
        if request.expected_content_digest is not None and sha256_hex(data) != request.expected_content_digest:
            raise PurchaseInvoiceEvidenceInputError()
        return add_attachment(
            self.subject.store,
            content=AttachmentBytesContent(data=data),
            request=AttachmentIngestionRequest(
                kind=AttachmentKind.INVOICE_PDF,
                source=AttachmentSource.LOCAL_FILE,
                source_reference=str(request.source_path),
                mime_type=request.mime_type,
                captured_at=request.captured_at,
                bucket_id=request.bucket_id,
                captured_by=request.actor,
                source_command="aeat app ledger evidence add",
            ),
        ).attachment_id


class Drafts:
    """Exact draft factory detects every actual draft save."""

    def __init__(self, subject: Subject) -> None:
        self.subject = subject
        self.document: ExtractionDraftDocument | None = None

    def load(self, identifier: str) -> ExtractionDraftDocument | None:
        assert identifier == str(PROFILE_ID) and not self.subject.fence.active
        return self.document

    def save(self, payload: ExtractionDraftDocument) -> None:
        def write() -> None:
            assert self.subject.fence.active and payload.bucket_id == str(PROFILE_ID)
            self.document = payload

        self.subject.write(write)

    def factory(self, *, bucket_id: str, settings: Settings) -> ExtractionDraftRepositoryProtocol:
        assert bucket_id == str(PROFILE_ID)
        return self


class SharedEvents(Events):
    """Synthetic event port exposes the same concrete custody identity."""

    def __init__(self, backend: object) -> None:
        super().__init__()
        self.secure_object_repository = backend


class Subject(ActionSubject):
    """One real authority pin with controlled source/custody capabilities."""

    def __init__(self, operation: PinnedAuthorityOperation) -> None:
        super().__init__(operation)
        self.backend = object()
        self.write: Callable[[Callable[[], None]], None] = unused
        self.before_read: Callable[[], None] = unused
        self.store = Store(self)
        self.evidence = Evidence(self)
        self.shared_events = SharedEvents(self.backend)
        self.drafts = Drafts(self)
        self.revoke_reader = False
        self.structured_refuses = True
        self.change_source: Path | None = None

    def compose(
        self,
        *,
        profile_id: UUID,
        operation: PinnedAuthorityOperation,
        mutation_writer: Callable[[Callable[[], None]], None],
        before_read: Callable[[], None],
    ) -> LedgerEvidenceIngestionPorts:
        assert profile_id == PROFILE_ID and operation is self.operation and not self.fence.active
        self.write, self.before_read = mutation_writer, before_read
        if self.change_source is not None:
            # The shape probe changes this only after planning hashes its bytes.
            source = self.change_source

            def probe(data: bytes) -> DocumentShape:
                source.write_bytes(b"changed after planning")
                return DocumentShape.XML_CII
        else:

            def probe(data: bytes) -> DocumentShape:
                return DocumentShape.XML_CII

        input_ports = EvidenceInputPorts(document_shape_probe=probe)

        def resolve(
            bucket_id: str, evidence_id: str | None, attachment_id: str | None, settings: Settings
        ) -> EvidenceInput:
            row = next(row for row in self.evidence.rows if row.evidence_id == evidence_id)
            return resolve_purchase_invoice_evidence_input(row, store=self.store, ports=input_ports)

        def structured(data: bytes) -> StructuredInvoiceRecord:
            if self.revoke_reader:
                self.fence.deny = True
                before_read()
            if self.structured_refuses:
                raise StructuredInvoiceReadError()
            return StructuredInvoiceRecord(
                shape=DocumentShape.XML_CII,
                supplier_tax_id="B12345674",
                customer_tax_id="X1234567L",
                supplier_name="Synthetic supplier",
                customer_name="Synthetic customer",
                supplier_postal_code="28013",
                customer_postal_code="28014",
                supplier_country_code="ES",
                customer_country_code="ES",
                invoice_number="synthetic-001",
                invoice_series=None,
                invoice_classification=None,
                rectifies_invoice_number=None,
                invoice_date="2026-01-01",
                currency="EUR",
                taxable_base=Decimal("100"),
                iva_amount=Decimal("21"),
                grand_total=Decimal("121"),
                recargo_amount=None,
                retencion_amount=None,
                suplidos_amount=None,
                iva_category="S",
                regime_legend=None,
                record_text="Synthetic structured invoice",
                lines=(),
                iva_breakdown=((Decimal("21"), Decimal("100"), Decimal("21")),),
            )

        extraction = InvoiceDraftExtractionPorts(
            resolve_evidence_input=resolve,
            evidence_input_ports=input_ports,
            text_layer_ports=EvidenceTextLayerPorts(extract_pages_text=unused),
            parse_structured_invoice=structured,
            read_text=unused,
            propose_supply_nature=unused,
            rasterise_pdf=unused,
            transcribe_vision=unused,
            consent_binding_error=unused,
        )
        return LedgerEvidenceIngestionPorts(
            profile_id=profile_id,
            operation=operation,
            settings=load_settings(),
            evidence=LedgerEvidencePorts(self.evidence, Ingestor(self), self.shared_events),
            extraction=extraction,
            draft_factory=self.drafts.factory,
        )
