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

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Final, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from ...core.config import Settings
from ...core.hex import Hex64Str
from ...core.identity import AeatCertificadoId, BucketId, ContentDigest
from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import now
from ...domain.attachments.enums import AttachmentKind, AttachmentSource
from ...domain.attachments.protocols import AttachmentStoreProtocol
from ...domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from ...domain.notifications.sancion import SancionLiquidacion
from .errors import (
    LiveApplicationInputError,
    LiveReadPrecondition,
    live_read_no_recovery_verdict,
)
from .notification_ports import (
    NotificationContentGuard,
    NotificationDocumentFetcher,
    NotificationDocumentProtocol,
    NotificationDocumentReaderProtocol,
    NotificationRowProtocol,
)
from .snapshot_base import SnapshotNotFoundError, SnapshotRepository

log = get_logger(__name__)

_PDF_MIME_TYPE = "application/pdf"
_SOURCE_COMMAND = "app.live.notifications.document.pull"

#: Persisted fields the CALLER supplies on every store. These are the match: a
#: re-store of a certificado already in custody must agree with the stored row
#: on every one of them, and a divergence refuses rather than overwrites. The
#: silent-drop failure this guards is subtler than the obvious one — a re-store
#: carrying a NEW value that the no-op discards looks successful and loses data.
_CALLER_SUPPLIED_FIELDS: Final[frozenset[str]] = frozenset(
    {"certificado_id", "bucket_id", "document_sha256", "byte_size", "source_url"},
)

#: Persisted fields derived deterministically from the document BYTES. Equal
#: bytes imply equal values, and ``document_sha256`` — which IS the bytes'
#: identity — is compared above, so these are covered transitively. Re-deriving
#: them to compare would re-run the very reading the no-op exists to skip.
_BYTE_DERIVED_FIELDS: Final[frozenset[str]] = frozenset({"attachment_id", "sancion", "parse_refusal"})

#: Persisted fields deliberately OUTSIDE the match. ``fetched_at`` is a
#: last-seen body field, never identity: folding the clock in would make every
#: retry diverge from itself. ``mode`` is a single-value structural marker.
_NON_IDENTITY_FIELDS: Final[frozenset[str]] = frozenset({"fetched_at", "mode"})


