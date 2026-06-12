"""Purchase invoice evidence records and the CRUD application service.

``aeat app ledger evidence {add|remove|update|view|list}`` operate over a
:class:`PurchaseInvoiceEvidence` pydantic record. Audit events are emitted
to a :class:`BucketEventHistoryRepository` on every mutating verb.

File-type scope is restricted to PDF and image inputs. Plaintext, email
body, and Drive-URL evidence sources are out of scope. ``add`` refuses
non-PDF/non-image source paths with a typed
:class:`PurchaseInvoiceEvidenceInputError`.

Persistence is bucket-scoped encrypted secure-object storage. At ``add``
time the source file's bytes are copied into the encrypted
:class:`AttachmentStore` (active bucket) and the resulting content-addressed
``attachment_id`` is recorded on the evidence record; the bytes thereafter
live only in secure storage. ``source_path`` is retained as a provenance
breadcrumb and is never read for bytes
(``sensitive-financial-data-secure-storage-only``).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import override

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ...adapters.persistence.storage import LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...adapters.persistence.storage.envelope import SecureBoundRepository
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...core.config import Settings
from ...core.errors import AeatError
from ...core.external_constants import PDF_EXTENSION, PDF_MIME_TYPE
from ...core.identity import BucketId
from ...core.time import now as _utc_now
from ...domain.attachments import Attachment, AttachmentKind, AttachmentSource
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol

_PDF_EXTENSIONS = frozenset({PDF_EXTENSION})
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic", ".heif"})

# Concrete MIME types by source extension. The on-host vision reader needs a
# concrete MIME (image/png vs image/jpeg), which `MediaKind` alone cannot supply.
_SUFFIX_MIME = {
    PDF_EXTENSION: PDF_MIME_TYPE,
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}

_DEFERRED_ADR_REF = "evidence-source-expansion (deferred; only PDF and image inputs are accepted)"


def _attachment_kind_for(media_kind: MediaKind) -> AttachmentKind:
    """Map a purchase-invoice ``MediaKind`` to the attachment manifest kind."""
    return AttachmentKind.INVOICE_PDF if media_kind is MediaKind.PDF else AttachmentKind.RECEIPT_IMAGE


class MediaKind(StrEnum):
    """Canonical media-kind values for purchase invoice evidence."""

    PDF = "pdf"
    IMAGE = "image"


class PurchaseInvoiceEvidenceInputError(AeatError):
    """Raised when a CLI-supplied evidence input violates the typed contract."""


class PurchaseInvoiceEvidenceNotFoundError(AeatError):
    """Raised when a CLI lookup targets a missing evidence record."""


class PurchaseInvoiceEvidence(BaseModel):
    """One persisted purchase invoice evidence record."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=64)
    bucket_id: BucketId
    source_path: str = Field(min_length=1)
    source_sha256: str = Field(min_length=64, max_length=64)
    # In-store byte home: the bytes live encrypted in the AttachmentStore under this
    # content-addressed id. `source_path` is a provenance breadcrumb only and is never
    # read for bytes (sensitive-financial-data-secure-storage-only).
    attachment_id: str | None = Field(default=None, min_length=64, max_length=64)
    media_kind: MediaKind
    supplier: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    notes: str = ""
    created_at: datetime
    updated_at: datetime

    @field_serializer("taxable_base", "iva_rate", "iva_amount", when_used="json")
    def _serialize_decimal(self, value: Decimal | None) -> str | None:
        return None if value is None else str(value)


class PurchaseInvoiceEvidenceDocument(BaseModel):
    """Encrypted bucket-local purchase invoice evidence catalogue."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bucket_id: BucketId
    records: tuple[PurchaseInvoiceEvidence, ...] = ()


class PurchaseInvoiceEvidencePatch(BaseModel):
    """Mutable subset of ``PurchaseInvoiceEvidence`` fields accepted by ``update``.

    Only the fields listed here may be changed after an evidence record is
    created. ``evidence_id``, ``bucket_id``, ``source_path``,
    ``source_sha256``, ``media_kind``, and the timestamp fields are immutable.
    A ``None`` value for any optional field means "leave unchanged"; the
    service ignores ``None`` entries when applying the patch.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    supplier: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    notes: str | None = None


def _resolve_media_kind(source_path: Path) -> MediaKind:
    suffix = source_path.suffix.lower()
    if suffix in _PDF_EXTENSIONS:
        return MediaKind.PDF
    if suffix in _IMAGE_EXTENSIONS:
        return MediaKind.IMAGE
    raise PurchaseInvoiceEvidenceInputError(
        f"source path {source_path!s} has unsupported extension {suffix!r}; "
        f"only PDF and image inputs are accepted. See {_DEFERRED_ADR_REF}.",
        suggestion="aeat app ledger evidence list",
    )


