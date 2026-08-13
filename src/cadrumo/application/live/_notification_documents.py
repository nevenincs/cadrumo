"""Encrypted custody for the documents AEAT serves behind a notificación.

One capture, three writes, in this order: the PDF bytes go into the encrypted
content-addressed :class:`adapters.persistence.storage.AttachmentStore`, the
sanción reading is derived from those bytes in memory, and a
:class:`NotificationDocumentRecord` binding the certificado to the resulting
``attachment_id`` is persisted as its own encrypted secure-object row.

**The bytes never touch the filesystem.** They arrive from the sede adapter in
memory, are handed straight to the attachment store's encrypted blob namespace,
and are dropped. There is no temp file, no scratch directory, no plaintext
cache, no on-disk extraction step, and nothing sensitive reaches a log line —
only the certificado id, the digest and the byte count, which say nothing about
what the document contains. There is also **no browser-opening path** here and
none is to be added: displaying an AEAT notification is the taxpayer's own act,
not this application's.

The legal guard governs this whole module by construction rather than by
convention. Fetching runs through
:func:`~adapters.outbound.aeat.sede.fetch_notification_document`, which calls
:func:`~adapters.outbound.aeat.sede.assert_notification_content_readable`
before anything crosses the wire, so a notification AEAT has not recorded as
read produces no AEAT contact, no bytes, no attachment and no record. This
module re-asserts the same guard before it does any work of its own — not
because the adapter's check is doubted, but because a future caller reaching
this service by another route must meet the guard too, and a guard that sits
only at the bottom of a call chain protects only the callers that go through
the bottom.

See Also:
    :mod:`adapters.inbound.notificacion`
        Deterministic reader for the fetched document's text layer.
    :mod:`domain.attachments`
        The byte-custody tier this service writes through; it records what the
        bytes are, never a fiscal figure about them.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from ...adapters.inbound.notificacion import (
    NotificacionParseError,
    SancionLiquidacion,
    SancionParseError,
    parse_sancion_document,
)
from ...adapters.inbound.pdf import extract_pages_text_from_bytes
from ...adapters.outbound.aeat.sede import (
    NotificationDocument,
    RemoteNotification,
    assert_notification_content_readable,
    fetch_notification_document,
)
from ...adapters.persistence.profile.snapshots import SecureSnapshotRepository
from ...adapters.persistence.storage import (
    LIVE_NOTIFICATION_DOCUMENT_NAMESPACE,
    resolve_attachment_store,
    secure_object_repository_for_bucket,
)
from ...core import STRICT_FROZEN_CONFIG
from ...core.config import Settings, load_settings
from ...core.identity import AeatCertificadoId, BucketId
from ...core.logging import get_logger
from ...core.time import now
from ...domain.attachments import (
    AttachmentBytesContent,
    AttachmentIngestionRequest,
    AttachmentKind,
    AttachmentSource,
    AttachmentStoreProtocol,
    add_attachment,
)
from ._errors import (
    LiveApplicationInputError,
    LiveReadPrecondition,
    live_read_no_recovery_verdict,
)
from ._snapshot_base import SnapshotNotFoundError

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.auth import AeatSession

log = get_logger(__name__)

_PDF_MIME_TYPE = "application/pdf"
_SOURCE_COMMAND = "app.live.notifications.document.pull"


class NotificationDocumentNotFoundError(SnapshotNotFoundError):
    """Raised when no stored document record matches the requested certificado."""


class NotificationDocumentRecord(BaseModel):
    """The custody record binding one notification to its stored document bytes.

    This record is a POINTER plus provenance, never the bytes: the bytes live
    in the encrypted attachment store under :attr:`attachment_id`, which is
    their own SHA-256. Holding the digest in both places is deliberate — the
    record can be verified against custody without decrypting anything.

    Attributes:
        certificado_id: The notification the document was served under. Also
            the record's storage key, so re-pulling the same notification
            rewrites one row rather than accumulating duplicates.
        bucket_id: The profile bucket that owns both this record and the bytes.
        attachment_id: The stored bytes' content address in the encrypted
            attachment store.
        document_sha256: Digest of the fetched PDF, equal to
            :attr:`attachment_id` by construction and carried explicitly so a
            reader never has to know that.
        byte_size: Size of the fetched PDF.
        source_url: The AEAT detail endpoint the document was served from.
        fetched_at: When the fetch completed.
        sancion: The deterministic reading of the document when it is a sanción
            or liquidación act that parsed completely. ``None`` when the
            document is another kind, or when the reader REFUSED — a refusal is
            recorded as an absent reading, never as a zeroed one, and the bytes
            are kept either way so an operator can read them themselves.
        parse_refusal: Why the reading is absent, when it is. Carried so the
            refusal survives in the record instead of being lost to a log line.
        mode: Structural read-only marker.
    """

    model_config = STRICT_FROZEN_CONFIG

    certificado_id: AeatCertificadoId
    bucket_id: BucketId
    attachment_id: str = Field(min_length=64, max_length=64)
    document_sha256: str = Field(min_length=64, max_length=64)
    byte_size: int = Field(ge=1)
    source_url: str = Field(min_length=1)
    fetched_at: datetime
    sancion: SancionLiquidacion | None = None
    parse_refusal: str | None = Field(default=None, min_length=1, max_length=512)
    mode: Literal["read"] = "read"

    @property
    def snapshot_id(self) -> str:
        """Return the record's storage address, which IS its certificado.

        The secure-object repository addresses every payload by a
        ``snapshot_id``; here that address is the certificado itself, so one
        notification owns exactly one row and a re-pull rewrites it rather than
        accumulating near-duplicates of the same served document.
        """
        return str(self.certificado_id)


def notification_document_object_key(bucket_id: str, certificado_id: str) -> str:
    """Build the secure-object key for one bucket's notification-document record."""
    trimmed_bucket = bucket_id.strip()
    trimmed_certificado = certificado_id.strip()
    if not trimmed_bucket:
        raise LiveApplicationInputError(
            translated_message="application.live.notifications.errors.bucket_id_blank",
        )
    if not trimmed_certificado:
        raise LiveApplicationInputError(
            translated_message="application.live.notifications.errors.certificado_id_blank",
        )
    return f"notification-document:{trimmed_bucket}:{trimmed_certificado}"


