"""Ledger lifecycle and transaction-structure CLI commands.

Use of :class:`OutputSchema`, :class:`TransactionCatalogueRepository` for compliance.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Protocol

import typer
from pydantic import ValidationError

from ...application.ledger import (
    SplitChildCommand,
    archive_manual_transaction,
    attach_manual_transaction_evidence,
    ledger_transaction_payload,
    ledger_transaction_review_status,
    list_manual_transactions,
    merge_transactions,
    remove_manual_transaction,
    reset_ledger_catalogue,
    resolve_transaction_id,
    restore_manual_transaction,
    split_transaction,
    stash_manual_transaction,
)
from ...core import resolve_active_bucket_id
from ...core.i18n import tr
from ...core.time import now
from ...domain.attachments import DocumentLinkSource
from ...domain.transactions import (
    Transaction,
    TransactionCatalogueRepository,
    TransactionIdPrefixError,
)
from ._common import _bad, _emit_envelope, _state, _tx_repo
from ._schemas import OutputSchema


class _TransactionRepo(Protocol):
    @property
    def bucket_id(self) -> str: ...


def register_lifecycle_commands(app: typer.Typer) -> None:
    """Register ledger lifecycle and structure mutation commands."""
    app.command("attach", help=tr("cli.ledger.attach.help"))(ledger_attach)
    app.command(
        "doclink",
        help=tr(
            "cli.ledger.doclink.help",
            default="Record a Gmail/Drive/URL document link on a ledger row (never fetched).",
        ),
    )(ledger_doclink)
    app.command("archive", help=tr("cli.ledger.archive.help"))(ledger_archive)
    app.command("stash", help=tr("cli.ledger.stash.help"))(ledger_stash)
    app.command("restore", help=tr("cli.ledger.restore.help"))(ledger_restore)
    app.command("remove", help=tr("cli.ledger.remove.help"))(ledger_remove)
    app.command("reset", help=tr("cli.ledger.reset.help"))(ledger_reset)
    app.command("split", help=tr("cli.ledger.split.help"))(ledger_split)
    app.command("merge", help=tr("cli.ledger.merge.help"))(ledger_merge)


def _parse_required_decimal(raw: str, *, label: str) -> Decimal:
    try:
        return Decimal(raw.strip())
    except (InvalidOperation, ValueError) as exc:
        raise _bad(tr("cli.ledger.errors.invalid_decimal", label=label, raw=raw)) from exc


def _bucket_transaction_ids(transaction_repository: _TransactionRepo) -> tuple[str, ...]:
    bucket_id = transaction_repository.bucket_id
    results = list_manual_transactions(
        bucket_id=bucket_id,
        transaction_repository=transaction_repository
        if isinstance(transaction_repository, TransactionCatalogueRepository)
        else None,
    )
    return tuple(result.transaction.transaction_id for result in results)


def _resolve_id(transaction_repository: _TransactionRepo, prefix: str) -> str:
    try:
        return resolve_transaction_id(prefix, _bucket_transaction_ids(transaction_repository))
    except TransactionIdPrefixError as exc:
        raw_message = str(exc)
        if "is empty" in raw_message:
            raise _bad(tr("cli.ledger.errors.id_prefix_empty")) from exc
        if "non-hex" in raw_message:
            raise _bad(tr("cli.ledger.errors.id_prefix_not_hex", prefix=prefix)) from exc
        if "longer than" in raw_message:
            raise _bad(tr("cli.ledger.errors.id_prefix_too_long", prefix=prefix)) from exc
        if "no transaction" in raw_message:
            raise _bad(tr("cli.ledger.errors.id_prefix_not_found", prefix=prefix)) from exc
        if "matches" in raw_message:
            _, _, candidates = raw_message.partition(":")
            raise _bad(
                tr(
                    "cli.ledger.errors.id_prefix_collision",
                    prefix=prefix,
                    candidates=candidates.strip() or "?",
                )
            ) from exc
        raise _bad(tr("cli.ledger.errors.id_prefix_unknown", message=raw_message)) from exc


def _ledger_validation_bad(error: ValidationError) -> typer.BadParameter:
    item = error.errors()[0] if error.errors() else {}
    location = ".".join(str(part) for part in item.get("loc", ()) if part is not None) or "ledger"
    message = str(item.get("msg") or error)
    return _bad(f"{location}: {message}")


def _emit_update_result(
    ctx: typer.Context,
    result_transaction: Transaction,
    bucket_id: str,
    events: tuple[str, ...],
    *,
    command: str,
    result_cls: type[OutputSchema],
) -> None:
    transaction_payload = ledger_transaction_payload(result_transaction)
    review_status = ledger_transaction_review_status(result_transaction)
    result = result_cls.model_validate(
        {
            "bucket_id": bucket_id,
            "transaction_id": result_transaction.transaction_id,
            "bucket_event_ids": list(events),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        }
    )
    _emit_envelope(
        ctx,
        command=command,
        result=result,
        lines=[
            f"{tr('cli.ledger.labels.id')}\t{result_transaction.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction_payload.date}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction_payload.amount}",
            f"{tr('cli.ledger.labels.description')}\t{transaction_payload.description}",
            f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
        ],
    )


def ledger_attach(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.attach.id_help")),
    purchase_invoice_evidence_id: str | None = typer.Option(
        None,
        "--purchase-invoice-evidence-id",
        help=tr("cli.ledger.attach.purchase_invoice_evidence_help"),
    ),
    attachment_ids: list[str] = typer.Option(
        [],
        "--attachment-id",
        help=tr("cli.ledger.attach.attachment_help"),
    ),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.attach.actor_help")),
) -> None:
    """Attach existing secure evidence objects to one ledger transaction."""
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = attach_manual_transaction_evidence(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        purchase_invoice_evidence_id=purchase_invoice_evidence_id,
        attachment_ids=tuple(attachment_ids),
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger attach",
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerAttachResult

    _emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.attach",
        result_cls=LedgerAttachResult,
    )


def ledger_doclink(
    ctx: typer.Context,
    transaction_id: str = typer.Option(
        ...,
        "--id",
        help=tr("cli.ledger.doclink.id_help", default="Ledger transaction id."),
    ),
    source: DocumentLinkSource = typer.Option(
        ..., "--source", help=tr("cli.ledger.doclink.source_help", default="Link source: gmail, google_drive, or url.")
    ),
    reference: str = typer.Option(
        ..., "--reference", help=tr("cli.ledger.doclink.reference_help", default="The document link reference.")
    ),
    note: str = typer.Option("", "--note", help=tr("cli.ledger.doclink.note_help", default="Optional note.")),
    actor: str | None = typer.Option(
        None,
        "--actor",
        help=tr("cli.ledger.doclink.actor_help", default="Operator label."),
    ),
) -> None:
    """Record a Gmail/Drive/URL document link as local evidence on a ledger row."""
    from ...adapters.persistence.storage.attachment import AttachmentStore
    from ...domain.attachments import AttachmentKind
    from ...domain.attachments._service import add_link_attachment

    # The advertised --source choice set (DocumentLinkSource) is exactly the
    # three link sources this map covers, so the click Choice gate rejects any
    # other value with an instructive accepted-set message before the handler
    # runs; this mapping is therefore total over the option's domain.
    kind_by_source = {
        DocumentLinkSource.GMAIL: AttachmentKind.EMAIL_MESSAGE,
        DocumentLinkSource.GOOGLE_DRIVE: AttachmentKind.DRIVE_DOCUMENT,
        DocumentLinkSource.URL: AttachmentKind.OTHER,
    }
    kind = kind_by_source[source]
    attachment_source = source.to_attachment_source()
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    store = AttachmentStore()
    attachment = add_link_attachment(
        store,
        kind=kind,
        source=attachment_source,
        source_reference=reference,
        captured_at=now(),
        bucket_id=transaction_repository.bucket_id,
        link_transaction_ids=(resolved_id,),
        notes=note,
    )
    result = attach_manual_transaction_evidence(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        attachment_ids=(attachment.attachment_id,),
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger doclink",
        transaction_repository=transaction_repository,
        attachment_store=store,
    )
    from ._ledger_payloads import LedgerAttachResult

    _emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.doclink",
        result_cls=LedgerAttachResult,
    )


def ledger_archive(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.archive.id_help")),
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.archive.reason_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.archive.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.archive.actor_help")),
) -> None:
    """Archive one ledger transaction through the bucket-scoped backend."""
    if not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = archive_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        source_command="aeat app ledger archive",
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerArchiveResult

    _emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.archive",
        result_cls=LedgerArchiveResult,
    )


def ledger_stash(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.stash.id_help")),
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.stash.reason_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.stash.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.stash.actor_help")),
) -> None:
    """Stash one ledger transaction through the bucket-scoped backend."""
    if not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = stash_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        source_command="aeat app ledger stash",
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerStashResult

    _emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.stash",
        result_cls=LedgerStashResult,
    )


def ledger_restore(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.restore.id_help")),
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.restore.reason_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.restore.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.restore.actor_help")),
) -> None:
    """Restore one stashed or archived ledger transaction to active."""
    if not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    result = restore_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        source_command="aeat app ledger restore",
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerRestoreResult

    _emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.restore",
        result_cls=LedgerRestoreResult,
    )


def ledger_remove(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.remove.id_help")),
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.remove.reason_help")),
    dry_run: bool = typer.Option(False, "--dry-run", help=tr("cli.ledger.remove.dry_run_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.remove.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.remove.actor_help")),
) -> None:
    """Remove one ledger transaction through the bucket-scoped backend."""
    if not dry_run and not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    report = remove_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        dry_run=dry_run,
        source_command="aeat app ledger remove",
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerRemoveResult

    _emit_envelope(
        ctx,
        command="ledger.remove",
        result=LedgerRemoveResult.model_validate(report.model_dump(mode="json")),
        lines=[
            f"{tr('cli.ledger.labels.bucket')}\t{report.bucket_id}",
            f"{tr('cli.ledger.labels.id')}\t{report.transaction_id}",
            f"{tr('cli.ledger.labels.removed')}\t{report.removed}",
            f"{tr('cli.ledger.labels.dry_run')}\t{report.dry_run}",
        ],
    )


def ledger_reset(
    ctx: typer.Context,
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.reset.reason_help")),
    dry_run: bool = typer.Option(False, "--dry-run", help=tr("cli.ledger.reset.dry_run_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.reset.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.reset.actor_help")),
) -> None:
    """Reset the active bucket ledger catalogue through the backend."""
    if not dry_run and not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))
    state = _state()
    transaction_repository = _tx_repo(state)
    report = reset_ledger_catalogue(
        bucket_id=transaction_repository.bucket_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        dry_run=dry_run,
        source_command="aeat app ledger reset",
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerResetResult

    _emit_envelope(
        ctx,
        command="ledger.reset",
        result=LedgerResetResult.model_validate(report.model_dump(mode="json")),
        lines=[
            f"{tr('cli.ledger.labels.bucket')}\t{report.bucket_id}",
            f"{tr('cli.ledger.labels.rows')}\t{len(report.removed_transaction_ids)}",
            f"{tr('cli.ledger.labels.reset')}\t{report.reset}",
            f"{tr('cli.ledger.labels.dry_run')}\t{report.dry_run}",
        ],
    )


def ledger_split(
    ctx: typer.Context,
    transaction_id: str = typer.Option(..., "--id", help=tr("cli.ledger.split.id_help")),
    child_amount: list[str] = typer.Option([], "--child-amount", help=tr("cli.ledger.split.child_amount_help")),
    child_description: list[str] = typer.Option(
        [],
        "--child-description",
        help=tr("cli.ledger.split.child_description_help"),
    ),
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.split.reason_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.split.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.split.actor_help")),
) -> None:
    """Redistribute one parent transaction into N child transactions."""
    if not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))
    if len(child_amount) != len(child_description):
        raise _bad(tr("cli.ledger.split.errors.child_args_mismatch"))
    if len(child_amount) < 2:
        raise _bad(tr("cli.ledger.split.errors.min_two_children"))
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    try:
        children = tuple(
            SplitChildCommand(
                amount=_parse_required_decimal(amount_raw, label="child-amount"),
                description=description_raw,
            )
            for amount_raw, description_raw in zip(child_amount, child_description, strict=True)
        )
        result = split_transaction(
            bucket_id=transaction_repository.bucket_id,
            transaction_id=resolved_id,
            children=children,
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger split",
            reason=reason,
            transaction_repository=transaction_repository,
        )
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    from ._ledger_payloads import LedgerSplitResult

    _emit_envelope(
        ctx,
        command="ledger.split",
        result=LedgerSplitResult.model_validate(
            {
                "bucket_id": result.bucket_id,
                "parent_transaction_id": result.parent_transaction_id,
                "split_group_id": result.split_group_id,
                "child_transaction_ids": list(result.child_transaction_ids),
                "bucket_event_id": result.bucket_event_id,
            }
        ),
        lines=[
            f"{tr('cli.ledger.labels.bucket')}\t{result.bucket_id}",
            f"{tr('cli.ledger.labels.parent_id')}\t{result.parent_transaction_id}",
            f"{tr('cli.ledger.labels.split_group_id')}\t{result.split_group_id}",
            f"{tr('cli.ledger.labels.children')}\t{len(result.child_transaction_ids)}",
            f"{tr('cli.ledger.labels.event_id')}\t{result.bucket_event_id}",
        ],
    )


def ledger_merge(
    ctx: typer.Context,
    child_id: list[str] = typer.Option([], "--child-id", help=tr("cli.ledger.merge.child_id_help")),
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.merge.reason_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.merge.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.merge.actor_help")),
) -> None:
    """Re-merge a complete cohort of split children into a fresh transaction."""
    if not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))
    if len(child_id) < 2:
        raise _bad(tr("cli.ledger.merge.errors.min_two_children"))
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_ids = tuple(_resolve_id(transaction_repository, raw) for raw in child_id)
    result = merge_transactions(
        bucket_id=transaction_repository.bucket_id,
        child_transaction_ids=resolved_ids,
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger merge",
        reason=reason,
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerMergeResult

    _emit_envelope(
        ctx,
        command="ledger.merge",
        result=LedgerMergeResult.model_validate(
            {
                "bucket_id": result.bucket_id,
                "split_group_id": result.split_group_id,
                "parent_transaction_id": result.parent_transaction_id,
                "merged_transaction_id": result.merged_transaction_id,
                "source_child_ids": list(result.source_child_ids),
                "bucket_event_id": result.bucket_event_id,
            }
        ),
        lines=[
            f"{tr('cli.ledger.labels.bucket')}\t{result.bucket_id}",
            f"{tr('cli.ledger.labels.split_group_id')}\t{result.split_group_id}",
            f"{tr('cli.ledger.labels.parent_id')}\t{result.parent_transaction_id}",
            f"{tr('cli.ledger.labels.merged_id')}\t{result.merged_transaction_id}",
            f"{tr('cli.ledger.labels.children')}\t{len(result.source_child_ids)}",
            f"{tr('cli.ledger.labels.event_id')}\t{result.bucket_event_id}",
        ],
    )


__all__ = [
    "ledger_archive",
    "ledger_attach",
    "ledger_doclink",
    "ledger_merge",
    "ledger_remove",
    "ledger_reset",
    "ledger_restore",
    "ledger_split",
    "ledger_stash",
    "register_lifecycle_commands",
]
