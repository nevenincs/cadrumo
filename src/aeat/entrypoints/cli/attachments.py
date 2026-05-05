"""``aeat attachments`` command group for the content-addressed attachment service.

Wraps :mod:`aeat.application.attachments` so operators can ingest a
local file (``add``), enumerate stored manifests (``list``), and
inspect a single manifest (``show``). Storage routes through
:class:`aeat.domain.attachments.AttachmentStore` rooted at
``AEAT_ATTACHMENTS_DIR``. All user-facing strings flow through the
multilingual helpers in :mod:`aeat.entrypoints.cli._i18n`.
"""

from __future__ import annotations

import mimetypes
from datetime import UTC, datetime
from pathlib import Path

import typer

from ...application.attachments import (
    add_attachment,
    list_attachments,
    load_attachment,
)
from ...core.config import load_settings
from ...domain.attachments import (
    Attachment,
    AttachmentError,
    AttachmentKind,
    AttachmentSource,
    AttachmentStore,
)
from ._i18n import tr

_DEFAULT_MIME_TYPE = "application/octet-stream"

app = typer.Typer(
    name="attachments",
    no_args_is_help=True,
    help=tr("cli.attachments.app_help"),
)


@app.command(name="add", help=tr("cli.attachments.add_help"))
def add_cmd(
    path: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, help=tr("cli.attachments.add_path_help")
    ),
    kind: AttachmentKind = typer.Option(
        AttachmentKind.OTHER,
        "--kind",
        case_sensitive=False,
        help=tr("cli.attachments.add_kind_help"),
    ),
    source: AttachmentSource = typer.Option(
        AttachmentSource.LOCAL_FILE,
        "--source",
        case_sensitive=False,
        help=tr("cli.attachments.add_source_help"),
    ),
    source_reference: str | None = typer.Option(
        None,
        "--source-reference",
        help=tr("cli.attachments.add_source_ref_help"),
    ),
    mime_type: str | None = typer.Option(
        None,
        "--mime-type",
        help=tr("cli.attachments.add_mime_type_help"),
    ),
    link_transaction_ids: list[str] | None = typer.Option(
        None,
        "--link-tx",
        help=tr("cli.attachments.add_link_tx_help"),
    ),
    link_invoice_ids: list[str] | None = typer.Option(
        None,
        "--link-invoice",
        help=tr("cli.attachments.add_link_invoice_help"),
    ),
    metadata_items: list[str] | None = typer.Option(
        None,
        "--metadata",
        help=tr("cli.attachments.add_metadata_help"),
    ),
    notes: str = typer.Option(
        "",
        "--notes",
        help=tr("cli.attachments.add_notes_help"),
    ),
) -> None:
    """Ingest ``path`` and print the persisted attachment manifest as JSON.

    Resolves ``path`` to an absolute filesystem location, infers the
    MIME type via :func:`_guess_mime_type` when not supplied, parses
    ``--metadata`` items via :func:`_parse_metadata`, and delegates the
    write to :func:`aeat.application.attachments.add_attachment`.

    Args:
        path: Local file to ingest.
        kind: :class:`aeat.domain.attachments.AttachmentKind` label.
        source: :class:`aeat.domain.attachments.AttachmentSource` channel.
        source_reference: Provenance pointer; defaults to the absolute
            source path.
        mime_type: MIME-type override; defaults to a best-effort guess.
        link_transaction_ids: Repeatable transaction IDs to link.
        link_invoice_ids: Repeatable invoice IDs to link.
        metadata_items: Repeatable ``key=value`` provider metadata.
        notes: Optional human-readable notes.

    Raises:
        :exc:`typer.Exit`: With code 2 on validation failures or
            attachment-store errors.
    """
    store = _store()
    resolved_path = path.resolve()
    resolved_reference = (source_reference or str(resolved_path)).strip()
    if not resolved_reference:
        typer.echo(
            tr("cli.attachments.errors.empty_source_reference"),
            err=True,
        )
        raise typer.Exit(code=2)
    resolved_mime = (mime_type or _guess_mime_type(resolved_path)).strip()
    if not resolved_mime:
        typer.echo(
            tr("cli.attachments.errors.empty_mime_type"),
            err=True,
        )
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


