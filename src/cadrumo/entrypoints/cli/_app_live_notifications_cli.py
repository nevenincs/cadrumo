"""Behavior handlers for live notification snapshot commands.

The pull command delegates the live DEHú read to :func:`capture_notifications`;
the list, view, and latest commands read bucket-local
:class:`PersistedNotificationsSnapshot` records through
:class:`NotificationsService`. Every command emits a typed app-live payload and
does not acknowledge, mark, submit, or mutate notifications in AEAT.

The ``document`` subgroup reaches one notification's served content.
``document pull`` is the only verb in this module that can cause an AEAT
request for a document, and it is guarded by
:func:`~adapters.outbound.aeat.sede.assert_notification_content_readable`:
AEAT serves a notification's content and performs its *comparecencia* through
the same control, so driving it on an unread notification is the act that makes
the notification legally served, starts the appeal and payment periods, and
requires the taxpayer's own signature. That signature is theirs alone to give,
so the guard admits nothing but a notification AEAT already reports as read and
this module adds no flag, option or branch that can widen it. ``document view``
reads the encrypted local record and contacts AEAT not at all.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Literal, TypedDict

import typer

from ...adapters.inbound.notificacion import NotificationDocumentReader
from ...adapters.outbound.aeat.sede import assert_notification_content_readable, fetch_notification_document
from ...adapters.persistence.profile.snapshots import SecureSnapshotRepository
from ...adapters.persistence.storage import (
    LIVE_NOTIFICATION_DOCUMENT_NAMESPACE,
    AttachmentStore,
    secure_object_repository_for_bucket,
)
from ...application.live import (
    LiveApplicationInputError,
    NotificationDocumentNotFoundError,
    NotificationDocumentRecord,
    NotificationDocumentService,
    NotificationsService,
    capture_notifications,
    notification_document_object_key,
    pull_notification_document,
)
from ...core.config import Settings, load_settings
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ._app_live_auth_preflight import _emit_live_auth_preflight
from ._app_live_notifications_payloads import (
    NotificationDocumentHistoryEntry,
    NotificationDocumentHistoryResult,
    NotificationDocumentPullResult,
    NotificationDocumentViewResult,
    NotificationRowPayload,
    NotificationsCaptureResult,
    NotificationsLatestResult,
    NotificationsListResult,
    NotificationSnapshotListingPayload,
    NotificationsViewResult,
    SancionReadingPayload,
)
from ._common import active_bucket_id_or_refuse, emit_envelope, notice_lines

if TYPE_CHECKING:
    from ...domain.notifications import SancionLiquidacion


def _bucket_id() -> str:
    return active_bucket_id_or_refuse()


def _notification_document_service(settings: Settings) -> NotificationDocumentService:
    """Compose the notification-document use case with its real adapters."""

    def repository_factory(bucket_id: str) -> SecureSnapshotRepository[NotificationDocumentRecord]:
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

    return NotificationDocumentService(
        settings=settings,
        attachment_store=AttachmentStore(),
        repository_factory=repository_factory,
        content_guard=assert_notification_content_readable,
        document_fetcher=fetch_notification_document,
        document_reader=NotificationDocumentReader(),
    )


def notifications_pull(ctx: typer.Context) -> None:
    """Drive the live DEHu fetch and persist flow.

    The live read is performed by :func:`capture_notifications`, persisted as a
    :class:`PersistedNotificationsSnapshot`, and emitted through
    :class:`NotificationsCaptureResult`.
    """
    bucket_id = _bucket_id()
    _emit_live_auth_preflight()
    persisted = asyncio.run(capture_notifications(bucket_id=bucket_id))
    result = NotificationsCaptureResult(
        bucket_id=bucket_id,
        snapshot_id=persisted.snapshot_id,
        captured_at=persisted.captured_at,
        persisted_at=persisted.persisted_at,
        row_count=len(persisted.rows),
        source_url=persisted.source_url,
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{persisted.snapshot_id}",
        f"captured_at\t{persisted.captured_at.isoformat()}",
        f"row_count\t{len(persisted.rows)}",
        f"source_url\t{persisted.source_url}",
    ]
    emit_envelope(ctx, command="app.live.notifications.pull", result=result, lines=lines)


def notifications_list(ctx: typer.Context) -> None:
    """List persisted DEHu notification snapshots without contacting AEAT.

    The command reads :class:`NotificationsService` storage for the active
    bucket and emits :class:`NotificationsListResult` summaries rather than
    expanding notification rows.
    """
    bucket_id = _bucket_id()
    rows = NotificationsService().list_snapshots(bucket_id=bucket_id)
    result = NotificationsListResult(
        bucket_id=bucket_id,
        count=len(rows),
        rows=[
            NotificationSnapshotListingPayload(
                snapshot_id=r.snapshot_id,
                captured_at=r.captured_at,
                row_count=len(r.rows),
            )
            for r in rows
        ],
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for r in rows:
        lines.append(f"{r.snapshot_id}\t{r.captured_at.isoformat()}\trows={len(r.rows)}")
    emit_envelope(ctx, command="app.live.notifications.list", result=result, lines=lines)


def notifications_show(
    ctx: typer.Context,
    snapshot_id: str,
) -> None:
    """Show one persisted DEHu notification snapshot by id prefix.

    The id is resolved through :class:`NotificationsService` ``show``, then
    projected as :class:`NotificationsViewResult`. This local view does not
    acknowledge, submit, or mark notifications remotely.
    """
    bucket_id = _bucket_id()
    record = NotificationsService().show(bucket_id=bucket_id, snapshot_id=snapshot_id)
    result = NotificationsViewResult(
        bucket_id=bucket_id,
        snapshot_id=record.snapshot_id,
        captured_at=record.captured_at,
        source_url=record.source_url,
        row_count=len(record.rows),
        rows=[
            NotificationRowPayload(
                certificado_id=r.certificado_id,
                tipo=r.tipo,
                concepto=r.concepto,
                titular_nif=r.titular_nif,
                titular_nombre=r.titular_nombre,
                destinatario_nif=r.destinatario_nif,
                destinatario_nombre=r.destinatario_nombre,
                fecha_emision=r.fecha_emision.isoformat(),
                fecha_notificacion=r.fecha_notificacion.isoformat() if r.fecha_notificacion else None,
                modo_notificacion=r.modo_notificacion,
                leida=r.leida,
                source_url=str(r.source_url),
                mode=r.mode,
            )
            for r in record.rows
        ],
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"source_url\t{record.source_url}",
        f"row_count\t{len(record.rows)}",
    ]
    for r in record.rows:
        lines.append("\t".join(f"{k}={v}" for k, v in r.model_dump(mode="json").items()))
    emit_envelope(ctx, command="app.live.notifications.view", result=result, lines=lines)


def notifications_latest(ctx: typer.Context) -> None:
    """Show the most recent DEHu notification snapshot, or report none.

    A missing snapshot from :class:`NotificationsService` still emits
    :class:`NotificationsLatestResult` with ``snapshot_id=None`` so automation
    can distinguish no local capture from a live-read failure.
    """
    bucket_id = _bucket_id()
    record = NotificationsService().latest(bucket_id=bucket_id)
    if record is None:
        empty = NotificationsLatestResult(bucket_id=bucket_id, snapshot_id=None)
        emit_envelope(
            ctx,
            command="app.live.notifications.latest",
            result=empty,
            lines=[f"bucket\t{bucket_id}", "snapshot_id\t-"],
        )
        return
    result = NotificationsLatestResult(
        bucket_id=bucket_id,
        snapshot_id=record.snapshot_id,
        captured_at=record.captured_at,
        source_url=record.source_url,
        row_count=len(record.rows),
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"row_count\t{len(record.rows)}",
    ]
    emit_envelope(ctx, command="app.live.notifications.latest", result=result, lines=lines)


def _sancion_payload(sancion: SancionLiquidacion) -> SancionReadingPayload:
    """Project a stored reading, rendering every amount as its canonical decimal string."""
    return SancionReadingPayload(
        certificado_id=str(sancion.certificado_id),
        clave_liquidacion=str(sancion.clave_liquidacion),
        referencia=sancion.referencia,
        nif=sancion.nif,
        objeto_tributario=sancion.objeto_tributario,
        base_sancion=str(sancion.base_sancion),
        porcentaje_minimo=str(sancion.porcentaje_minimo),
        sancion_resultante=str(sancion.sancion_resultante),
        reduccion_conformidad=None if sancion.reduccion_conformidad is None else str(sancion.reduccion_conformidad),
        reduccion_pronto_pago=None if sancion.reduccion_pronto_pago is None else str(sancion.reduccion_pronto_pago),
        diferencia=None if sancion.diferencia is None else str(sancion.diferencia),
        importe_a_ingresar=str(sancion.importe_a_ingresar),
        document_sha256=sancion.document_sha256,
    )


class _NotificationDocumentPayloadFields(TypedDict):
    """Precisely typed shared fields passed to the two document payloads."""

    bucket_id: str
    certificado_id: str
    attachment_id: str
    document_sha256: str
    byte_size: int
    source_url: str
    fetched_at: datetime
    sancion_parsed: bool
    sancion: SancionReadingPayload | None
    parse_refusal: str | None
    mode: Literal["read"]


def _document_payload_fields(
    bucket_id: str,
    record: NotificationDocumentRecord,
) -> _NotificationDocumentPayloadFields:
    """Build the fields both document leaves share, from the one stored record."""
    return {
        "bucket_id": bucket_id,
        "certificado_id": str(record.certificado_id),
        "attachment_id": record.attachment_id,
        "document_sha256": record.document_sha256,
        "byte_size": record.byte_size,
        "source_url": record.source_url,
        "fetched_at": record.fetched_at,
        "sancion_parsed": record.sancion is not None,
        "sancion": None if record.sancion is None else _sancion_payload(record.sancion),
        "parse_refusal": record.parse_refusal,
        "mode": "read",
    }


def _document_lines(bucket_id: str, record: NotificationDocumentRecord) -> list[str]:
    """Render the stored record's own figures as text lines, values included."""
    lines = [
        f"bucket\t{bucket_id}",
        f"certificado_id\t{record.certificado_id}",
        f"attachment_id\t{record.attachment_id}",
        f"document_sha256\t{record.document_sha256}",
        f"byte_size\t{record.byte_size}",
        f"source_url\t{record.source_url}",
        f"fetched_at\t{record.fetched_at.isoformat()}",
        f"sancion_parsed\t{record.sancion is not None}",
    ]
    if record.sancion is not None:
        reading = record.sancion
        lines.extend(
            [
                f"clave_liquidacion\t{reading.clave_liquidacion}",
                f"referencia\t{reading.referencia}",
                f"objeto_tributario\t{reading.objeto_tributario}",
                f"base_sancion\t{reading.base_sancion}",
                f"porcentaje_minimo\t{reading.porcentaje_minimo}",
                f"sancion_resultante\t{reading.sancion_resultante}",
                f"importe_a_ingresar\t{reading.importe_a_ingresar}",
            ],
        )
    return lines