NotificationParseRefusal = Annotated[str, StringConstraints(min_length=1, max_length=512)]
"""Why a sede notification document could not be parsed."""


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
            the record's storage key, so one notification owns exactly one row
            and a retried pull neither duplicates it nor rewrites it.
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
        parse_refusal: Why the reading is absent, required exactly when it is.
            Carried so the refusal survives in the record instead of being lost
            to a log line.
        mode: Structural read-only marker.
    """

    model_config = STRICT_FROZEN_CONFIG

    certificado_id: AeatCertificadoId
    bucket_id: BucketId
    attachment_id: Hex64Str
    document_sha256: ContentDigest
    byte_size: int = Field(ge=1)
    source_url: str = Field(min_length=1)
    fetched_at: datetime
    sancion: SancionLiquidacion | None = None
    parse_refusal: NotificationParseRefusal | None = None
    mode: Literal["read"] = "read"

    @model_validator(mode="after")
    def _a_reading_is_present_or_refused_never_both_nor_neither(self) -> NotificationDocumentRecord:
        """Refuse a custody record that does not say what became of the reading.

        The two fields are one answer expressed in two slots, so exactly one of
        them is populated on every record. Neither populated is the dangerous
        state: it reads as "the document held no figures" when the truth is
        that nobody looked, and an operator who trusts it stops reading a
        served act that may carry an amount. Both populated is the incoherent
        one — a reading the reader simultaneously refused to vouch for.

        Enforced here rather than at the surfaces that project the record,
        because this is a statement about the custody data itself and holds for
        every reader port, every stored row and every reload of one.
        """
        if self.sancion is not None and self.parse_refusal is not None:
            raise ValueError(
                "a notification document carries a sancion reading or the reason there is none, "
                "and this record carries both a reading and a refusal",
            )
        if self.sancion is None and self.parse_refusal is None:
            raise ValueError(
                "a notification document carries a sancion reading or the reason there is none, "
                "and this record carries neither a reading nor a refusal",
            )
        return self

    @property
    def snapshot_id(self) -> str:
        """Return the record's storage address, which IS its certificado.

        The secure-object repository addresses every payload by a
        ``snapshot_id``; here that address is the certificado itself, so one
        notification owns exactly one row rather than accumulating
        near-duplicates of the same served document.
        """
        return str(self.certificado_id)


class NotificationDocumentCustody(BaseModel):
    """One custody attempt's outcome: the record, and whether it was already held.

    The record alone cannot answer whether the attempt stored anything. A retry
    against a certificado already in custody returns the row that was there
    before, byte-identical to a first store's return, so a caller holding only
    the record has no way to tell an ingest from a no-op — and the CLI contract
    requires a guarded no-op to say so, both in its result shape and on the
    notices channel.

    Carrying the answer on the return value rather than re-deriving it at the
    caller is what keeps ONE authority for the decision: the service compares
    the caller-supplied fields and decides, and every surface reads that
    decision instead of asking custody a second question of its own.

    Attributes:
        record: The persisted record — the row already in custody when this
            attempt was a no-op, the newly written one otherwise.
        already_in_custody: Whether the attempt stored nothing because the
            certificado was already held with agreeing content.
    """

    model_config = STRICT_FROZEN_CONFIG

    record: NotificationDocumentRecord
    already_in_custody: bool


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


def _record_in_custody(
    repository: SnapshotRepository[NotificationDocumentRecord],
    certificado_id: str,
) -> NotificationDocumentRecord | None:
    """Return the record already in custody for ``certificado_id``, or ``None``.

    ``load`` addresses the row by its exact key rather than by prefix, so a miss
    here means nothing is stored under this certificado — never that several
    rows were ambiguous.
    """
    try:
        return repository.load(certificado_id)
    except NotificationDocumentNotFoundError:
        return None


def _diverging_persisted_fields(
    existing: NotificationDocumentRecord,
    *,
    bucket_id: str,
    row: NotificationRowProtocol,
    document: NotificationDocumentProtocol,
) -> tuple[str, ...]:
    """Return every caller-supplied field on which a re-store disagrees with custody.

    The incoming mapping is keyed off :data:`_CALLER_SUPPLIED_FIELDS` rather
    than iterated from itself, so adding a field to the match set without
    supplying its incoming value raises here instead of narrowing the match
    silently.
    """
    incoming: dict[str, object] = {
        "certificado_id": str(row.certificado_id),
        "bucket_id": str(bucket_id),
        "document_sha256": document.pdf_sha256,
        "byte_size": len(document.pdf_bytes),
        "source_url": str(document.source_url),
    }
    diverging: list[str] = []
    for name in sorted(_CALLER_SUPPLIED_FIELDS):
        stored = getattr(existing, name)
        candidate = incoming[name]
        if isinstance(candidate, str):
            stored = str(stored)
        if stored != candidate:
            diverging.append(name)
    return tuple(diverging)


class NotificationDocumentService:
    """Bucket-scoped custody and read surface over fetched notification documents.

    The service is structurally read-only towards AEAT: it fetches and stores,
    and there is no verb here that acknowledges, submits, signs or otherwise
    changes anything on AEAT's side.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        attachment_store: AttachmentStoreProtocol,
        repository_factory: Callable[[str], SnapshotRepository[NotificationDocumentRecord]],
        content_guard: NotificationContentGuard,
        document_fetcher: NotificationDocumentFetcher,
        document_reader: NotificationDocumentReaderProtocol,
    ) -> None:
        """Bind the service to its application ports and concrete deployment settings.

        Args:
            settings: Deployment settings supplied by the composition root.
            attachment_store: Encrypted byte-custody port.
            repository_factory: Bucket-scoped notification-record repository.
            content_guard: Legal comparecencia guard for notification rows.
            document_fetcher: Sede document fetch port.
            document_reader: In-memory PDF/text reading port.
        """
        self._settings = settings
        self._attachment_store = attachment_store
        self._repository_factory = repository_factory
        self._content_guard = content_guard
        self._document_fetcher = document_fetcher
        self._document_reader = document_reader

    def persist_document(
        self,
        *,
        bucket_id: str,
        row: NotificationRowProtocol,
        document: NotificationDocumentProtocol,
    ) -> NotificationDocumentCustody:
        """Take custody of already-fetched document bytes and record the binding.

        Split from :meth:`pull_document` so the custody boundary is exercisable
        without a browser: everything below the wire — encryption, the
        content-addressed write, the reading, the record — runs here.

        **Re-storing a certificado already in custody is a content-addressed
        no-op.** A non-interactive caller may retry, and the
        AEAT document behind one certificado is immutable — the act was served
        once. So a retry carrying the same bytes returns the record that is
        already stored: no second attachment write, no re-run of the reading,
        no re-stamped ``fetched_at``, and no second secure-object write. A
        retry that carries DIFFERENT content refuses instead, because either
        the stored row or the incoming one is wrong about a taxpayer's served
        act and overwriting silently would destroy the evidence of which.

        Args:
            bucket_id: The profile bucket taking custody.
            row: The notification the document belongs to. Re-checked against
                the legal guard before anything is written.
            document: The fetched bytes, held in memory.

        Returns:
            A :class:`NotificationDocumentCustody` carrying the persisted
            record — the one already in custody when this call was a no-op —
            and the flag saying which of the two happened.

        Raises:
            SedeNavigationError: When ``row`` is not a notification AEAT has
                already recorded as read.
            LiveApplicationInputError: When the document does not belong to the
                supplied row, or when a document is already in custody for this
                certificado and the incoming one disagrees with it.
        """
        self._content_guard(row)
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

        repository = self._repository_factory(bucket_id)
        existing = _record_in_custody(repository, str(row.certificado_id))
        if existing is not None:
            diverging = _diverging_persisted_fields(
                existing,
                bucket_id=bucket_id,
                row=row,
                document=document,
            )
            if diverging:
                raise LiveApplicationInputError(
                    translated_message="application.live.notifications.errors.document_conflict",
                    context={
                        "certificado_id": str(row.certificado_id),
                        "diverging_fields": ", ".join(diverging),
                        "stored_document_sha256": existing.document_sha256,
                        "incoming_document_sha256": document.pdf_sha256,
                    },
                )
            log.info(
                "notification document already in custody, storing nothing: certificado=%s",
                row.certificado_id,
            )
            return NotificationDocumentCustody(record=existing, already_in_custody=True)

        attachment = add_attachment(
            self._attachment_store,
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
        repository.save(record)
        log.info(
            "notification document stored: certificado=%s bytes=%d parsed=%s",
            row.certificado_id,
            len(document.pdf_bytes),
            sancion is not None,
        )
        return NotificationDocumentCustody(record=record, already_in_custody=False)

    async def pull_document(
        self,
        *,
        bucket_id: str,
        session: object,
        row: NotificationRowProtocol,
    ) -> NotificationDocumentCustody:
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
            The :class:`NotificationDocumentCustody` outcome. A second pull of
            the same certificado re-fetches the served bytes — AEAT's own
            record of a redisplay is not this application's to suppress — but
            stores nothing and reports ``already_in_custody``.

        Raises:
            SedeNavigationError: When ``row`` is anything other than already
                read, or when the AEAT landing is off-policy.
        """
        self._content_guard(row)
        document = await self._document_fetcher(session, row, settings=self._settings)
        return self.persist_document(bucket_id=bucket_id, row=row, document=document)

    def show(self, *, bucket_id: str, certificado_id: str) -> NotificationDocumentRecord:
        """Return the stored record for one certificado, or raise if none is stored."""
        return self._repository_factory(bucket_id).load(certificado_id)

    def list_documents(self, *, bucket_id: str) -> tuple[NotificationDocumentRecord, ...]:
        """Return every stored document record for the bucket, newest fetch first."""
        records = self._repository_factory(bucket_id).list_snapshots()
        return tuple(sorted(records, key=lambda record: record.fetched_at, reverse=True))

    def _read_document(self, document: NotificationDocumentProtocol) -> tuple[SancionLiquidacion | None, str | None]:
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
        sancion, refusal = self._document_reader.read(document)
        if refusal is not None:
            log.info(
                "notification document reading refused: certificado=%s",
                document.certificado_id,
            )
        return sancion, refusal


__all__ = [
    "NotificationDocumentCustody",
    "NotificationDocumentNotFoundError",
    "NotificationDocumentRecord",
    "NotificationDocumentService",
    "notification_document_object_key",
]