def _document_repository(
    settings: Settings,
    bucket_id: str,
) -> SecureSnapshotRepository[NotificationDocumentRecord]:
    """Bind the encrypted secure-object repository for one bucket's document records."""
    return SecureSnapshotRepository(
        bucket_id=bucket_id,
        payload_model=NotificationDocumentRecord,
        namespace_definition=LIVE_NOTIFICATION_DOCUMENT_NAMESPACE,
        object_key=notification_document_object_key,
        not_found_factory=lambda certificado_id: NotificationDocumentNotFoundError(
            translated_message="application.live.notifications.errors.document_not_found",
            context={"certificado_id": certificado_id},
        ),
        ambiguous_prefix_factory=lambda certificado_id, full_ids: NotificationDocumentNotFoundError(
            translated_message="application.live.notifications.errors.document_prefix_ambiguous",
            context={"certificado_id": certificado_id, "match_count": len(full_ids)},
        ),
        domain_label="notification-document",
        input_error_cls=LiveApplicationInputError,
        objects=secure_object_repository_for_bucket(bucket_id, settings),
    )


class NotificationDocumentService:
    """Bucket-scoped custody and read surface over fetched notification documents.

    The service is structurally read-only towards AEAT: it fetches and stores,
    and there is no verb here that acknowledges, submits, signs or otherwise
    changes anything on AEAT's side.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        attachment_store: AttachmentStoreProtocol | None = None,
    ) -> None:
        """Bind the service to a settings object and an optional injected store.

        Args:
            settings: Deployment settings; loaded when omitted.
            attachment_store: Byte-custody port. Resolved to the concrete
                encrypted :class:`adapters.persistence.storage.AttachmentStore`
                when omitted, so production has exactly one construction site.
        """
        self._settings = settings or load_settings()
        self._attachment_store = attachment_store

    def persist_document(
        self,
        *,
        bucket_id: str,
        row: RemoteNotification,
        document: NotificationDocument,
    ) -> NotificationDocumentRecord:
        """Take custody of already-fetched document bytes and record the binding.

        Split from :meth:`pull_document` so the custody boundary is exercisable
        without a browser: everything below the wire — encryption, the
        content-addressed write, the reading, the record — runs here.

        Args:
            bucket_id: The profile bucket taking custody.
            row: The notification the document belongs to. Re-checked against
                the legal guard before anything is written.
            document: The fetched bytes, held in memory.

        Returns:
            The persisted :class:`NotificationDocumentRecord`.

        Raises:
            SedeNavigationError: When ``row`` is not a notification AEAT has
                already recorded as read.
            LiveApplicationInputError: When the document does not belong to the
                supplied row.
        """
        assert_notification_content_readable(row)
        if str(document.certificado_id) != str(row.certificado_id):
            raise LiveApplicationInputError(
                translated_message="application.live.notifications.errors.document_row_mismatch",
                context={
                    "row_certificado_id": str(row.certificado_id),
                    "document_certificado_id": str(document.certificado_id),
                },
                precondition_verdict=live_read_no_recovery_verdict(
                    LiveReadPrecondition.NOTIFICATION_DOCUMENT_MATCHES_ROW,
                    facts={
                        "row_certificado_id": str(row.certificado_id),
                        "document_certificado_id": str(document.certificado_id),
                        "matches_row": False,
                    },
                ),
            )

        attachment = add_attachment(
            resolve_attachment_store(self._attachment_store),
            content=AttachmentBytesContent(data=document.pdf_bytes),
            request=AttachmentIngestionRequest(
                kind=AttachmentKind.AEAT_NOTIFICATION_PDF,
                source=AttachmentSource.URL,
                source_reference=str(document.source_url),
                mime_type=_PDF_MIME_TYPE,
                captured_at=now(),
                bucket_id=bucket_id,
                source_command=_SOURCE_COMMAND,
                metadata={
                    "certificado_id": str(row.certificado_id),
                    "tipo": row.tipo,
                    "fecha_emision": row.fecha_emision.isoformat(),
                },
            ),
        )

        sancion, refusal = self._read_document(document)
        record = NotificationDocumentRecord(
            certificado_id=row.certificado_id,
            bucket_id=bucket_id,
            attachment_id=attachment.attachment_id,
            document_sha256=document.pdf_sha256,
            byte_size=len(document.pdf_bytes),
            source_url=str(document.source_url),
            fetched_at=now(),
            sancion=sancion,
            parse_refusal=refusal,
        )
        _document_repository(self._settings, bucket_id).save(record)
        log.info(
            "notification document stored: certificado=%s bytes=%d parsed=%s",
            row.certificado_id,
            len(document.pdf_bytes),
            sancion is not None,
        )
        return record

    async def pull_document(
        self,
        *,
        bucket_id: str,
        session: AeatSession,
        row: RemoteNotification,
    ) -> NotificationDocumentRecord:
        """Fetch one already-read notification's document and take custody of it.

        The guard runs twice on this path — here, and again inside
        :func:`~adapters.outbound.aeat.sede.fetch_notification_document` before
        any request is issued. The first check is what guarantees a refused row
        produces no AEAT contact at all rather than a request that is discarded
        afterwards.

        Args:
            bucket_id: The profile bucket taking custody.
            session: An authenticated AEAT session.
            row: The notification to fetch. Must be one AEAT already records as
                read.

        Returns:
            The persisted :class:`NotificationDocumentRecord`.

        Raises:
            SedeNavigationError: When ``row`` is anything other than already
                read, or when the AEAT landing is off-policy.
        """
        assert_notification_content_readable(row)
        document = await fetch_notification_document(session, row, settings=self._settings)
        return self.persist_document(bucket_id=bucket_id, row=row, document=document)

    def show(self, *, bucket_id: str, certificado_id: str) -> NotificationDocumentRecord:
        """Return the stored record for one certificado, or raise if none is stored."""
        return _document_repository(self._settings, bucket_id).load(certificado_id)

    def list_documents(self, *, bucket_id: str) -> tuple[NotificationDocumentRecord, ...]:
        """Return every stored document record for the bucket, newest fetch first."""
        records = _document_repository(self._settings, bucket_id).list_snapshots()
        return tuple(sorted(records, key=lambda record: record.fetched_at, reverse=True))

    def _read_document(self, document: NotificationDocument) -> tuple[SancionLiquidacion | None, str | None]:
        """Read the document's text layer, returning either a record or a refusal.

        A refusal is NOT an error at this boundary. The bytes are already in
        custody and are the authoritative artefact; the structured reading is a
        convenience over them. So a document the reader will not vouch for
        yields ``(None, reason)`` — the operator keeps the document and is told
        plainly that no figures were extracted, which is a far better outcome
        than a partially-read record that looks authoritative.

        The extraction is in-memory: the bytes are never written to a path for
        a parser to open.
        """
        try:
            pages = extract_pages_text_from_bytes(
                document.pdf_bytes,
                error_class=NotificacionParseError,
                pdf_label="an AEAT notification document",
                source_label="the fetched notification PDF",
            )
        except NotificacionParseError as exc:
            # A scan-only or XFA document has no text layer to read. The bytes
            # are already in custody and remain the artefact; only the
            # convenience reading is unavailable.
            log.info("notification document has no readable text layer: certificado=%s", document.certificado_id)
            return None, f"{type(exc).__name__}: {exc}"[:512]

        text = "\n".join(pages)
        try:
            return (
                parse_sancion_document(
                    text,
                    certificado_id=str(document.certificado_id),
                    document_sha256=document.pdf_sha256,
                ),
                None,
            )
        except SancionParseError as exc:
            log.info(
                "notification document not read as a sanción: certificado=%s reason=%s",
                document.certificado_id,
                type(exc).__name__,
            )
            return None, f"{type(exc).__name__}: {exc}"[:512]


__all__ = [
    "NotificationDocumentNotFoundError",
    "NotificationDocumentRecord",
    "NotificationDocumentService",
    "notification_document_object_key",
]
