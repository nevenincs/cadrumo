"""Ledger lifecycle and transaction-structure CLI commands.

Lifecycle commands resolve transactions through the shared repository helpers
and emit typed :class:`OutputSchema` mutation envelopes for every structural
change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from pydantic import ValidationError

from ...application.ledger import (
    LLMProvider,
    PurchaseInvoiceEvidenceInputError,
    SplitChildCommand,
    apply_evidence_split,
    archive_manual_transaction,
    attach_manual_transaction_evidence,
    compute_display_id_width,
    is_llm_provider_available,
    ledger_transaction_payload,
    ledger_transaction_review_status,
    merge_transactions,
    remove_manual_transaction,
    reset_ledger_catalogue,
    restore_manual_transaction,
    split_transaction,
    stash_manual_transaction,
    suggest_evidence_split,
)
from ...core import resolve_active_bucket_id
from ...core.external_constants import PDF_MIME_TYPE
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.time import now
from ...domain.attachments import DocumentLinkSource
from ...domain.transactions import (
    BusinessClassification,
    LLMClassifierError,
    Transaction,
    TransactionValidationError,
    is_classified,
)
from ._common import _bad, _emit_envelope, _state, _tx_repo, parse_decimal_amount
from ._ledger_support import _resolve_id
from ._schemas import OutputSchema

if TYPE_CHECKING:
    from ._ledger_payloads import LedgerSplitChildIdPayload


def register_lifecycle_commands(app: typer.Typer) -> None:
    """Register ledger lifecycle and structure mutation commands."""
    app.command("attach", help=tr("cli.ledger.attach.help"))(ledger_attach)
    app.command(
        "doclink",
        help=tr(
            "cli.ledger.doclink.help",
            default="Fetch a Drive document link and store its bytes as encrypted evidence on a ledger row.",
        ),
    )(ledger_doclink)
    app.command("archive", help=tr("cli.ledger.archive.help"))(ledger_archive)
    app.command("stash", help=tr("cli.ledger.stash.help"))(ledger_stash)
    app.command("restore", help=tr("cli.ledger.restore.help"))(ledger_restore)
    app.command("remove", help=tr("cli.ledger.remove.help"))(ledger_remove)
    app.command("reset", help=tr("cli.ledger.reset.help"))(ledger_reset)
    app.command("split", help=tr("cli.ledger.split.help"))(ledger_split)
    app.command("merge", help=tr("cli.ledger.merge.help"))(ledger_merge)


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
        },
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
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.attach.id_help")),
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


def _sniff_document_mime_type(reference: str, data: bytes) -> str:
    """Best-effort MIME type for fetched evidence bytes.

    Sniffs the magic bytes for the document kinds operators attach (PDF,
    PNG, JPEG), then falls back to a filename guess from the reference, then
    to ``application/octet-stream``. The bytes are always stored regardless
    of the guessed type; the type is provenance metadata, never a gate.
    """
    import mimetypes

    if data.startswith(b"%PDF-"):
        return PDF_MIME_TYPE
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    guessed, _ = mimetypes.guess_type(reference)
    return guessed or "application/octet-stream"


def ledger_doclink(
    ctx: typer.Context,
    transaction_id: str = typer.Argument(
        ...,
        help=tr("cli.ledger.doclink.id_help", default="Ledger transaction id."),
    ),
    source: DocumentLinkSource = typer.Option(
        ...,
        "--source",
        help=tr("cli.ledger.doclink.source_help", default="Link source: gmail, google_drive, or url."),
    ),
    reference: str = typer.Option(
        ...,
        "--reference",
        help=tr("cli.ledger.doclink.reference_help", default="The document link reference."),
    ),
    note: str = typer.Option("", "--note", help=tr("cli.ledger.doclink.note_help", default="Optional note.")),
    actor: str | None = typer.Option(
        None,
        "--actor",
        help=tr("cli.ledger.doclink.actor_help", default="Operator label."),
    ),
) -> None:
    """Fetch a document link and store its bytes as encrypted evidence on a ledger row.

    The reference is resolved through
    :func:`aeat.adapters.outbound.google.resolve_document_link`, which fetches
    Drive files reachable under the granted ``drive.file`` scope. The fetched
    bytes are stored through the byte-bearing
    :func:`aeat.domain.attachments.add_attachment_bytes` path (real ``sha256``
    and ``mime_type``), and the original link is kept as manifest provenance.
    Gmail links, arbitrary URLs, and out-of-scope Drive files are **refused** —
    a link is never stored as evidence.
    """
    from ...adapters.outbound.google import resolve_document_link
    from ...adapters.outbound.google._active_profile import resolve_active_profile
    from ...adapters.outbound.storage import OutboundStorageError
    from ...adapters.outbound.storage._factory import _build_google_credentials
    from ...adapters.persistence.storage.attachment import AttachmentStore
    from ...domain.attachments import AttachmentKind, add_attachment_bytes

    attachment_source = source.to_attachment_source()
    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)

    profile = resolve_active_profile()
    try:
        credentials = _build_google_credentials(profile=profile)
        data = resolve_document_link(
            source=attachment_source,
            reference=reference,
            credentials=credentials,
        )
    except OutboundStorageError as exc:
        required_scope = ""
        if exc.context is not None:
            required_scope = str(exc.context.get("required_scope", ""))
        scope_hint = f" (requires the {required_scope} scope)" if required_scope else ""
        raise _bad(
            tr(
                "cli.ledger.doclink.refused",
                source=attachment_source.value,
                reference=reference,
                scope_hint=scope_hint,
                default=(
                    f"Cannot fetch the {attachment_source.value} document for {reference!r}"
                    f"{scope_hint}: evidence must carry the document's encrypted bytes, and a "
                    "link is never stored on its own. Download the document and attach it with "
                    "'aeat app ledger attach --attachment-id ...', or grant the required Google "
                    "scope and retry."
                ),
            ),
        ) from exc

    store = AttachmentStore()
    attachment = add_attachment_bytes(
        store,
        data=data,
        kind=AttachmentKind.DRIVE_DOCUMENT,
        source=attachment_source,
        source_reference=reference,
        mime_type=_sniff_document_mime_type(reference, data),
        captured_at=now(),
        bucket_id=transaction_repository.bucket_id,
        link_transaction_ids=(resolved_id,),
        metadata={"source": attachment_source.value, "source_reference": reference},
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
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.archive.id_help")),
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
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.stash.id_help")),
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
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.restore.id_help")),
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
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.remove.id_help")),
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
    transaction_id: str = typer.Argument(..., help=tr("cli.ledger.split.id_help")),
    child_amount: list[str] = typer.Option([], "--child-amount", help=tr("cli.ledger.split.child_amount_help")),
    child_description: list[str] = typer.Option(
        [],
        "--child-description",
        help=tr("cli.ledger.split.child_description_help"),
    ),
    llm: LLMProvider | None = typer.Option(
        None,
        "--llm",
        help=tr(
            "cli.ledger.split.llm_help",
            default="Propose an evidence-driven N-way split with the given LLM provider.",
        ),
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help=tr(
            "cli.ledger.split.apply_help",
            default="Persist the proposed --llm split (requires --yes); without it the proposal is previewed only.",
        ),
    ),
    read_evidence: bool = typer.Option(
        False,
        "--read-evidence",
        help=tr(
            "cli.ledger.split.read_evidence_help",
            default="Read the transaction's attached invoice on-host and feed it to the --llm split proposer.",
        ),
    ),
    evidence_acknowledged: bool = typer.Option(
        False,
        "--evidence-acknowledged",
        help=tr(
            "cli.ledger.split.evidence_acknowledged_help",
            default="Acknowledge --read-evidence sends the evidence to a cloud model (off by default, gestor-barred).",
        ),
    ),
    vision_model: str | None = typer.Option(
        None,
        "--vision-model",
        help=tr(
            "cli.ledger.split.vision_model_help",
            default="Override the local Ollama vision model for a scanned/image invoice read (e.g. qwen2.5vl:7b).",
        ),
    ),
    reason: str = typer.Option("", "--reason", help=tr("cli.ledger.split.reason_help")),
    yes: bool = typer.Option(False, "--yes", help=tr("cli.ledger.split.yes_help")),
    actor: str | None = typer.Option(None, "--actor", help=tr("cli.ledger.split.actor_help")),
) -> None:
    """Redistribute one parent transaction into N child transactions (manual or --llm)."""
    if llm is not None or read_evidence:
        _ledger_split_llm(
            ctx,
            transaction_id=transaction_id,
            child_amount=child_amount,
            child_description=child_description,
            provider=llm,
            apply=apply,
            read_evidence=read_evidence,
            evidence_acknowledged=evidence_acknowledged,
            vision_model=vision_model,
            reason=reason,
            yes=yes,
            actor=actor,
        )
        return
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
                amount=parse_decimal_amount(amount_raw, label="child-amount"),
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

    child_id_rows = _split_child_id_rows(result.child_transaction_ids)
    notices = _split_classification_dropped_notices(result.parent_transaction.business_classification)
    lines = [
        f"{tr('cli.ledger.labels.bucket')}\t{result.bucket_id}",
        f"{tr('cli.ledger.labels.parent_id')}\t{result.parent_transaction_id}",
        f"{tr('cli.ledger.labels.split_group_id')}\t{result.split_group_id}",
        f"{tr('cli.ledger.labels.children')}\t{len(result.child_transaction_ids)}",
    ]
    lines.extend(
        f"{tr('cli.ledger.labels.child_id')}\t{row.display_id}\t{row.full_id}" for row in child_id_rows
    )
    lines.append(f"{tr('cli.ledger.labels.event_id')}\t{result.bucket_event_id}")
    lines.extend(f"ADVISORY\t{notice.message}" for notice in notices)
    _emit_envelope(
        ctx,
        command="ledger.split",
        result=LedgerSplitResult.model_validate(
            {
                "bucket_id": result.bucket_id,
                "parent_transaction_id": result.parent_transaction_id,
                "split_group_id": result.split_group_id,
                "child_transaction_ids": list(result.child_transaction_ids),
                "child_transactions": [row.model_dump(mode="json") for row in child_id_rows],
                "bucket_event_id": result.bucket_event_id,
            },
        ),
        lines=lines,
        notices=notices or None,
    )


def _split_child_id_rows(child_transaction_ids: tuple[str, ...]) -> list[LedgerSplitChildIdPayload]:
    """Build the typed full + short id rows for the persisted split children.

    ``ledger merge`` requires the full child ids and refuses a partial cohort,
    so a persisted split must surface them (audit M11). The short ``display_id``
    is the shortest unique prefix within the child cohort — the same
    display-width convention the ledger list surface uses — so the operator can
    read or copy either form into ``aeat app ledger merge --child-id ...``.
    """
    from ._ledger_payloads import LedgerSplitChildIdPayload

    width = compute_display_id_width(child_transaction_ids)
    return [
        LedgerSplitChildIdPayload(full_id=child_id, display_id=child_id[:width])
        for child_id in child_transaction_ids
    ]


def _split_classification_dropped_notices(
    parent_classification: BusinessClassification,
) -> list[Notice]:
    """Build the non-blocking advisory when a split drops the parent's classification.

    Split children deliberately default to ``NOT_YET_PROCESSED`` to force
    conscious per-row tax treatment; the parent's classification is not cloned.
    When the parent carried a real classified outcome (BUSINESS / PERSONAL /
    MIXED), that drop is surfaced as an ``info`` :class:`Notice` so it is not
    silent — the operator is told the children need re-classification.
    """
    if not is_classified(parent_classification):
        return []
    return [
        Notice(
            severity=NoticeSeverity.INFO,
            code="ledger.split.classification_dropped",
            message=tr(
                "cli.ledger.split.classification_dropped",
                classification=parent_classification.value,
            ),
            suggestion="aeat app ledger classify",
            context={"parent_classification": parent_classification.value},
        ),
    ]


def _ledger_split_llm(
    ctx: typer.Context,
    *,
    transaction_id: str,
    child_amount: list[str],
    child_description: list[str],
    provider: LLMProvider | None,
    apply: bool,
    read_evidence: bool,
    evidence_acknowledged: bool,
    vision_model: str | None,
    reason: str,
    yes: bool,
    actor: str | None,
) -> None:
    """Run the evidence-driven LLM split suggest / apply loop for ``ledger split --llm``.

    Without ``--apply`` the proposed children (derived amounts, model-selected
    categories, registry-derived IVA) are previewed and nothing is persisted.
    With ``--apply`` (and ``--yes``) the reviewed proposal drives
    :func:`apply_evidence_split`: the single-writer split plus per-child
    classification, registry-derived numbers, parent-invoice evidence link, and
    ``llm:<model>`` provenance. The manual ``--child-amount`` / ``--child-description``
    flags are the explicit operator override and cannot be combined with ``--llm``.
    """
    from ._ledger_payloads import LedgerSplitChildProposalPayload, LedgerSplitResult

    if child_amount or child_description:
        raise _bad(
            tr(
                "cli.ledger.split.llm_exclusive",
                default="--llm cannot be combined with --child-amount/--child-description; "
                "the manual path is the explicit operator override.",
            ),
        )
    if provider is not None and not is_llm_provider_available(provider):
        raise _bad(
            tr(
                "cli.ledger.classify.llm_provider_unavailable",
                provider=provider.value,
                default=(
                    f"LLM provider {provider.value!r} is unavailable: its CLI is not on PATH. "
                    f"Install the {provider.value!r} CLI and ensure it is on PATH, "
                    "or run 'aeat app ledger providers' to list usable providers."
                ),
            ),
        )
    if apply and not yes:
        raise _bad(tr("cli.ledger.errors.confirm_required"))

    state = _state()
    transaction_repository = _tx_repo(state)
    bucket_id = transaction_repository.bucket_id
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    try:
        suggestion = suggest_evidence_split(
            bucket_id=bucket_id,
            transaction_id=resolved_id,
            provider=provider,
            transaction_repository=transaction_repository,
            read_evidence=read_evidence,
            evidence_acknowledged=evidence_acknowledged,
            vision_model=vision_model,
        )
    except PurchaseInvoiceEvidenceInputError as exc:
        raise _bad(str(exc)) from exc
    except LLMClassifierError as exc:
        raise _bad(
            tr("cli.ledger.classify.llm_failed", reason=str(exc), default=f"LLM split proposal failed: {exc}"),
        ) from exc

    proposed_children = [
        LedgerSplitChildProposalPayload.model_validate(
            {
                "proportion": format(child.proportion, "f"),
                "amount": format(child.amount, "f"),
                "description": child.description,
                "category": child.category.value if child.category is not None else None,
                "iva_category": child.iva_category.value if child.iva_category is not None else None,
                "iva_rate": format(child.iva_rate, "f") if child.iva_rate is not None else None,
                "taxable_base": format(child.taxable_base, "f") if child.taxable_base is not None else None,
                "iva_amount": format(child.iva_amount, "f") if child.iva_amount is not None else None,
                "rate_derivable": child.rate_derivable,
            },
        )
        for child in suggestion.children
    ]

    if not apply:
        result = LedgerSplitResult.model_validate(
            {
                "bucket_id": bucket_id,
                "parent_transaction_id": suggestion.transaction_id,
                "llm": True,
                "persisted": False,
                "provider": suggestion.provider.value if suggestion.provider is not None else None,
                "provenance": suggestion.provenance,
                "reason": suggestion.reason,
                "parent_amount": format(suggestion.parent_amount, "f"),
                "proposed_children": [child.model_dump(mode="json") for child in proposed_children],
            },
        )
        lines = [
            f"{tr('cli.ledger.labels.id')}\t{suggestion.transaction_id}",
            f"{tr('cli.ledger.labels.children')}\t{len(proposed_children)}",
        ]
        lines.extend(f"{child.description}\t{child.amount}\t{child.iva_category or ''}" for child in proposed_children)
        lines.append(tr("cli.ledger.classify.llm_review_hint"))
        _emit_envelope(ctx, command="ledger.split", result=result, lines=lines)
        return

    try:
        applied = apply_evidence_split(
            suggestion,
            bucket_id=bucket_id,
            actor=actor or resolve_active_bucket_id() or "operator",
            transaction_repository=transaction_repository,
        )
    except TransactionValidationError as exc:
        raise _bad(str(exc)) from exc
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc

    child_id_rows = _split_child_id_rows(applied.child_transaction_ids)
    result = LedgerSplitResult.model_validate(
        {
            "bucket_id": applied.bucket_id,
            "parent_transaction_id": applied.parent_transaction_id,
            "split_group_id": applied.split_group_id,
            "child_transaction_ids": list(applied.child_transaction_ids),
            "child_transactions": [row.model_dump(mode="json") for row in child_id_rows],
            "llm": True,
            "persisted": True,
            "provider": suggestion.provider.value if suggestion.provider is not None else None,
            "provenance": applied.provenance,
            "reason": suggestion.reason,
            "parent_amount": format(suggestion.parent_amount, "f"),
            "proposed_children": [child.model_dump(mode="json") for child in proposed_children],
            "classified_child_count": applied.classified_child_count,
        },
    )
    lines = [
        f"{tr('cli.ledger.labels.parent_id')}\t{applied.parent_transaction_id}",
        f"{tr('cli.ledger.labels.split_group_id')}\t{applied.split_group_id}",
        f"{tr('cli.ledger.labels.children')}\t{len(applied.child_transaction_ids)}",
    ]
    lines.extend(
        f"{tr('cli.ledger.labels.child_id')}\t{row.display_id}\t{row.full_id}" for row in child_id_rows
    )
    lines.append(f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{applied.provenance}")
    _emit_envelope(ctx, command="ledger.split", result=result, lines=lines)


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
            },
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
