"""Shared fixtures for the notification-document custody and service suites.

The served PDF is BUILT here rather than committed as a file: the bytes AEAT
serves are the taxpayer's own sanción, and this repository is not a home for
them. Two suites need the same construction — the custody roundtrip and the
service semantics — so it lives once, here, rather than once per suite.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from functools import cache
from typing import TYPE_CHECKING

from sqlalchemy import select

from ....adapters.inbound.notificacion.document_reader import NotificationDocumentReader
from ....adapters.outbound.aeat.sede.notifications import (
    NotificationDocument,
    RemoteNotification,
    assert_notification_content_readable,
    fetch_notification_document,
)
from ....adapters.persistence.profile.snapshots import SecureSnapshotRepository
from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ....adapters.persistence.storage.secure_object_namespaces import LIVE_NOTIFICATION_DOCUMENT_NAMESPACE
from ....adapters.persistence.storage.sql import SecureObjectRow
from ....adapters.persistence.storage.sql.session import session_scope
from ....application.live.errors import LiveApplicationInputError
from ....application.live.notification_documents import (
    NotificationDocumentNotFoundError,
    NotificationDocumentRecord,
    NotificationDocumentService,
    notification_document_object_key,
)
from ....core.config import load_settings
from ....core.hashing import sha256_hex
from ....domain.attachments.protocols import AttachmentStoreProtocol
from ....tests.aeat_literal_fixtures import NOTIFICATION_DETALLE_SEDE_URL_FIXTURE
from ....tests.pdf_fixtures import text_pdf_bytes
from ....tests.secure_sql import TestRuntimeProfile

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

BUCKET_ID = "61616161-6161-4161-8161-616161616161"
DOCUMENT_NAMESPACE = "cadrumo.application.live.notification_document"
CERT_READ = "2699101808461"
CERT_UNREAD = "2596230606502"
DETAIL_URL = f"{NOTIFICATION_DETALLE_SEDE_URL_FIXTURE}?ncc=2699101808461"

SANCION_TEXT_LINES = (
    "Clave de liquidacion: A2860024500012345",
    "Referencia: 2024/0001234",
    "N.I.F.: 12345678Z",
    "Base sobre la que se liquida la sancion 3.687,12euros",
    "Porcentaje minimo de sancion 50,00%",
    "Sancion resultante 1.843,56euros",
    "Reduccion del 30% 553,07euros",
    "Reduccion del 40% 516,20euros",
    "Diferencia 774,29euros",
)


@cache
def sancion_pdf_bytes(lines: tuple[str, ...] = SANCION_TEXT_LINES) -> bytes:
    """Render ``lines`` into a real single-page PDF with an extractable text layer.

    Delegates to the canonical reportlab-based builder, then self-verifies
    through pypdfium2 that the produced bytes really carry the text layer
    before any test relies on it, so what a test asserts on is text a real
    extractor genuinely recovers, not a string the test handed to itself.

    ``text_pdf_bytes`` builds with ``invariant=True``, so byte-stability
    across calls no longer depends on this cache -- it is a cost optimisation
    only, sparing repeat callers both the reportlab build and the pypdfium2
    verification below for a ``lines`` value already computed.
    """
    import pypdfium2 as pdfium

    data = text_pdf_bytes(lines)
    document = pdfium.PdfDocument(data)
    try:
        recovered = "\n".join(document[0].get_textpage().get_text_range().splitlines())
        assert lines[0] in recovered
    finally:
        document.close()
    return data


def read_row(*, certificado_id: str = CERT_READ) -> RemoteNotification:
    """Build a notification AEAT reports as READ, with every optional field set."""
    return RemoteNotification(
        certificado_id=certificado_id,
        tipo="notificacion",
        concepto="Acuerdo de resolucion de procedimiento sancionador",
        titular_nif="12345678Z",
        titular_nombre="PERSONA PRUEBA UNO",
        destinatario_nif="12345678Z",
        destinatario_nombre="PERSONA PRUEBA UNO",
        fecha_emision=date(2026, 2, 3),
        fecha_notificacion=date(2026, 2, 13),
        modo_notificacion="Comparecencia en sede electronica",
        leida=True,
        source_url=DETAIL_URL,
    )


def served_document(
    *,
    certificado_id: str = CERT_READ,
    data: bytes | None = None,
    source_url: str = DETAIL_URL,
) -> NotificationDocument:
    """Build the document AEAT served for one notification, digest included."""
    payload = data if data is not None else sancion_pdf_bytes()
    return NotificationDocument(
        certificado_id=certificado_id,
        pdf_bytes=payload,
        pdf_sha256=sha256_hex(payload),
        source_url=source_url,
    )


def build_service(
    *,
    bucket_id: str = BUCKET_ID,
    attachment_store: AttachmentStoreProtocol | None = None,
) -> NotificationDocumentService:
    """Compose the service with real storage, sede and reader adapters."""
    settings = load_settings()

    def repository_factory(resolved_bucket_id: str) -> SecureSnapshotRepository[NotificationDocumentRecord]:
        return SecureSnapshotRepository(
            bucket_id=resolved_bucket_id,
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
            objects=secure_object_repository_for_bucket(resolved_bucket_id, settings),
        )

    return NotificationDocumentService(
        settings=settings,
        attachment_store=(attachment_store if attachment_store is not None else AttachmentStore(bucket_id=bucket_id)),
        repository_factory=repository_factory,
        content_guard=assert_notification_content_readable,
        document_fetcher=fetch_notification_document,
        document_reader=NotificationDocumentReader(),
    )


@contextmanager
def stored_document_row(profile: TestRuntimeProfile, *, certificado_id: str = CERT_READ) -> Generator[SecureObjectRow]:
    """Yield the encrypted secure-object row holding one document record.

    Both suites reach the raw row for different reasons — one mutates it to
    prove the load refuses a dropped field, the other reads its ciphertext to
    prove a no-op wrote nothing — so the row lookup itself lives once.
    """
    object_key = notification_document_object_key(BUCKET_ID, certificado_id)
    session: Session
    with session_scope(profile.repository._engine) as session:  # type: ignore[attr-defined]
        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == DOCUMENT_NAMESPACE,
            SecureObjectRow.object_key == object_key,
        )
        yield session.execute(stmt).scalar_one()
