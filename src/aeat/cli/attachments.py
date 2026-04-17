"""`aeat attachments` command group for the content-addressed attachment service."""

from __future__ import annotations

import mimetypes
from datetime import UTC, datetime
from pathlib import Path

import typer

from ..config import load_settings
from ..financial.attachments import (
    Attachment,
    AttachmentError,
    AttachmentKind,
    AttachmentSource,
    AttachmentStore,
    add_attachment,
    list_attachments,
    load_attachment,
)

_DEFAULT_MIME_TYPE = "application/octet-stream"

app = typer.Typer(
    name="attachments",
    no_args_is_help=True,
    help="Content-addressed attachment service (#76).",
)


@app.command(name="add", help="Ingest a file into the content-addressed attachment store.")
def add_cmd(
    path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True, help="Path to the source file."),
    kind: AttachmentKind = typer.Option(
        AttachmentKind.OTHER,
        "--kind",
        case_sensitive=False,
        help="Attachment kind enumeration label.",
    ),
    source: AttachmentSource = typer.Option(
        AttachmentSource.LOCAL_FILE,
        "--source",
        case_sensitive=False,
        help="Attachment source channel.",
    ),
    source_reference: str | None = typer.Option(
        None,
        "--source-reference",
        help="Provenance pointer (defaults to the absolute source path).",
    ),
    mime_type: str | None = typer.Option(
        None,
        "--mime-type",
        help="MIME type override (defaults to a guess from the path extension).",
    ),
    link_transaction_ids: list[str] | None = typer.Option(
        None,
        "--link-tx",
        help="Transaction identifier to link (repeatable).",
    ),
    link_invoice_ids: list[str] | None = typer.Option(
        None,
        "--link-invoice",
        help="Invoice identifier to link (repeatable).",
    ),
    metadata_items: list[str] | None = typer.Option(
        None,
        "--metadata",
        help="Free-form provider metadata as key=value (repeatable; string values only).",
    ),
    notes: str = typer.Option(
        "",
        "--notes",
        help="Optional human-readable notes.",
    ),
) -> None:
    """Ingest ``path`` and print the persisted manifest as JSON."""
    store = _store()
    resolved_path = path.resolve()
    resolved_reference = (source_reference or str(resolved_path)).strip()
    if not resolved_reference:
        typer.echo("--source-reference must not be blank", err=True)
        raise typer.Exit(code=2)
    resolved_mime = (mime_type or _guess_mime_type(resolved_path)).strip()
    if not resolved_mime:
        typer.echo("--mime-type must not be blank", err=True)
        raise typer.Exit(code=2)
    metadata = _parse_metadata(metadata_items or [])
    try:
        attachment = add_attachment(
            store,
            path=resolved_path,
            kind=kind,
            source=source,
            source_reference=resolved_reference,
            mime_type=resolved_mime,
            captured_at=datetime.now(UTC),
            link_transaction_ids=tuple(link_transaction_ids or ()),
            link_invoice_ids=tuple(link_invoice_ids or ()),
            metadata=metadata,
            notes=notes,
        )
    except AttachmentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(attachment.model_dump_json(indent=2))


@app.command(name="list", help="List stored attachments, optionally filtered by linkage or kind.")
def list_cmd(
    linked_to: str | None = typer.Option(
        None,
        "--linked-to",
        help="Only show attachments linked to this transaction or invoice identifier.",
    ),
    kind: AttachmentKind | None = typer.Option(
        None,
        "--kind",
        case_sensitive=False,
        help="Only show attachments matching this kind.",
    ),
) -> None:
    """List attachments from the configured store."""
    store = _store()
    try:
        attachments = list_attachments(store, linked_to=linked_to, kind=kind)
    except AttachmentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    if not attachments:
        typer.echo("No attachments found.")
        return
    typer.echo("attachment_id\tkind\tsource\tmime_type\tbytes_size\tcaptured_at\tlinked_tx\tlinked_invoices")
    for attachment in sorted(attachments, key=lambda item: (item.captured_at, item.attachment_id)):
        typer.echo(_format_attachment_row(attachment))


@app.command(name="show", help="Show one stored attachment manifest as JSON.")
def show_cmd(
    attachment_id: str = typer.Argument(..., help="Stable attachment identifier (SHA-256 hex digest)."),
) -> None:
    """Show one attachment manifest from the configured store."""
    store = _store()
    try:
        attachment = load_attachment(store, attachment_id)
    except AttachmentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(attachment.model_dump_json(indent=2))


def _store() -> AttachmentStore:
    """Return the configured attachment store rooted in ``AEAT_ATTACHMENTS_DIR``."""
    return AttachmentStore.at(load_settings().aeat_attachments_dir)


def _guess_mime_type(path: Path) -> str:
    """Guess the MIME type for ``path`` with a safe binary fallback."""
    guessed, _encoding = mimetypes.guess_type(path.name)
    return guessed or _DEFAULT_MIME_TYPE


def _parse_metadata(items: list[str]) -> dict[str, str]:
    """Parse ``--metadata key=value`` pairs with strict validation.

    Rules:
    - Each item must contain at least one ``=`` separator.
    - The key is the substring before the first ``=``, trimmed, non-empty.
    - The value is the substring after the first ``=``, preserved verbatim.
    - Duplicate keys within one invocation exit with code 2.
    """
    parsed: dict[str, str] = {}
    for raw in items:
        if "=" not in raw:
            typer.echo(f"--metadata entry must be key=value: {raw!r}", err=True)
            raise typer.Exit(code=2)
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            typer.echo(f"--metadata key must not be blank: {raw!r}", err=True)
            raise typer.Exit(code=2)
        if not value:
            typer.echo(f"--metadata value must not be blank: {raw!r}", err=True)
            raise typer.Exit(code=2)
        if key in parsed:
            typer.echo(f"--metadata key repeated: {key!r}", err=True)
            raise typer.Exit(code=2)
        parsed[key] = value
    return parsed


def _format_attachment_row(attachment: Attachment) -> str:
    """Format one attachment row for the ``list`` command output."""
    return "\t".join(
        [
            attachment.attachment_id,
            attachment.kind.value,
            attachment.source.value,
            attachment.mime_type,
            str(attachment.bytes_size),
            attachment.captured_at.isoformat(),
            ",".join(attachment.linked_transaction_ids) or "-",
            ",".join(attachment.linked_invoice_ids) or "-",
        ]
    )
