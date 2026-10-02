"""Behavior handlers for live notification snapshot commands.

The pull command submits the live DEHú read through its exact-profile registered
operation; the list, view, and latest commands read bucket-local notification
snapshots through registered profile operations. Every command emits a typed
app-live payload and does not acknowledge, mark, submit, or mutate notifications
in AEAT.

The ``document`` subgroup reaches one notification's served content.
``document pull`` is the only verb in this module that can cause an AEAT
request for a document. Its registered capture operation enforces the content
read guard before making that request: AEAT serves a notification's content
and performs its *comparecencia* through the same control, so driving it on an
unread notification is the act that makes the notification legally served,
starts the appeal and payment periods, and requires the taxpayer's own
signature. That signature is theirs alone to give, so the guard admits nothing
but a notification AEAT already reports as read. ``document view`` reads the
encrypted local record and contacts AEAT not at all.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal, TypedDict
from uuid import UUID

import typer

from ...application.live.notification_document_read_operation import (
    NotificationDocumentSancionPublicV1,
    NotificationDocumentViewPublicResultV1,
)
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ._app_live_auth_preflight import emit_live_auth_preflight
from ._app_live_notifications_payloads import (
    NotificationDocumentHistoryEntry,
    NotificationDocumentHistoryResult,
    NotificationDocumentPayload,
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
from .common import active_bucket_id_or_refuse, emit_envelope, notice_lines
from .runtime_notification_document_capture import capture_notification_document_for_cli
from .runtime_notification_document_read import (
    read_notification_document_history_for_cli,
    read_notification_document_view_for_cli,
)
from .runtime_notifications_capture import read_notifications_capture_for_cli
from .runtime_notifications_read import (
    read_notifications_latest_for_cli,
    read_notifications_list_for_cli,
    read_notifications_show_for_cli,
)


def notifications_pull(ctx: typer.Context) -> None:
    """Drive the live DEHu fetch and persist flow through its profile worker.

    The registered exact-profile operation persists a
    :class:`PersistedNotificationsSnapshot` and emits the existing
    :class:`NotificationsCaptureResult` presentation.
    """
    bucket_id = active_bucket_id_or_refuse()
    emit_live_auth_preflight(ctx)
    profile_id = UUID(bucket_id)
    read = read_notifications_capture_for_cli(ctx, profile_id=profile_id)
    projection = read.projection
    try:
        if UUID(projection.bucket_id) != profile_id:
            raise ValueError("notification capture result does not match its active profile")
        result = NotificationsCaptureResult(
            bucket_id=bucket_id,
            snapshot_id=projection.snapshot_id,
            captured_at=projection.captured_at,
            persisted_at=projection.persisted_at,
            row_count=projection.row_count,
            source_url=projection.source_url,
        )
    except Exception:
        from ...application.runtime.contracts import RuntimeRefusalCode
        from .runtime_registered_operation import submitted_operation_error

        completed = read.completion
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{projection.snapshot_id}",
        f"captured_at\t{projection.captured_at.isoformat()}",
        f"row_count\t{projection.row_count}",
        f"source_url\t{projection.source_url}",
    ]
    emit_envelope(ctx, command="app.live.notifications.pull", result=result, lines=lines)


def notifications_list(ctx: typer.Context) -> None:
    """List persisted DEHu notification snapshots without contacting AEAT.

    The registered exact-profile read emits :class:`NotificationsListResult`
    summaries rather than expanding notification rows.
    """
    projection = read_notifications_list_for_cli(ctx).projection
    bucket_id = projection.bucket_id
    result = NotificationsListResult(
        bucket_id=bucket_id,
        count=projection.count,
        rows=[
            NotificationSnapshotListingPayload(
                snapshot_id=row.snapshot_id,
                captured_at=row.captured_at,
                row_count=row.row_count,
            )
            for row in projection.rows
        ],
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{projection.count}"]
    for row in projection.rows:
        lines.append(f"{row.snapshot_id}\t{row.captured_at.isoformat()}\trows={row.row_count}")
    emit_envelope(ctx, command="app.live.notifications.list", result=result, lines=lines)


def notifications_show(
    ctx: typer.Context,
    snapshot_id: str,
) -> None:
    """Show one persisted DEHu notification snapshot by id prefix.

    The id prefix is resolved by the registered exact-profile operation, then
    projected as :class:`NotificationsViewResult`. This local view does not
    acknowledge, submit, or mark notifications remotely.
    """
    projection = read_notifications_show_for_cli(ctx, snapshot_id=snapshot_id).projection
    bucket_id = projection.bucket_id
    result = NotificationsViewResult(
        bucket_id=bucket_id,
        snapshot_id=projection.snapshot_id,
        captured_at=projection.captured_at,
        source_url=projection.source_url,
        row_count=projection.row_count,
        rows=[
            NotificationRowPayload(
                certificado_id=row.certificado_id,
                tipo=row.tipo,
                concepto=row.concepto,
                titular_nif=row.titular_nif,
                titular_nombre=row.titular_nombre,
                destinatario_nif=row.destinatario_nif,
                destinatario_nombre=row.destinatario_nombre,
                fecha_emision=row.fecha_emision.isoformat(),
                fecha_notificacion=row.fecha_notificacion.isoformat() if row.fecha_notificacion else None,
                modo_notificacion=row.modo_notificacion,
                leida=row.leida,
                source_url=row.source_url,
                mode=row.mode,
            )
            for row in projection.rows
        ],
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{projection.snapshot_id}",
        f"captured_at\t{projection.captured_at.isoformat()}",
        f"source_url\t{projection.source_url}",
        f"row_count\t{projection.row_count}",
    ]
    for row in result.rows:
        lines.append("\t".join(f"{k}={v}" for k, v in row.model_dump(mode="json").items()))
    emit_envelope(ctx, command="app.live.notifications.view", result=result, lines=lines)


def notifications_latest(ctx: typer.Context) -> None:
    """Show the most recent DEHu notification snapshot, or report none.

    A missing snapshot still emits :class:`NotificationsLatestResult` with
    ``snapshot_id=None`` so automation can distinguish no local capture from a
    live-read failure.
    """
    projection = read_notifications_latest_for_cli(ctx).projection
    bucket_id = projection.bucket_id
    if projection.snapshot_id is None:
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
        snapshot_id=projection.snapshot_id,
        captured_at=projection.captured_at,
        source_url=projection.source_url,
        row_count=projection.row_count,
    )
    captured_at = projection.captured_at
    source_url = projection.source_url
    row_count = projection.row_count
    if captured_at is None or source_url is None or row_count is None:
        raise ValueError("latest notification projection is missing snapshot details")
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{projection.snapshot_id}",
        f"captured_at\t{captured_at.isoformat()}",
        f"row_count\t{row_count}",
    ]
    emit_envelope(ctx, command="app.live.notifications.latest", result=result, lines=lines)


def _public_sancion_payload(sancion: NotificationDocumentSancionPublicV1) -> SancionReadingPayload:
    """Adapt the operation's already-redacted reading to the CLI payload."""
    return SancionReadingPayload(
        certificado_id=sancion.certificado_id,
        clave_liquidacion=sancion.clave_liquidacion,
        referencia=sancion.referencia,
        nif=sancion.nif,
        objeto_tributario=sancion.objeto_tributario,
        base_sancion=sancion.base_sancion,
        porcentaje_minimo=sancion.porcentaje_minimo,
        sancion_resultante=sancion.sancion_resultante,
        reduccion_conformidad=sancion.reduccion_conformidad,
        reduccion_pronto_pago=sancion.reduccion_pronto_pago,
        diferencia=sancion.diferencia,
        importe_a_ingresar=sancion.importe_a_ingresar,
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


def _document_projection_fields(
    bucket_id: str,
    projection: NotificationDocumentViewPublicResultV1,
) -> _NotificationDocumentPayloadFields:
    """Adapt one registered safe projection to the existing CLI result fields."""
    return {
        "bucket_id": bucket_id,
        "certificado_id": str(projection.certificado_id),
        "attachment_id": projection.attachment_id,
        "document_sha256": projection.document_sha256,
        "byte_size": projection.byte_size,
        "source_url": projection.source_url,
        "fetched_at": projection.fetched_at,
        "sancion_parsed": projection.sancion_parsed,
        "sancion": None if projection.sancion is None else _public_sancion_payload(projection.sancion),
        "parse_refusal": projection.parse_refusal,
        "mode": projection.mode,
    }


def _document_lines(result: NotificationDocumentPayload) -> list[str]:
    """Render the existing document payload's figures as text lines."""
    lines = [
        f"bucket\t{result.bucket_id}",
        f"certificado_id\t{result.certificado_id}",
        f"attachment_id\t{result.attachment_id}",
        f"document_sha256\t{result.document_sha256}",
        f"byte_size\t{result.byte_size}",
        f"source_url\t{result.source_url}",
        f"fetched_at\t{result.fetched_at.isoformat()}",
        f"sancion_parsed\t{result.sancion_parsed}",
    ]
    if result.sancion is not None:
        reading = result.sancion
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


def _comparecencia_notice(result: NotificationDocumentPayload) -> Notice:
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
        ),
        context={"certificado_id": str(result.certificado_id), "comparecencia_performed": "false"},
    )