@app.command(name="list", help=tr("cli.attachments.list_help"))
def list_cmd(
    linked_to: str | None = typer.Option(
        None,
        "--linked-to",
        help=tr("cli.attachments.list_linked_to_help"),
    ),
    kind: AttachmentKind | None = typer.Option(
        None,
        "--kind",
        case_sensitive=False,
        help=tr("cli.attachments.list_kind_filter_help"),
    ),
) -> None:
    """List attachments from the configured store as a tab-separated table.

    Delegates to :func:`aeat.application.attachments.list_attachments`
    and renders one row per attachment ordered by ``captured_at`` and
    then by ``attachment_id``. When the listing is empty a localised
    "no attachments found" message is emitted instead.

    Args:
        linked_to: Optional transaction or invoice identifier to filter
            on.
        kind: Optional :class:`aeat.domain.attachments.AttachmentKind`
            to filter on.

    Raises:
        :exc:`typer.Exit`: With code 2 on attachment-store errors.
    """
    store = _store()
    try:
        attachments = list_attachments(store, linked_to=linked_to, kind=kind)
    except AttachmentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    if not attachments:
        typer.echo(tr("cli.attachments.list.no_attachments"))
        return
    typer.echo(tr("cli.attachments.list_header"))
    for attachment in sorted(attachments, key=lambda item: (item.captured_at, item.attachment_id)):
        typer.echo(_format_attachment_row(attachment))


@app.command(name="show", help=tr("cli.attachments.show_help"))
def show_cmd(
    attachment_id: str = typer.Argument(..., help=tr("cli.attachments.show_id_help")),
) -> None:
    """Show one attachment manifest from the configured store as JSON.

    Args:
        attachment_id: Stable SHA-256 hex digest identifying the
            attachment in
            :class:`aeat.domain.attachments.AttachmentStore`.

    Raises:
        :exc:`typer.Exit`: With code 2 when the attachment cannot be
            loaded.
    """
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
    """Guess the MIME type for ``path`` with a safe binary fallback.

    Falls back to :data:`_DEFAULT_MIME_TYPE` when
    :func:`mimetypes.guess_type` cannot recognise the extension.
    """
    guessed, _encoding = mimetypes.guess_type(path.name)
    return guessed or _DEFAULT_MIME_TYPE


def _parse_metadata(items: list[str]) -> dict[str, str]:
    """Parse ``--metadata key=value`` pairs with strict validation.

    Rules:

    - Each item must contain at least one ``=`` separator.
    - The key is the substring before the first ``=``, trimmed, and
      non-empty.
    - The value is the substring after the first ``=``, preserved
      verbatim.
    - Duplicate keys within one invocation exit with code 2.

    Args:
        items: Raw ``key=value`` strings collected from the CLI.

    Returns:
        Mapping of validated keys to their values.

    Raises:
        :exc:`typer.Exit`: With code 2 when validation fails.
    """
    parsed: dict[str, str] = {}
    for raw in items:
        if "=" not in raw:
            typer.echo(
                tr("cli.attachments.errors.invalid_metadata_format", raw=raw),
                err=True,
            )
            raise typer.Exit(code=2)
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            typer.echo(
                tr("cli.attachments.errors.empty_metadata_key", raw=raw),
                err=True,
            )
            raise typer.Exit(code=2)
        if not value:
            typer.echo(
                tr("cli.attachments.errors.empty_metadata_value", raw=raw),
                err=True,
            )
            raise typer.Exit(code=2)
        if key in parsed:
            typer.echo(
                tr("cli.attachments.errors.duplicate_metadata_key", key=key),
                err=True,
            )
            raise typer.Exit(code=2)
        parsed[key] = value
    return parsed


def _format_attachment_row(attachment: Attachment) -> str:
    """Format one :class:`aeat.domain.attachments.Attachment` as a TSV row."""
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
