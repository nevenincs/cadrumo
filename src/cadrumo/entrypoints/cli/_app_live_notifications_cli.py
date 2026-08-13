"""Typer registration for live notification snapshot commands.

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
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Annotated

import typer

from ...application.live import (
    NotificationDocumentService,
    NotificationsService,
    capture_notifications,
    pull_notification_document,
)
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ._app_live_auth_preflight import resolve_active_bucket, run_auth_preflight
from ._app_live_payloads import (
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
from ._common import _emit_envelope, notice_lines

if TYPE_CHECKING:
    from ...adapters.inbound.notificacion import SancionLiquidacion
    from ...application.live import NotificationDocumentRecord

_active_bucket_id: Callable[[], str] | None = None
_auth_preflight: Callable[[], None] | None = None


def register_notifications_commands(
    app: typer.Typer,
    *,
    active_bucket_id: Callable[[], str],
    auth_preflight: Callable[[], None],
) -> None:
    """Mount live notification commands on the live app."""
    global _active_bucket_id, _auth_preflight
    _active_bucket_id = active_bucket_id
    _auth_preflight = auth_preflight
    app.add_typer(notifications_app, name="notifications")


def _bucket_id() -> str:
    return resolve_active_bucket(_active_bucket_id, family="notifications")


notifications_app = typer.Typer(
    name="notifications",
    help=tr("cli.app.live.notifications.app_help", default="DEHu notification snapshots (read-only)."),
    no_args_is_help=True,
    add_completion=False,
)


@notifications_app.command(
    "pull",
    help=tr(
        "cli.app.live.notifications.pull_help",
        default="Pull DEHu notifications and persist a bucket-scoped snapshot.",
    ),
)
def notifications_pull(ctx: typer.Context) -> None:
    """Drive the live DEHu fetch and persist flow.

    The live read is performed by :func:`capture_notifications`, persisted as a
    :class:`PersistedNotificationsSnapshot`, and emitted through
    :class:`NotificationsCaptureResult`.
    """
    bucket_id = _bucket_id()
    run_auth_preflight(_auth_preflight, family="notifications")
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
    _emit_envelope(ctx, command="app.live.notifications.pull", result=result, lines=lines)


@notifications_app.command(
    "list",
    help=tr(
        "cli.app.live.notifications.list_help",
        default="List persisted DEHu notification snapshots in the active profile.",
    ),
)
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
    _emit_envelope(ctx, command="app.live.notifications.list", result=result, lines=lines)


@notifications_app.command(
    "view",
    help=tr("cli.app.live.notifications.view_help", default="View one DEHu notification snapshot."),
)
def notifications_show(
    ctx: typer.Context,
    snapshot_id: Annotated[
        str,
        typer.Argument(
            help=tr("cli.app.live.notifications.snapshot_id_help", default="Snapshot id (or unambiguous prefix)."),
        ),
    ],
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
    _emit_envelope(ctx, command="app.live.notifications.view", result=result, lines=lines)


@notifications_app.command(
    "latest",
    help=tr(
        "cli.app.live.notifications.latest_help",
        default="Show the most recent DEHu notification snapshot in the active profile.",
    ),
)
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
        _emit_envelope(
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
    _emit_envelope(ctx, command="app.live.notifications.latest", result=result, lines=lines)


document_app = typer.Typer(
    name="document",
    help=tr(
        "cli.app.live.notifications.document.app_help",
        default="Fetch and read back the document AEAT served behind one notification.",
    ),
    no_args_is_help=True,
    add_completion=False,
)
notifications_app.add_typer(document_app, name="document")


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


def _document_payload_fields(bucket_id: str, record: NotificationDocumentRecord) -> dict[str, object]:
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
                "anything about what it says."
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


@document_app.command(
    "pull",
    help=tr(
        "cli.app.live.notifications.document.pull_help",
        default="Fetch one already-read notification's document into encrypted custody.",
    ),
)
def notifications_document_pull(
    ctx: typer.Context,
    certificado_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.live.notifications.document.certificado_id_help",
                default="AEAT numero de certificado of the notification.",
            ),
        ),
    ],
) -> None:
    """Fetch and take custody of one already-read notification's document.

    The row is resolved from the bucket's own captured notification snapshots
    so the comparecencia guard keys on what AEAT reported, never on anything a
    caller supplied. A notification AEAT does not already report as read is
    refused before any request crosses the wire.
    """
    bucket_id = _bucket_id()
    run_auth_preflight(_auth_preflight, family="notifications")
    custody = asyncio.run(pull_notification_document(bucket_id=bucket_id, certificado_id=certificado_id))
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
    _emit_envelope(
        ctx,
        command="app.live.notifications.document.pull",
        result=result,
        lines=lines,
        notices=notices,
    )


@document_app.command(
    "view",
    help=tr(
        "cli.app.live.notifications.document.view_help",
        default="Show one stored notification document and its reading, without contacting AEAT.",
    ),
)
def notifications_document_view(
    ctx: typer.Context,
    certificado_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.live.notifications.document.certificado_id_help",
                default="AEAT numero de certificado of the notification.",
            ),
        ),
    ],
) -> None:
    """Read back one stored notification document from bucket-local custody.

    Nothing here authenticates, navigates or fetches: the record and its
    reading come from the encrypted secure-object store, so this verb cannot be
    the act that serves a notification. It runs with no AEAT session at all.
    """
    bucket_id = _bucket_id()
    record = NotificationDocumentService().show(bucket_id=bucket_id, certificado_id=certificado_id)
    result = NotificationDocumentViewResult(**_document_payload_fields(bucket_id, record))
    notices = _document_notices(record, notices=())
    lines = [*_document_lines(bucket_id, record), *notice_lines(notices)]
    _emit_envelope(
        ctx,
        command="app.live.notifications.document.view",
        result=result,
        lines=lines,
        notices=notices,
    )