def _already_in_custody_notice(result: NotificationDocumentPullResult) -> Notice:
    """Say plainly that the retry stored nothing, so a no-op is not read as an ingest."""
    return Notice(
        severity=NoticeSeverity.INFO,
        code="live.notifications.document.already_in_custody",
        message=tr(
            "cli.app.live.notifications.document.already_in_custody_notice",
        ),
        context={
            "certificado_id": str(result.certificado_id),
            "document_sha256": result.document_sha256,
            "fetched_at": result.fetched_at.isoformat(),
        },
    )


def _unparsed_document_notice(result: NotificationDocumentPayload) -> Notice | None:
    """Report a document the reader refused, rather than presenting it as figureless.

    A document with no reading is NOT a document with no figures. The bytes are
    in custody either way and remain the authoritative artefact; only the
    convenience reading is missing, and the operator has to be told so they read
    the document themselves instead of concluding the act carried no amounts.
    """
    if result.parse_refusal is None:
        return None
    return Notice(
        severity=NoticeSeverity.INFO,
        code="live.notifications.document.unparsed",
        message=tr(
            "cli.app.live.notifications.document.unparsed_notice",
        ),
        context={"certificado_id": str(result.certificado_id), "parse_refusal": result.parse_refusal},
    )


def _document_notices(result: NotificationDocumentPayload, *, notices: Sequence[Notice]) -> list[Notice]:
    """Append the shared unparsed-document report to a leaf's own notices."""
    collected = list(notices)
    unparsed = _unparsed_document_notice(result)
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
    bucket_id = active_bucket_id_or_refuse()
    emit_live_auth_preflight(ctx)
    profile_id = UUID(bucket_id)
    read = capture_notification_document_for_cli(
        ctx,
        profile_id=profile_id,
        certificado_id=certificado_id,
    )
    projection = read.projection
    try:
        if UUID(projection.bucket_id) != profile_id or projection.certificado_id != certificado_id:
            raise ValueError("notification-document capture result does not match its active profile and certificado")
        result = NotificationDocumentPullResult(
            already_in_custody=projection.already_in_custody,
            **_document_projection_fields(bucket_id, projection),
        )
    except Exception:
        from ...application.runtime.contracts import RuntimeRefusalCode
        from .runtime_registered_operation import submitted_operation_error

        completed = read.completion
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    leaf_notices: list[Notice] = [_comparecencia_notice(result)]
    if result.already_in_custody:
        leaf_notices.append(_already_in_custody_notice(result))
    notices = _document_notices(result, notices=leaf_notices)
    lines = [
        *_document_lines(result),
        f"already_in_custody\t{result.already_in_custody}",
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
    bucket_id = active_bucket_id_or_refuse()
    profile_id = UUID(bucket_id)
    read = read_notification_document_view_for_cli(
        ctx,
        profile_id=profile_id,
        certificado_id=certificado_id,
    )
    projection = read.projection
    try:
        if UUID(projection.bucket_id) != profile_id or projection.certificado_id != certificado_id:
            raise ValueError("notification-document view result does not match its active profile and certificado")
        result = NotificationDocumentViewResult(**_document_projection_fields(bucket_id, projection))
    except Exception:
        from ...application.runtime.contracts import RuntimeRefusalCode
        from .runtime_registered_operation import submitted_operation_error

        completed = read.completion
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    notices = _document_notices(result, notices=())
    lines = [*_document_lines(result), *notice_lines(notices)]
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
        ),
        context={"document_count": str(count), "total_computed": "false"},
    )


def notifications_document_history(ctx: typer.Context) -> None:
    """List parsed documents in encrypted custody without asserting a balance."""
    bucket_id = active_bucket_id_or_refuse()
    profile_id = UUID(bucket_id)
    read = read_notification_document_history_for_cli(ctx, profile_id=profile_id)
    projection = read.projection
    try:
        if UUID(projection.bucket_id) != profile_id or projection.count != len(projection.documents):
            raise ValueError("notification-document history does not match its active profile and rows")
        documents = [
            NotificationDocumentHistoryEntry(
                certificado_id=str(row.certificado_id),
                fetched_at=row.fetched_at,
                sancion=_public_sancion_payload(row.sancion),
            )
            for row in projection.documents
        ]
        result = NotificationDocumentHistoryResult(
            bucket_id=bucket_id,
            count=projection.count,
            documents=documents,
        )
    except Exception:
        from ...application.runtime.contracts import RuntimeRefusalCode
        from .runtime_registered_operation import submitted_operation_error

        completed = read.completion
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
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
