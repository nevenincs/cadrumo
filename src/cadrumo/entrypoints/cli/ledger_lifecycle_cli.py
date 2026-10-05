"""Ledger lifecycle and transaction-structure CLI commands.

Lifecycle commands resolve transactions through the shared repository helpers
and emit typed :class:`OutputSchema` mutation
payloads inside :class:`SchemaEnvelope` through
:func:`emit_envelope` for every structural change.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Literal
from uuid import UUID

import typer
from pydantic import ValidationError

from ...application.ledger.id_resolution import compute_display_id_width
from ...application.ledger.llm_review_contracts import (
    LEDGER_SPLIT_REVIEW_DEFINITION_ID,
    LedgerLlmReviewProjection,
    LedgerLlmReviewRequest,
    LedgerLlmReviewResponse,
    LedgerLlmSuggestionProjection,
)
from ...application.ledger.llm_review_results import LedgerLlmOperationResult
from ...application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from ...application.ledger.models import SplitChildCommand
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity, strict_round_trip
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.transactions.enums import BusinessClassification, is_classified
from ._decimal_parsing import parse_decimal_amount
from ._ledger_support import (
    ledger_validation_bad,
)
from .common import bad, emit_envelope
from .registered_operation_contracts import (
    RegisteredOperationCompletion,
    RegisteredOperationReviewCompletion,
    RegisteredOperationReviewHandler,
)
from .registered_operation_errors import invalid_completion_error, submitted_operation_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation

if TYPE_CHECKING:
    from ...application.ledger.split_operation import LedgerSplitOperationResult
    from ._ledger_payloads import LedgerSplitChildIdPayload, LedgerSplitChildProposalPayload


def ledger_detach(
    ctx: typer.Context,
    transaction_id: str,
    attachment_ids: tuple[str, ...] = (),
    actor: str | None = None,
) -> None:
    """Detach supplementary attachments from one ledger transaction."""
    from .runtime_ledger_attachment import emit_ledger_attachment_result, run_ledger_detach

    result = run_ledger_detach(
        ctx,
        transaction_id=transaction_id,
        attachment_ids=tuple(attachment_ids),
        actor=actor,
    )
    from ._ledger_payloads import LedgerDetachResult

    emit_ledger_attachment_result(
        ctx,
        result,
        command="ledger.detach",
        result_schema=LedgerDetachResult,
    )


def ledger_attach(
    ctx: typer.Context,
    transaction_id: str,
    purchase_invoice_evidence_id: str | None = None,
    attachment_ids: tuple[str, ...] = (),
    actor: str | None = None,
) -> None:
    """Attach existing secure evidence objects to one ledger transaction."""
    from .runtime_ledger_attachment import emit_ledger_attachment_result, run_ledger_attach

    result = run_ledger_attach(
        ctx,
        transaction_id=transaction_id,
        purchase_invoice_evidence_id=purchase_invoice_evidence_id,
        attachment_ids=tuple(attachment_ids),
        actor=actor,
    )
    from ._ledger_payloads import LedgerAttachResult

    emit_ledger_attachment_result(
        ctx,
        result,
        command="ledger.attach",
        result_schema=LedgerAttachResult,
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
    from ._ledger_payloads import LedgerArchiveResult
    from .runtime_ledger_lifecycle import emit_ledger_lifecycle_result, run_ledger_archive

    result = run_ledger_archive(
        ctx,
        transaction_id=transaction_id,
        reason=reason,
        actor=actor or resolve_active_bucket_id() or "operator",
    )
    emit_ledger_lifecycle_result(
        ctx,
        result,
        command="ledger.archive",
        result_schema=LedgerArchiveResult,
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
    from ._ledger_payloads import LedgerStashResult
    from .runtime_ledger_lifecycle import emit_ledger_lifecycle_result, run_ledger_stash

    result = run_ledger_stash(
        ctx,
        transaction_id=transaction_id,
        reason=reason,
        actor=actor or resolve_active_bucket_id() or "operator",
    )
    emit_ledger_lifecycle_result(
        ctx,
        result,
        command="ledger.stash",
        result_schema=LedgerStashResult,
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
    from ._ledger_payloads import LedgerExcludeResult
    from .runtime_ledger_lifecycle import emit_ledger_lifecycle_result, run_ledger_exclude

    result = run_ledger_exclude(
        ctx,
        transaction_id=transaction_id,
        reason=reason,
        actor=actor or resolve_active_bucket_id() or "operator",
    )
    emit_ledger_lifecycle_result(
        ctx,
        result,
        command="ledger.exclude",
        result_schema=LedgerExcludeResult,
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
    from ._ledger_payloads import LedgerRestoreResult
    from .runtime_ledger_lifecycle import emit_ledger_lifecycle_result, run_ledger_restore

    result = run_ledger_restore(
        ctx,
        transaction_id=transaction_id,
        reason=reason,
        actor=actor or resolve_active_bucket_id() or "operator",
    )
    emit_ledger_lifecycle_result(
        ctx,
        result,
        command="ledger.restore",
        result_schema=LedgerRestoreResult,
    )


def ledger_remove(
    ctx: typer.Context,
    transaction_id: str,
    reason: str = "",
    dry_run: bool = False,
    yes: bool = False,
    actor: str | None = None,
) -> None:
    """Remove one ledger transaction through the registered profile worker."""
    if not dry_run and not yes:
        raise bad(tr("cli.ledger.errors.confirm_required"))
    from ._ledger_payloads import LedgerRemoveResult
    from .runtime_ledger_remove import run_ledger_remove

    removal = run_ledger_remove(
        ctx,
        transaction_id=transaction_id,
        reason=reason,
        dry_run=dry_run,
        actor=actor or resolve_active_bucket_id() or "operator",
    )
    report = removal.report

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
    """Reset the authenticated profile ledger catalogue through its worker."""
    if not dry_run and not yes:
        raise bad(tr("cli.ledger.errors.confirm_required"))
    from .runtime_ledger_reset import run_ledger_reset

    reset = run_ledger_reset(ctx, reason=reason, dry_run=dry_run, actor=actor)
    report = reset.report
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


def _validate_manual_split_options(
    *,
    child_amount: tuple[str, ...],
    child_description: tuple[str, ...],
    yes: bool,
) -> None:
    """Validate the confirmation and cardinality contract for a manual split."""
    if not yes:
        raise bad(tr("cli.ledger.errors.confirm_required"))
    if len(child_amount) != len(child_description):
        raise bad(tr("cli.ledger.split.errors.child_args_mismatch"))
    if len(child_amount) < 2:
        raise bad(tr("cli.ledger.split.errors.min_two_children"))


def _emit_manual_split_result(ctx: typer.Context, result: LedgerSplitOperationResult) -> None:
    """Project the persisted split result and its classification advisory."""
    from ._ledger_payloads import LedgerSplitResult

    child_id_rows = _split_child_id_rows(result.child_transaction_ids)
    notices = _split_classification_dropped_notices(result.parent_business_classification)
    lines = [
        f"{tr('cli.ledger.labels.bucket')}\t{result.profile_id}",
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
                "bucket_id": str(result.profile_id),
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
    _validate_manual_split_options(
        child_amount=child_amount,
        child_description=child_description,
        yes=yes,
    )
    try:
        children = tuple(
            SplitChildCommand(
                amount=parse_decimal_amount(amount_raw, label="child-amount"),
                description=description_raw,
            )
            for amount_raw, description_raw in zip(child_amount, child_description, strict=True)
        )
    except ValidationError as exc:
        raise ledger_validation_bad(exc) from exc
    from .runtime_ledger_split import run_ledger_split

    result = run_ledger_split(
        ctx,
        transaction_id=transaction_id,
        children=children,
        reason=reason,
        actor=actor,
    )
    _emit_manual_split_result(ctx, result)


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


def _build_split_child_proposals(suggestion: LedgerLlmSuggestionProjection) -> list[LedgerSplitChildProposalPayload]:
    """Project the suggestion's proposed children into typed payload rows."""
    from ._ledger_payloads import LedgerSplitChildProposalPayload

    return [
        LedgerSplitChildProposalPayload.model_validate(
            {
                "proportion": child.proportion,
                "amount": child.amount,
                "description": child.description,
                "category": child.category,
                "iva_category": child.iva_category,
                "iva_rate": child.iva_rate,
                "taxable_base": child.taxable_base,
                "iva_amount": child.iva_amount,
                "rate_derivable": child.rate_derivable,
            },
        )
        for child in suggestion.children
    ]