def _comparecencia_notice(record: NotificationDocumentRecord) -> Notice:
    """State the legal constraint the fetch honoured, on every successful pull.

    The refusal on an unread notification is designed behaviour, not a fault,
    and an operator who only ever meets it as an error has no way to learn
    that. Saying it on the path that SUCCEEDS is what makes the refusal legible
    before it happens: this fetch redisplayed a document AEAT already records
    the taxpayer as having read, and nothing in this application drives the
    control that would serve an unread one.
    """
    return Notice(
        severity=NoticeSeverity.INFO,
        code="live.notifications.document.comparecencia_guarded",
        message=tr(
            "cli.app.live.notifications.document.comparecencia_notice",
            default=(
                "This document was fetched only because AEAT already reports the notification as read by the "
                "taxpayer. Opening an unread notification is the comparecencia that makes it legally served and "
                "starts its appeal and payment periods, so an unread notification is refused and must be opened "
                "by the taxpayer personally."
            ),
        ),
        context={"certificado_id": str(record.certificado_id), "comparecencia_performed": "false"},
    )


def _already_in_custody_notice(record: NotificationDocumentRecord) -> Notice:
    """Say plainly that the retry stored nothing, so a no-op is not read as an ingest."""
    return Notice(
        severity=NoticeSeverity.INFO,
        code="live.notifications.document.already_in_custody",
        message=tr(
            "cli.app.live.notifications.document.already_in_custody_notice",
            default=(
                "This document was already held for that notification with identical content, so nothing was "
                "stored again and the fetch timestamp was left as it was. The record returned is the one already "
                "in custody."
            ),
        ),
        context={
            "certificado_id": str(record.certificado_id),
            "document_sha256": record.document_sha256,
            "fetched_at": record.fetched_at.isoformat(),
        },
    )