class PurchaseInvoiceEvidenceResult(BaseModel):
    """Return record from a mutating evidence verb — record plus emitted event id."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    record: PurchaseInvoiceEvidence
    bucket_event_ids: tuple[str, ...] = ()


class PurchaseInvoiceEvidenceRepository(SecureBoundRepository[PurchaseInvoiceEvidenceDocument]):
    """Encrypted repository for one bucket's purchase invoice evidence records."""

    namespace = LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE.namespace
    sensitivity = LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE.sensitivity
    schema_version = LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE.schema_version
    payload_type = PurchaseInvoiceEvidenceDocument

    @override
    def extract_identifier(self, payload: PurchaseInvoiceEvidenceDocument) -> str:
        return payload.bucket_id


def _repository(settings: Settings, bucket_id: str) -> PurchaseInvoiceEvidenceRepository:
    return PurchaseInvoiceEvidenceRepository(objects=secure_object_repository_for_bucket(bucket_id, settings))


def _load(settings: Settings, bucket_id: str) -> list[PurchaseInvoiceEvidence]:
    document = _repository(settings, bucket_id).load(bucket_id)
    return list(document.records) if document is not None else []


def _save(settings: Settings, bucket_id: str, records: list[PurchaseInvoiceEvidence]) -> None:
    _repository(settings, bucket_id).save(
        PurchaseInvoiceEvidenceDocument(bucket_id=bucket_id, records=tuple(records)),
    )


_EVIDENCE_EVENT_PAYLOAD_VERSION = 1


def _build_evidence_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    evidence_id: str,
    actor: str,
    occurred_at: datetime,
    payload: dict[str, str],
) -> BucketEvent:
    return BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=actor,
            object_type=BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
            object_id=evidence_id,
            payload=payload,
        ),
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
        object_id=evidence_id,
        payload_version=_EVIDENCE_EVENT_PAYLOAD_VERSION,
        payload=payload,
    )


def _emit_evidence_event(
    *,
    event_repository: BucketEventHistoryRepositoryProtocol,
    bucket_id: str,
    event_type: BucketEventType,
    evidence_id: str,
    actor: str,
    occurred_at: datetime,
    payload: dict[str, str],
) -> str:
    event = _build_evidence_event(
        bucket_id=bucket_id,
        event_type=event_type,
        evidence_id=evidence_id,
        actor=actor,
        occurred_at=occurred_at,
        payload=payload,
    )
    event_repository.save(append_bucket_event(event_repository.load(), event))
    return event.event_id


