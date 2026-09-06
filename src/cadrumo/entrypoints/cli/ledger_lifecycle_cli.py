"""Ledger lifecycle and transaction-structure CLI commands.

Lifecycle commands resolve transactions through the shared repository helpers
and emit typed :class:`OutputSchema` mutation
payloads inside :class:`SchemaEnvelope` through
:func:`emit_envelope` for every structural change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from pydantic import ValidationError

from ...application.ledger.actions_lifecycle import (
    archive_manual_transaction,
    mark_transaction_reviewed_excluded,
    remove_manual_transaction,
    reset_ledger_catalogue,
    restore_manual_transaction,
    stash_manual_transaction,
)
from ...application.ledger.actions_split_merge import merge_transactions, split_transaction
from ...application.ledger.id_resolution import compute_display_id_width
from ...application.ledger.models import SplitChildCommand
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.external_constants import PDF_MIME_TYPE
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity, strict_round_trip
from ...core.time.clock import now
from ...domain.attachments.enums import AttachmentSource, DocumentLinkSource
from ...domain.transactions.enums import BusinessClassification, is_classified
from ...domain.transactions.errors import TransactionValidationError
from ...llm.suggestions import LLMSplitApplyResult
from ._common import bad, current_workflow_state, emit_envelope, transaction_catalogue_repo
from ._decimal_parsing import parse_decimal_amount
from ._ledger_support import (
    emit_update_result,
    ledger_transaction_validation_no_recovery,
    ledger_validation_bad,
    resolve_id,
)

if TYPE_CHECKING:
    from ...application.ledger.models import ManualLedgerTransactionResult
    from ...llm.suggestions import LLMSplitSuggestion
    from ._ledger_payloads import LedgerSplitChildIdPayload, LedgerSplitChildProposalPayload


def ledger_detach(
    ctx: typer.Context,
    transaction_id: str,
    attachment_ids: tuple[str, ...] = (),
    actor: str | None = None,
) -> None:
    """Detach supplementary attachments from one ledger transaction."""
    from ...application.ledger.actions_manual import detach_manual_transaction_attachments

    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    resolved_id = resolve_id(transaction_repository, transaction_id)
    result = detach_manual_transaction_attachments(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        attachment_ids=tuple(attachment_ids),
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger detach",
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerDetachResult

    emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.detach",
        result_cls=LedgerDetachResult,
        notices=_stale_finalized_revision_notices(result),
    )


def ledger_attach(
    ctx: typer.Context,
    transaction_id: str,
    purchase_invoice_evidence_id: str | None = None,
    attachment_ids: tuple[str, ...] = (),
    actor: str | None = None,
) -> None:
    """Attach existing secure evidence objects to one ledger transaction."""
    from ...application.ledger.actions_manual import attach_manual_transaction_evidence

    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    resolved_id = resolve_id(transaction_repository, transaction_id)
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

    emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.attach",
        result_cls=LedgerAttachResult,
        notices=_stale_finalized_revision_notices(result),
    )


def _stale_finalized_revision_notices(result: ManualLedgerTransactionResult) -> list[Notice]:
    """Warn that each finalized revision citing this row will not pick the evidence up.

    A revision bundles its ledger evidence when it is VERIFIED, and that bundle
    is frozen. An attachment landing afterwards is stored on the ledger row but
    never reaches the already-verified filing, so an export or filing gate
    reading the bundle keeps refusing.

    The advisory deliberately names NO recovery verb, because neither candidate
    works and both were measured rather than assumed: ``work calculate``
    re-derives the same content-addressed revision id (evidence is not part of
    that hash) and returns the existing finalized revision untouched, and
    ``work discard`` is worse than useless — it marks the work unit
    ``descartado``, and the follow-up ``work create`` re-derives the SAME
    work-unit id and hands the discarded unit back, permanently stranding that
    (modelo, filing year, period) target for the profile. Suggesting either
    would send the operator further from a working filing, so the guidance is
    the ordering rule that does work: link invoices before calculating
    (``aeat-architecture-boundaries``: name a real way forward, never a bare
    refusal — and never a false one).
    """
    from ._modelo_rendering import advisory_notice

    return [
        advisory_notice(
            "ledger.attach.finalized_revision_stale",
            tr(
                "cli.ledger.attach.finalized_revision_stale",
                modelo=blocker.modelo,
                filing_year=str(blocker.filing_year),
                period=blocker.period,
            ),
            context={
                "work_unit_id": blocker.work_unit_id,
                "calculation_revision_id": blocker.calculation_revision_id,
                "revision_state": blocker.revision_state,
                "modelo": blocker.modelo,
                "filing_year": str(blocker.filing_year),
                "period": blocker.period,
                "reason": "finalized_revision_predates_evidence",
                # Neither candidate verb is safe here, so this advisory
                # carries no action. Saying so explicitly keeps a
                # deliberate absence distinguishable from an action
                # nobody got round to attaching.
                "actionability": "finalized_revision_has_no_safe_recovery_action",
            },
        )
        for blocker in result.stale_finalized_revisions
    ]


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


def ledger_evidence_pull(
    ctx: typer.Context,
    transaction_id: str,
    source: DocumentLinkSource,
    reference: str,
    note: str = "",
    actor: str | None = None,
) -> None:
    """Fetch a document link and store its bytes as encrypted evidence on a ledger row.

    The reference is resolved through
    :func:`resolve_document_link`, which fetches
    Drive files reachable under the granted ``drive.file`` scope. The fetched
    bytes are stored through the byte-bearing
    :func:`add_attachment` path (real
    ``sha256`` and ``mime_type``), and the original link is kept as manifest
    provenance. Gmail links, arbitrary URLs, and out-of-scope Drive files are
    **refused** — a link is never stored as evidence.
    """
    from ...adapters.outbound.google.active_profile import resolve_active_profile
    from ...adapters.outbound.google.document_link_resolver import resolve_document_link
    from ...adapters.outbound.storage.factory import build_google_credentials
    from ...adapters.persistence.storage.attachment import AttachmentStore
    from ...application.ledger.actions_manual import attach_manual_transaction_evidence
    from ...domain.attachments.enums import AttachmentKind
    from ...domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment

    attachment_source = source.to_attachment_source()
    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    resolved_id = resolve_id(transaction_repository, transaction_id)

    profile = resolve_active_profile()
    credentials = build_google_credentials(profile=profile)
    data = resolve_document_link(
        source=attachment_source,
        reference=reference,
        credentials=credentials,
    )

    store = AttachmentStore()
    attachment = add_attachment(
        store,
        content=AttachmentBytesContent(data=data),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.DRIVE_DOCUMENT,
            source=attachment_source,
            source_reference=reference,
            mime_type=_sniff_document_mime_type(reference, data),
            captured_at=now(),
            bucket_id=transaction_repository.bucket_id,
            link_transaction_ids=(resolved_id,),
            metadata={"source": attachment_source.value, "source_reference": reference},
            notes=note,
        ),
    )
    result = attach_manual_transaction_evidence(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        attachment_ids=(attachment.attachment_id,),
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger evidence pull",
        transaction_repository=transaction_repository,
        attachment_store=store,
    )
    from ._ledger_payloads import LedgerAttachResult

    emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.evidence.pull",
        result_cls=LedgerAttachResult,
    )


def _parse_drive_folder_reference(reference: str) -> str:
    """Resolve a Drive folder id/URL/reference to a bare folder id.

    Reuses the same id-extraction grammar as a single Drive document link
    (:func:`~adapters.outbound.google.parse_drive_file_id`); a Drive
    folder id has the same shape as a file id, only the ``in parents`` query
    disambiguates the two on the Drive side. Refuses a reference with no
    recognisable Drive id rather than sending an unparsed string to the API.
    """
    from ...adapters.outbound.google.document_link_resolver import parse_drive_file_id

    folder_id = parse_drive_file_id(reference)
    if folder_id is None:
        raise bad(
            tr("cli.app.ledger.evidence.pull_all_errors.folder_id_unrecognised", reference=reference),
        )
    return folder_id


def ledger_evidence_pull_all(
    ctx: typer.Context,
    folder: str,
    note: str = "",
) -> None:
    """Bulk-fetch every PDF/image child of a Drive folder into encrypted evidence.

    Lists the folder's children through
    :func:`~adapters.outbound.google.list_drive_folder_documents` (the
    same ``drive.file``-scoped minimal-scope posture
    :func:`ledger_evidence_pull` uses for a single document), then fetches and
    encrypts each PDF/image child through
    :func:`~adapters.outbound.google.resolve_document_link` and
    :func:`~domain.attachments.add_attachment` — the identical
    fetch-and-encrypt primitive ``doclink`` composes, never re-implemented
    here. Fetched attachments are content-addressed and deduplicate by
    SHA-256, so re-running the sweep is idempotent. Attachments are stored
    unlinked to any transaction; binding is a separate operator action.

    A file the app cannot reach under the ``drive.file`` scope is refused
    individually — evidence bytes are never stored as a link-only pointer,
    and one refused file does not abort the rest of the sweep. Gmail bulk
    fetch is out of scope pending a separate ``gmail.readonly``
    scope-upgrade decision.
    """
    from ...adapters.outbound.google.active_profile import resolve_active_profile
    from ...adapters.outbound.google.document_link_resolver import (
        list_drive_folder_documents,
        resolve_document_link,
    )
    from ...adapters.outbound.storage.factory import build_google_credentials
    from ...adapters.persistence.storage.attachment import AttachmentStore
    from ...application.ledger.evidence_sweep import classify_evidence_sweep_failure
    from ...core.errors.hierarchy import CadrumoError
    from ...domain.attachments.enums import AttachmentKind
    from ...domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
    from ._ledger_payloads import LedgerEvidencePullAllFilePayload, LedgerEvidencePullAllResult

    folder_id = _parse_drive_folder_reference(folder)
    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    bucket_id = transaction_repository.bucket_id

    profile = resolve_active_profile()
    credentials = build_google_credentials(profile=profile)
    listing = list_drive_folder_documents(folder_id=folder_id, credentials=credentials)

    store = AttachmentStore()
    rows: list[LedgerEvidencePullAllFilePayload] = []
    fetched_count = 0
    refused_count = 0
    for document in listing.documents:
        reference = f"https://drive.google.com/file/d/{document.file_id}"
        try:
            data = resolve_document_link(
                source=AttachmentSource.GOOGLE_DRIVE,
                reference=reference,
                credentials=credentials,
            )
            attachment = add_attachment(
                store,
                content=AttachmentBytesContent(data=data),
                request=AttachmentIngestionRequest(
                    kind=AttachmentKind.DRIVE_DOCUMENT,
                    source=AttachmentSource.GOOGLE_DRIVE,
                    source_reference=reference,
                    mime_type=document.mime_type or _sniff_document_mime_type(document.name, data),
                    captured_at=now(),
                    bucket_id=bucket_id,
                    metadata={
                        "source": AttachmentSource.GOOGLE_DRIVE.value,
                        "source_reference": reference,
                        "drive_folder_id": folder_id,
                        "drive_file_name": document.name,
                    },
                    notes=note,
                ),
            )
        except CadrumoError as exc:
            # Only a failure that is a fact about THIS document continues the
            # sweep; the classifier answers None for anything else, and that
            # one re-raises rather than fabricating a per-file cause for a
            # transport problem affecting every remaining row.
            refusal = classify_evidence_sweep_failure(exc)
            if refusal is None:
                raise
            refused_count += 1
            rows.append(
                LedgerEvidencePullAllFilePayload(
                    file_id=document.file_id,
                    name=document.name,
                    mime_type=document.mime_type,
                    fetched=False,
                    refusal_reason=refusal.value,
                ),
            )
            continue
        fetched_count += 1
        rows.append(
            LedgerEvidencePullAllFilePayload(
                file_id=document.file_id,
                name=document.name,
                mime_type=document.mime_type,
                fetched=True,
                attachment_id=attachment.attachment_id,
            ),
        )

    result = LedgerEvidencePullAllResult.model_validate(
        {
            "bucket_id": bucket_id,
            "folder_id": folder_id,
            "total_documents": len(listing.documents),
            "fetched_count": fetched_count,
            "refused_count": refused_count,
            "skipped_non_document_count": listing.skipped_non_document_count,
            "files": [row.model_dump(mode="json") for row in rows],
        },
    )
    lines = [
        f"{tr('cli.app.ledger.evidence.pull_all_labels.folder_id')}\t{folder_id}",
        f"{tr('cli.app.ledger.evidence.pull_all_labels.total')}\t{len(listing.documents)}",
        f"{tr('cli.app.ledger.evidence.pull_all_labels.fetched')}\t{fetched_count}",
        f"{tr('cli.app.ledger.evidence.pull_all_labels.refused')}\t{refused_count}",
        f"{tr('cli.app.ledger.evidence.pull_all_labels.skipped')}\t{listing.skipped_non_document_count}",
    ]
    lines.extend(
        f"{row.name}\t{row.mime_type}\t{'fetched' if row.fetched else 'refused'}\t"
        f"{row.attachment_id or row.refusal_reason or ''}"
        for row in rows
    )
    notices: list[Notice] = []
    if refused_count:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.pull_folder.files_refused",
                message=tr(
                    "cli.app.ledger.evidence.pull_all_notices.files_refused",
                    refused_count=refused_count,
                ),
                context={"folder_id": folder_id, "refused_count": str(refused_count)},
            ),
        )
    emit_envelope(
        ctx,
        command="ledger.evidence.pull_all",
        result=result,
        lines=lines,
        notices=notices or None,
    )


def ledger_archive(
    ctx: typer.Context,
    transaction_id: str,
    reason: str = "",
    yes: bool = False,
    actor: str | None = None,
) -> None:
    """Archive one ledger transaction through the bucket-scoped backend."""
    if not yes:
        raise bad(tr("cli.ledger.errors.confirm_required"))
    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    resolved_id = resolve_id(transaction_repository, transaction_id)
    result = archive_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        source_command="aeat app ledger archive",
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerArchiveResult

    emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.archive",
        result_cls=LedgerArchiveResult,
    )


def ledger_stash(
    ctx: typer.Context,
    transaction_id: str,
    reason: str = "",
    yes: bool = False,
    actor: str | None = None,
) -> None:
    """Stash one ledger transaction through the bucket-scoped backend."""
    if not yes:
        raise bad(tr("cli.ledger.errors.confirm_required"))
    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    resolved_id = resolve_id(transaction_repository, transaction_id)
    result = stash_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        source_command="aeat app ledger stash",
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerStashResult

    emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.stash",
        result_cls=LedgerStashResult,
    )


def ledger_exclude(
    ctx: typer.Context,
    transaction_id: str,
    reason: str = "",
    yes: bool = False,
    actor: str | None = None,
) -> None:
    """Mark one active ledger transaction as reviewed and excluded from filing."""
    if not yes:
        raise bad(tr("cli.ledger.errors.confirm_required"))
    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    resolved_id = resolve_id(transaction_repository, transaction_id)
    result = mark_transaction_reviewed_excluded(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        source_command="aeat app ledger exclude",
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerExcludeResult

    emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.exclude",
        result_cls=LedgerExcludeResult,
    )


def ledger_restore(
    ctx: typer.Context,
    transaction_id: str,
    reason: str = "",
    yes: bool = False,
    actor: str | None = None,
) -> None:
    """Restore one stashed or archived ledger transaction to active."""
    if not yes:
        raise bad(tr("cli.ledger.errors.confirm_required"))
    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    resolved_id = resolve_id(transaction_repository, transaction_id)
    result = restore_manual_transaction(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        source_command="aeat app ledger restore",
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerRestoreResult

    emit_update_result(
        ctx,
        result.transaction,
        result.ref.bucket_id,
        result.bucket_event_ids,
        command="ledger.restore",
        result_cls=LedgerRestoreResult,
    )


def ledger_remove(
    ctx: typer.Context,
    transaction_id: str,
    reason: str = "",
    dry_run: bool = False,
    yes: bool = False,
    actor: str | None = None,
) -> None:
    """Remove one ledger transaction through the bucket-scoped backend."""
    if not dry_run and not yes:
        raise bad(tr("cli.ledger.errors.confirm_required"))
    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    resolved_id = resolve_id(transaction_repository, transaction_id)
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

    emit_envelope(
        ctx,
        command="ledger.remove",
        result=strict_round_trip(LedgerRemoveResult, report),
        lines=[
            f"{tr('cli.ledger.labels.bucket')}\t{report.bucket_id}",
            f"{tr('cli.ledger.labels.id')}\t{report.transaction_id}",
            f"{tr('cli.ledger.labels.removed')}\t{report.removed}",
            f"{tr('cli.ledger.labels.dry_run')}\t{report.dry_run}",
        ],
    )


def ledger_reset(
    ctx: typer.Context,
    reason: str = "",
    dry_run: bool = False,
    yes: bool = False,
    actor: str | None = None,
) -> None:
    """Reset the active bucket ledger catalogue through the backend."""
    if not dry_run and not yes:
        raise bad(tr("cli.ledger.errors.confirm_required"))
    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    report = reset_ledger_catalogue(
        bucket_id=transaction_repository.bucket_id,
        actor=actor or resolve_active_bucket_id() or "operator",
        reason=reason,
        dry_run=dry_run,
        source_command="aeat app ledger reset",
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerResetResult

    emit_envelope(
        ctx,
        command="ledger.reset",
        result=strict_round_trip(LedgerResetResult, report),
        lines=[
            f"{tr('cli.ledger.labels.bucket')}\t{report.bucket_id}",
            f"{tr('cli.ledger.labels.rows')}\t{len(report.removed_transaction_ids)}",
            f"{tr('cli.ledger.labels.reset')}\t{report.reset}",
            f"{tr('cli.ledger.labels.dry_run')}\t{report.dry_run}",
        ],
    )


def ledger_split(
    ctx: typer.Context,
    transaction_id: str,
    child_amount: tuple[str, ...] = (),
    child_description: tuple[str, ...] = (),
    llm: bool = False,
    apply: bool = False,
    read_evidence: bool = False,
    vision_model: str | None = None,
    reason: str = "",
    yes: bool = False,
    actor: str | None = None,
) -> None:
    """Redistribute one parent transaction into N child transactions (manual or --llm)."""
    if llm or read_evidence:
        _ledger_split_llm(
            ctx,
            transaction_id=transaction_id,
            child_amount=list(child_amount),
            child_description=list(child_description),
            apply=apply,
            read_evidence=read_evidence,
            vision_model=vision_model,
            reason=reason,
            yes=yes,
            actor=actor,
        )
        return
    if not yes:
        raise bad(tr("cli.ledger.errors.confirm_required"))
    if len(child_amount) != len(child_description):
        raise bad(tr("cli.ledger.split.errors.child_args_mismatch"))
    if len(child_amount) < 2:
        raise bad(tr("cli.ledger.split.errors.min_two_children"))
    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    resolved_id = resolve_id(transaction_repository, transaction_id)
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
        raise ledger_validation_bad(exc) from exc
    from ._ledger_payloads import LedgerSplitResult

    child_id_rows = _split_child_id_rows(result.child_transaction_ids)
    notices = _split_classification_dropped_notices(result.parent_transaction.business_classification)
    lines = [
        f"{tr('cli.ledger.labels.bucket')}\t{result.bucket_id}",
        f"{tr('cli.ledger.labels.parent_id')}\t{result.parent_transaction_id}",
        f"{tr('cli.ledger.labels.split_group_id')}\t{result.split_group_id}",
        f"{tr('cli.ledger.labels.children')}\t{len(result.child_transaction_ids)}",
    ]
    lines.extend(f"{tr('cli.ledger.labels.child_id')}\t{row.display_id}\t{row.full_id}" for row in child_id_rows)
    lines.append(f"{tr('cli.ledger.labels.event_id')}\t{result.bucket_event_id}")
    lines.extend(f"ADVISORY\t{notice.message}" for notice in notices)
    emit_envelope(
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
    display-width convention the ledger list surface uses, so the operator can
    distinguish and copy either form.
    """
    from ._ledger_payloads import LedgerSplitChildIdPayload

    width = compute_display_id_width(child_transaction_ids)
    return [
        LedgerSplitChildIdPayload(full_id=child_id, display_id=child_id[:width]) for child_id in child_transaction_ids
    ]