def _unparsed_document_notice(record: NotificationDocumentRecord) -> Notice | None:
    """Report a document the reader refused, rather than presenting it as figureless.

    A document with no reading is NOT a document with no figures. The bytes are
    in custody either way and remain the authoritative artefact; only the
    convenience reading is missing, and the operator has to be told so they read
    the document themselves instead of concluding the act carried no amounts.
    """
    if record.parse_refusal is None:
        return None
    return Notice(
        severity=NoticeSeverity.INFO,
        code="live.notifications.document.unparsed",
        message=tr(
            "cli.app.live.notifications.document.unparsed_notice",
            default=(
                "No figures were read from this document, so it is held as bytes only. That is not a statement "
                "that the document carries no amounts: read the stored document itself before concluding "
                "anything about what it says. Consult the original, already-opened notification in the AEAT "
                "sede; this command does not render or export the encrypted PDF bytes."
            ),
        ),
        context={"certificado_id": str(record.certificado_id), "parse_refusal": record.parse_refusal},
    )


def _document_notices(record: NotificationDocumentRecord, *, notices: Sequence[Notice]) -> list[Notice]:
    """Append the shared unparsed-document report to a leaf's own notices."""
    collected = list(notices)
    unparsed = _unparsed_document_notice(record)
    if unparsed is not None:
        collected.append(unparsed)
    return collected