def _render_split_llm_preview(
    ctx: typer.Context,
    *,
    bucket_id: str,
    suggestion: LedgerLlmSuggestionProjection,
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
            "parent_amount": suggestion.parent_amount,
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
    suggestion: LedgerLlmSuggestionProjection,
    applied: LedgerLlmOperationResult,
    proposed_children: list[LedgerSplitChildProposalPayload],
) -> None:
    """Emit the persisted split-applied envelope."""
    from ._ledger_llm_cli import transport_from_provenance
    from ._ledger_payloads import LedgerSplitResult

    child_id_rows = _split_child_id_rows(applied.child_transaction_ids)
    result = LedgerSplitResult.model_validate(
        {
            "bucket_id": str(applied.profile_id),
            "parent_transaction_id": applied.transaction_id,
            "split_group_id": applied.split_group_id,
            "child_transaction_ids": list(applied.child_transaction_ids),
            "child_transactions": [row.model_dump(mode="json") for row in child_id_rows],
            "llm": True,
            "persisted": True,
            "provider": transport_from_provenance(suggestion.provenance),
            "provenance": applied.provenance,
            "reason": suggestion.reason,
            "parent_amount": suggestion.parent_amount,
            "proposed_children": [child.model_dump(mode="json") for child in proposed_children],
            "classified_child_count": applied.classified_child_count,
        },
    )
    lines = [
        f"{tr('cli.ledger.labels.parent_id')}\t{applied.transaction_id}",
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
    from ...application.operations.schema_identity import OperationSchemaIdentityV1
    from ...application.runtime.contracts import RuntimeRefusalCode
    from ...core.operations import profile_operation_subject

    _validate_split_llm_options(
        child_amount=child_amount,
        child_description=child_description,
        apply=apply,
        yes=yes,
    )

    client = bound_profile_client(ctx)
    request = LedgerLlmReviewRequest(
        profile_id=client.profile_id,
        transaction_id=transaction_id,
        mode="split",
        origin=LlmReviewInvocationOrigin.SPLIT_LLM,
        preview=not apply,
        actor=actor,
        read_evidence=read_evidence,
        vision_model=vision_model,
        reason=reason,
    )
    reviewed: LedgerLlmReviewProjection | None = None

    def matches(projection: LedgerLlmReviewProjection) -> bool:
        return not (
            projection.profile_id != client.profile_id
            or projection.suggestion.kind != "split"
            or not projection.suggestion.transaction_id.startswith(request.transaction_id)
        )

    def decide(projection: LedgerLlmReviewProjection) -> Literal["apply"] | None:
        nonlocal reviewed
        if request.preview or not matches(projection):
            from ...application.runtime.contracts import RuntimeRefusalError

            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        reviewed = projection
        return "apply" if apply else None

    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_SPLIT_REVIEW_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerLlmOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
        review=RegisteredOperationReviewHandler(
            review_type=LedgerLlmReviewProjection,
            review_schema=OperationSchemaIdentityV1.from_model(
                schema_id=LEDGER_SPLIT_REVIEW_DEFINITION_ID + ".projection",
                schema_version=1,
                model_type=LedgerLlmReviewProjection,
            ),
            response_schema=OperationSchemaIdentityV1.from_model(
                schema_id=LEDGER_SPLIT_REVIEW_DEFINITION_ID + ".response",
                schema_version=1,
                model_type=LedgerLlmReviewResponse,
            ),
            decide=decide,
        ),
    )
    if isinstance(completed, RegisteredOperationReviewCompletion):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=None,
            effect=completed.effect,
        )
    applied = completed.projection
    if request.preview:
        preview = applied.preview
        if (
            _split_preview_receipt_invalid(completed, applied, reviewed, client.profile_id)
            or preview is None
            or _split_preview_proposal_invalid(applied, preview, matches)
        ):
            raise invalid_completion_error(completed)
        suggestion = preview.suggestion
        _render_split_llm_preview(
            ctx,
            bucket_id=str(client.profile_id),
            suggestion=suggestion,
            proposed_children=_build_split_child_proposals(suggestion),
        )
        return
    if (
        not apply
        or reviewed is None
        or _split_applied_proposal_invalid(completed, applied, reviewed, client.profile_id)
    ):
        raise invalid_completion_error(completed)
    _render_split_llm_applied(
        ctx,
        suggestion=reviewed.suggestion,
        applied=applied,
        proposed_children=_build_split_child_proposals(reviewed.suggestion),
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
    from .runtime_ledger_merge import run_ledger_merge

    result = run_ledger_merge(
        ctx,
        child_ids=child_id,
        reason=reason,
        actor=actor,
    )
    from ._ledger_payloads import LedgerMergeResult

    emit_envelope(
        ctx,
        command="ledger.merge",
        result=LedgerMergeResult.model_validate(
            {
                "bucket_id": str(result.profile_id),
                "split_group_id": result.split_group_id,
                "parent_transaction_id": result.parent_transaction_id,
                "merged_transaction_id": result.merged_transaction_id,
                "source_child_ids": list(result.source_child_ids),
                "bucket_event_id": result.bucket_event_id,
            },
        ),
        lines=[
            f"{tr('cli.ledger.labels.bucket')}\t{result.profile_id}",
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
    "ledger_exclude",
    "ledger_merge",
    "ledger_remove",
    "ledger_reset",
    "ledger_restore",
    "ledger_split",
    "ledger_stash",
]


def _split_preview_receipt_invalid(
    completed: RegisteredOperationCompletion[LedgerLlmOperationResult],
    applied: LedgerLlmOperationResult,
    reviewed: LedgerLlmReviewProjection | None,
    profile_id: UUID,
) -> bool:
    """Require a successful read-only preview without an applied review."""
    return (
        reviewed is not None
        or applied.outcome != "preview"
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or (completed.effect is not OperationEffect.NONE)
        or (completed.refusal_code is not None)
        or (applied.profile_id != profile_id)
    )


def _split_preview_proposal_invalid(
    applied: LedgerLlmOperationResult,
    preview: LedgerLlmReviewProjection,
    matches: Callable[[LedgerLlmReviewProjection], bool],
) -> bool:
    """Correlate the preview transaction, reviewed digest, and provenance."""
    return (
        not matches(preview)
        or applied.transaction_id != preview.suggestion.transaction_id
        or applied.reviewed_proposal_digest != preview.reviewed_proposal_digest
        or (applied.provenance != preview.suggestion.provenance)
    )


def _split_applied_proposal_invalid(
    completed: RegisteredOperationCompletion[LedgerLlmOperationResult],
    applied: LedgerLlmOperationResult,
    reviewed: LedgerLlmReviewProjection,
    profile_id: UUID,
) -> bool:
    """Correlate the committed split with the exact reviewed proposal and mutation effect."""
    return (
        applied.outcome != "split"
        or applied.profile_id != profile_id
        or applied.transaction_id != reviewed.suggestion.transaction_id
        or (applied.reviewed_proposal_digest != reviewed.reviewed_proposal_digest)
        or (applied.provenance != reviewed.suggestion.provenance)
        or (completed.effect is not OperationEffect.UPDATED)
    )