class PurchaseInvoiceEvidenceService:
    """Application service for the ``aeat app ledger evidence`` verb group."""

    def __init__(
        self,
        settings: Settings | None = None,
        bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    ) -> None:
        """Initialise the service with optional dependency injection.

        Args:
            settings: Resolved ``Settings`` object. When ``None``,
                ``load_settings()`` is called so that test overrides via
                ``override_settings()`` are honoured.
            bucket_event_repository: Audit-event sink. Defaults to
                ``BucketEventHistoryRepository`` backed by the requested
                operation bucket.
        """
        # `load_settings()` honours `override_settings`; bare `Settings()`
        # bypasses the context-var and lands writes in the project default.
        from ...core.config import load_settings as _load_settings

        self._settings = settings or _load_settings()
        self._event_repository = bucket_event_repository

    def add(
        self,
        *,
        bucket_id: str,
        source_path: Path,
        supplier: str | None = None,
        invoice_number: str | None = None,
        invoice_date: str | None = None,
        taxable_base: Decimal | None = None,
        iva_rate: Decimal | None = None,
        iva_amount: Decimal | None = None,
        notes: str = "",
        actor: str = "cli",
    ) -> PurchaseInvoiceEvidenceResult:
        """Attach a new purchase invoice evidence file to a bucket (ledger).

        Resolves ``source_path`` to an absolute path, verifies the file
        exists, infers the ``MediaKind`` from the extension, copies the file's
        bytes into the encrypted :class:`AttachmentStore` (active bucket) and
        records the resulting content-addressed ``attachment_id`` on the record
        (the bytes thereafter live only in secure storage; ``source_path`` is a
        provenance breadcrumb), creates a ``PurchaseInvoiceEvidence`` record,
        appends it to the in-memory catalogue, persists the encrypted bucket-local catalogue
        in secure-object storage, and emits a
        ``PURCHASE_INVOICE_EVIDENCE_ATTACHED`` audit event.

        Args:
            bucket_id: Ledger bucket the evidence belongs to.
            source_path: Local path to a PDF or image file.
            supplier: Optional vendor name extracted from the invoice.
            invoice_number: Optional invoice identifier from the document.
            invoice_date: Optional issue date string (free-form; typically
                ``YYYY-MM-DD``).
            taxable_base: Optional net taxable amount (``~decimal.Decimal``).
            iva_rate: Optional IVA percentage as a ``~decimal.Decimal``.
            iva_amount: Optional IVA amount as a ``~decimal.Decimal``.
            notes: Operator free-text annotation.
            actor: Identifier stamped on the audit event (defaults to
                ``"cli"``).

        Returns:
            :class:`PurchaseInvoiceEvidenceResult`: Carrying the new record and the
            emitted audit event id.

        Raises:
            ``PurchaseInvoiceEvidenceInputError``: if ``source_path`` is not a
                readable file or has an unsupported extension.
        """
        resolved = Path(source_path).expanduser().resolve()
        if not resolved.is_file():
            raise PurchaseInvoiceEvidenceInputError(
                f"source path {source_path!s} does not resolve to a readable file (resolved to {resolved!s})",
                context={"source_path": str(source_path), "resolved_path": str(resolved)},
                suggestion=(
                    "check the --file path: confirm the file exists, the path is spelled correctly, "
                    "and the file is readable, then re-run `aeat app ledger evidence add`"
                ),
            )
        media_kind = _resolve_media_kind(resolved)
        now = _utc_now()
        # Store the bytes in the encrypted AttachmentStore (active bucket) so they live
        # in secure storage; `source_path` is never the byte source thereafter
        # (sensitive-financial-data-secure-storage-only).
        store = AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, self._settings))
        digest, bytes_size = store.put_file(resolved)
        store.write_manifest(
            Attachment(
                attachment_id=digest,
                kind=_attachment_kind_for(media_kind),
                source=AttachmentSource.LOCAL_FILE,
                source_reference=str(resolved),
                sha256=digest,
                mime_type=_SUFFIX_MIME[resolved.suffix.lower()],
                bytes_size=bytes_size,
                captured_at=now,
                bucket_id=bucket_id,
                captured_by=actor,
                source_command="aeat app ledger evidence add",
            ),
        )
        record = PurchaseInvoiceEvidence(
            evidence_id=uuid.uuid4().hex[:16],
            bucket_id=bucket_id,
            source_path=str(resolved),
            source_sha256=digest,
            attachment_id=digest,
            media_kind=media_kind,
            supplier=supplier,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            taxable_base=taxable_base,
            iva_rate=iva_rate,
            iva_amount=iva_amount,
            notes=notes,
            created_at=now,
            updated_at=now,
        )
        records = _load(self._settings, bucket_id)
        records.append(record)
        _save(self._settings, bucket_id, records)
        event_id = _emit_evidence_event(
            event_repository=self._event_repository_for_bucket(bucket_id),
            bucket_id=bucket_id,
            event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
            evidence_id=record.evidence_id,
            actor=actor,
            occurred_at=now,
            payload={"media_kind": record.media_kind, "source_path": record.source_path},
        )
        return PurchaseInvoiceEvidenceResult(record=record, bucket_event_ids=(event_id,))

    def view(self, *, bucket_id: str, evidence_id: str) -> PurchaseInvoiceEvidence:
        """Return the single evidence record identified by ``evidence_id``.

        Args:
            bucket_id: Ledger bucket to search.
            evidence_id: Unique evidence id assigned at ``add`` time.

        Returns:
            :class:`PurchaseInvoiceEvidence`: The matching record.

        Raises:
            ``PurchaseInvoiceEvidenceNotFoundError``: if no record with that id
                exists in the bucket.
        """
        for record in _load(self._settings, bucket_id):
            if record.evidence_id == evidence_id:
                return record
        raise PurchaseInvoiceEvidenceNotFoundError(
            f"no purchase invoice evidence record with id {evidence_id!r} in bucket {bucket_id!r}",
            suggestion="aeat app ledger evidence list",
        )

    def list_all(self, *, bucket_id: str) -> tuple[PurchaseInvoiceEvidence, ...]:
        """Return all evidence records for a bucket in append order.

        Args:
            bucket_id: Ledger bucket to read.

        Returns:
            tuple[:class:`PurchaseInvoiceEvidence`, ...]: Oldest first.
            Returns an empty tuple if the bucket has no evidence file yet.
        """
        return tuple(_load(self._settings, bucket_id))

    def update(
        self,
        *,
        bucket_id: str,
        evidence_id: str,
        patch: PurchaseInvoiceEvidencePatch,
        actor: str = "cli",
    ) -> PurchaseInvoiceEvidenceResult:
        """Apply a partial update to an existing evidence record.

        Loads the bucket's record list, finds the record matching
        ``evidence_id``, merges non-``None`` fields from ``patch``, stamps
        ``updated_at``, writes the updated list back, and emits a
        ``PURCHASE_INVOICE_EVIDENCE_REPLACED`` audit event.

        Args:
            bucket_id: Ledger bucket containing the record.
            evidence_id: Id of the record to update.
            patch: ``PurchaseInvoiceEvidencePatch`` carrying the fields to
                change. Fields set to ``None`` are left unchanged.
            actor: Identifier stamped on the audit event.

        Returns:
            :class:`PurchaseInvoiceEvidenceResult`: With the updated record and audit
            event id.

        Raises:
            ``PurchaseInvoiceEvidenceNotFoundError``: if no matching record
                exists.
        """
        records = _load(self._settings, bucket_id)
        for index, record in enumerate(records):
            if record.evidence_id != evidence_id:
                continue
            data = record.model_dump()
            for key, value in patch.model_dump(exclude_unset=True).items():
                if value is not None:
                    data[key] = value
            now = _utc_now()
            data["updated_at"] = now
            updated = PurchaseInvoiceEvidence.model_validate(data)
            records[index] = updated
            _save(self._settings, bucket_id, records)
            event_id = _emit_evidence_event(
                event_repository=self._event_repository_for_bucket(bucket_id),
                bucket_id=bucket_id,
                event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED,
                evidence_id=evidence_id,
                actor=actor,
                occurred_at=now,
                payload={"media_kind": updated.media_kind},
            )
            return PurchaseInvoiceEvidenceResult(record=updated, bucket_event_ids=(event_id,))
        raise PurchaseInvoiceEvidenceNotFoundError(
            f"no purchase invoice evidence record with id {evidence_id!r} in bucket {bucket_id!r}",
            suggestion="aeat app ledger evidence list",
        )

    def remove(
        self,
        *,
        bucket_id: str,
        evidence_id: str,
        actor: str = "cli",
    ) -> PurchaseInvoiceEvidenceResult:
        """Remove an evidence record from a bucket.

        Loads the bucket catalogue, finds the record, removes it from the
        in-memory list, persists the updated encrypted bucket-local catalogue
        in secure-object storage, and emits a
        ``PURCHASE_INVOICE_EVIDENCE_DETACHED`` audit event.

        Args:
            bucket_id: Ledger bucket containing the record.
            evidence_id: Id of the record to remove.
            actor: Identifier stamped on the audit event.

        Returns:
            :class:`PurchaseInvoiceEvidenceResult`: Carrying the removed record and
            the audit event id.

        Raises:
            ``PurchaseInvoiceEvidenceNotFoundError``: if no matching record
                exists.
        """
        records = _load(self._settings, bucket_id)
        for index, record in enumerate(records):
            if record.evidence_id == evidence_id:
                removed = records.pop(index)
                _save(self._settings, bucket_id, records)
                now = _utc_now()
                event_id = _emit_evidence_event(
                    event_repository=self._event_repository_for_bucket(bucket_id),
                    bucket_id=bucket_id,
                    event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
                    evidence_id=evidence_id,
                    actor=actor,
                    occurred_at=now,
                    payload={"media_kind": removed.media_kind},
                )
                return PurchaseInvoiceEvidenceResult(record=removed, bucket_event_ids=(event_id,))
        raise PurchaseInvoiceEvidenceNotFoundError(
            f"no purchase invoice evidence record with id {evidence_id!r} in bucket {bucket_id!r}",
            suggestion="aeat app ledger evidence list",
        )

    def _event_repository_for_bucket(self, bucket_id: str) -> BucketEventHistoryRepositoryProtocol:
        if self._event_repository is not None:
            return self._event_repository
        return BucketEventHistoryRepository(
            objects=secure_object_repository_for_bucket(bucket_id, self._settings),
        )


__all__ = [
    "PurchaseInvoiceEvidence",
    "PurchaseInvoiceEvidenceDocument",
    "PurchaseInvoiceEvidenceInputError",
    "PurchaseInvoiceEvidenceNotFoundError",
    "PurchaseInvoiceEvidencePatch",
    "PurchaseInvoiceEvidenceRepository",
    "PurchaseInvoiceEvidenceResult",
    "PurchaseInvoiceEvidenceService",
]