def notifications_document_pull(
    ctx: typer.Context,
    certificado_id: str,
) -> None:
    """Fetch and take custody of one already-read notification's document.

    The row is resolved from the bucket's own captured notification snapshots
    so the comparecencia guard keys on what AEAT reported, never on anything a
    caller supplied. A notification AEAT does not already report as read is
    refused before any request crosses the wire.
    """
    bucket_id = _bucket_id()
    _emit_live_auth_preflight()
    service = _notification_document_service(load_settings())
    custody = asyncio.run(
        pull_notification_document(
            bucket_id=bucket_id,
            certificado_id=certificado_id,
            service=service,
        )
    )
    record = custody.record
    result = NotificationDocumentPullResult(
        already_in_custody=custody.already_in_custody,
        **_document_payload_fields(bucket_id, record),
    )
    leaf_notices: list[Notice] = [_comparecencia_notice(record)]
    if custody.already_in_custody:
        leaf_notices.append(_already_in_custody_notice(record))
    notices = _document_notices(record, notices=leaf_notices)
    lines = [
        *_document_lines(bucket_id, record),
        f"already_in_custody\t{custody.already_in_custody}",
        *notice_lines(notices),
    ]
    emit_envelope(
        ctx,
        command="app.live.notifications.document.pull",
        result=result,
        lines=lines,
        notices=notices,
    )


def notifications_document_view(
    ctx: typer.Context,
    certificado_id: str,
) -> None:
    """Read back one stored notification document from bucket-local custody.

    Nothing here authenticates, navigates or fetches: the record and its
    reading come from the encrypted secure-object store, so this verb cannot be
    the act that serves a notification. It runs with no AEAT session at all.
    """
    bucket_id = _bucket_id()
    record = _notification_document_service(load_settings()).show(
        bucket_id=bucket_id,
        certificado_id=certificado_id,
    )
    result = NotificationDocumentViewResult(**_document_payload_fields(bucket_id, record))
    notices = _document_notices(record, notices=())
    lines = [*_document_lines(bucket_id, record), *notice_lines(notices)]
    emit_envelope(
        ctx,
        command="app.live.notifications.document.view",
        result=result,
        lines=lines,
        notices=notices,
    )


def _history_notice(*, count: int) -> Notice:
    """Bound the history to what each served document actually reports."""
    return Notice(
        severity=NoticeSeverity.INFO,
        code="live.notifications.document.history_not_balance",
        message=tr(
            "cli.app.live.notifications.document.history_notice",
            default=(
                "This history records figures AEAT served in individual notification documents. It is not a "
                "payable balance or the recaudacion register read by the deudas commands: payment, appeal, "
                "reduction and supersession are not established by this view."
            ),
        ),
        context={"document_count": str(count), "total_computed": "false"},
    )


def notifications_document_history(ctx: typer.Context) -> None:
    """List parsed documents in encrypted custody without asserting a balance."""
    bucket_id = _bucket_id()
    records = tuple(
        record
        for record in _notification_document_service(load_settings()).list_documents(bucket_id=bucket_id)
        if record.sancion is not None
    )
    documents = [
        NotificationDocumentHistoryEntry(
            certificado_id=str(record.certificado_id),
            fetched_at=record.fetched_at,
            sancion=_sancion_payload(record.sancion),
        )
        for record in records
        if record.sancion is not None
    ]
    result = NotificationDocumentHistoryResult(bucket_id=bucket_id, count=len(documents), documents=documents)
    notices = [_history_notice(count=len(documents))]
    lines = [f"bucket\t{bucket_id}", f"count\t{len(documents)}"]
    for document in documents:
        reading = document.sancion
        lines.extend(
            (
                f"certificado_id\t{document.certificado_id}",
                f"fetched_at\t{document.fetched_at.isoformat()}",
                f"clave_liquidacion\t{reading.clave_liquidacion}",
                f"referencia\t{reading.referencia}",
                f"objeto_tributario\t{reading.objeto_tributario}",
                f"base_sancion\t{reading.base_sancion}",
                f"porcentaje_minimo\t{reading.porcentaje_minimo}",
                f"sancion_resultante\t{reading.sancion_resultante}",
                f"reduccion_conformidad\t{reading.reduccion_conformidad}",
                f"reduccion_pronto_pago\t{reading.reduccion_pronto_pago}",
                f"diferencia\t{reading.diferencia}",
                f"importe_a_ingresar\t{reading.importe_a_ingresar}",
            ),
        )
    lines.extend(notice_lines(notices))
    emit_envelope(
        ctx,
        command="app.live.notifications.document.history",
        result=result,
        lines=lines,
        notices=notices,
    )


__all__ = [
    "notifications_document_history",
    "notifications_document_pull",
    "notifications_document_view",
    "notifications_latest",
    "notifications_list",
    "notifications_pull",
    "notifications_show",
]