def _split_classification_dropped_notices(
    parent_classification: BusinessClassification,
) -> list[Notice]:
    """Build the non-blocking advisory when a split drops the parent's classification.

    Split children deliberately default to ``NOT_YET_PROCESSED`` to force
    conscious per-row tax treatment; the parent's classification is not cloned.
    When the parent carried a real classified outcome (BUSINESS / PERSONAL /
    MIXED), that drop is surfaced as an ``info``
    :class:`Notice` so it is not silent — the operator
    is told the children need re-classification.
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
            context={
                "parent_classification": parent_classification.value,
            },
        ),
    ]


def _validate_split_llm_options(
    *,
    child_amount: list[str],
    child_description: list[str],
    apply: bool,
    yes: bool,
) -> None:
    """Reject manual-override flag combinations and an unconfirmed apply for ``ledger split --llm``."""
    if child_amount or child_description:
        raise bad(
            tr("cli.ledger.split.llm_exclusive"),
        )
    if apply and not yes:
        raise bad(tr("cli.ledger.errors.confirm_required"))


def _build_split_child_proposals(suggestion: LLMSplitSuggestion) -> list[LedgerSplitChildProposalPayload]:
    """Project the suggestion's proposed children into typed payload rows."""
    from ._ledger_payloads import LedgerSplitChildProposalPayload

    return [
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


def _render_split_llm_preview(
    ctx: typer.Context,
    *,
    bucket_id: str,
    suggestion: LLMSplitSuggestion,
    proposed_children: list[LedgerSplitChildProposalPayload],
) -> None:
    """Emit the non-persisting split preview envelope."""
    from ._ledger_llm_cli import transport_from_provenance
    from ._ledger_payloads import LedgerSplitResult

    result = LedgerSplitResult.model_validate(
        {
            "bucket_id": bucket_id,
            "parent_transaction_id": suggestion.transaction_id,
            "llm": True,
            "persisted": False,
            "provider": transport_from_provenance(suggestion.provenance),
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
    emit_envelope(ctx, command="ledger.split", result=result, lines=lines)


def _render_split_llm_applied(
    ctx: typer.Context,
    *,
    suggestion: LLMSplitSuggestion,
    applied: LLMSplitApplyResult,
    proposed_children: list[LedgerSplitChildProposalPayload],
) -> None:
    """Emit the persisted split-applied envelope."""
    from ._ledger_llm_cli import transport_from_provenance
    from ._ledger_payloads import LedgerSplitResult

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
            "provider": transport_from_provenance(suggestion.provenance),
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
    lines.extend(f"{tr('cli.ledger.labels.child_id')}\t{row.display_id}\t{row.full_id}" for row in child_id_rows)
    lines.append(f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{applied.provenance}")
    emit_envelope(ctx, command="ledger.split", result=result, lines=lines)


def _ledger_split_llm(
    ctx: typer.Context,
    *,
    transaction_id: str,
    child_amount: list[str],
    child_description: list[str],
    apply: bool,
    read_evidence: bool,
    vision_model: str | None,
    reason: str,
    yes: bool,
    actor: str | None,
) -> None:
    """Run the evidence-driven LLM split suggest / apply loop for ``ledger split --llm``.

    Without ``--apply`` the proposed children (derived amounts, model-selected
    categories, registry-derived IVA) are previewed and nothing is persisted.
    With ``--apply`` (and ``--yes``) the reviewed proposal is routed through the
    one review workflow (:func:`~application.ledger.llm_review_workflow.execute_reviewed_decision`)
    with the ``SPLIT_LLM`` origin, which delegates to the single-writer split
    plus per-child classification, registry-derived numbers, parent-invoice
    evidence link, and ``llm:<model>`` provenance. The manual ``--child-amount`` /
    ``--child-description`` flags are the explicit operator override and cannot be
    combined with ``--llm``.
    """
    from ...application.ledger.llm_classification import suggest_evidence_split
    from ...application.ledger.llm_review_workflow import (
        LlmReviewDecision,
        LlmReviewInvocationOrigin,
        execute_reviewed_decision,
    )

    _validate_split_llm_options(
        child_amount=child_amount,
        child_description=child_description,
        apply=apply,
        yes=yes,
    )

    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    bucket_id = transaction_repository.bucket_id
    resolved_id = resolve_id(transaction_repository, transaction_id)
    suggestion = suggest_evidence_split(
        bucket_id=bucket_id,
        transaction_id=resolved_id,
        transaction_repository=transaction_repository,
        read_evidence=read_evidence,
        vision_model=vision_model,
    )

    proposed_children = _build_split_child_proposals(suggestion)

    if not apply:
        _render_split_llm_preview(
            ctx,
            bucket_id=bucket_id,
            suggestion=suggestion,
            proposed_children=proposed_children,
        )
        return

    try:
        applied = execute_reviewed_decision(
            suggestion,
            origin=LlmReviewInvocationOrigin.SPLIT_LLM,
            decision=LlmReviewDecision.SPLIT,
            bucket_id=bucket_id,
            actor=actor or resolve_active_bucket_id() or "operator",
            transaction_repository=transaction_repository,
        )
    except TransactionValidationError as exc:
        raise ledger_transaction_validation_no_recovery(exc) from None
    except ValidationError as exc:
        raise ledger_validation_bad(exc) from exc
    if not isinstance(applied, LLMSplitApplyResult):
        raise TransactionValidationError(
            "SPLIT decision returned no evidence-split result",
            context={"result_type": type(applied).__name__},
        )

    _render_split_llm_applied(
        ctx,
        suggestion=suggestion,
        applied=applied,
        proposed_children=proposed_children,
    )


def ledger_merge(
    ctx: typer.Context,
    child_id: tuple[str, ...] = (),
    reason: str = "",
    yes: bool = False,
    actor: str | None = None,
) -> None:
    """Re-merge a complete cohort of split children into a fresh transaction."""
    if not yes:
        raise bad(tr("cli.ledger.errors.confirm_required"))
    if len(child_id) < 2:
        raise bad(tr("cli.ledger.merge.errors.min_two_children"))
    state = current_workflow_state()
    transaction_repository = transaction_catalogue_repo(state)
    resolved_ids = tuple(resolve_id(transaction_repository, raw) for raw in child_id)
    result = merge_transactions(
        bucket_id=transaction_repository.bucket_id,
        child_transaction_ids=resolved_ids,
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger merge",
        reason=reason,
        transaction_repository=transaction_repository,
    )
    from ._ledger_payloads import LedgerMergeResult

    emit_envelope(
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
    "ledger_evidence_pull",
    "ledger_evidence_pull_all",
    "ledger_exclude",
    "ledger_merge",
    "ledger_remove",
    "ledger_reset",
    "ledger_restore",
    "ledger_split",
    "ledger_stash",
]
