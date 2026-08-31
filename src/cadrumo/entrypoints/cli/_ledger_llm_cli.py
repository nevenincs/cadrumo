"""LLM-assisted ledger classification CLI routing: suggest / saturate / reject / auto-split.

Extracted from ``_ledger.py`` (SPLIT-CANDIDATE) so the ledger command module
stays within its size budget. The router makes one model call — the split
proposer — and routes on its verdict: a multi-child verdict drives the
evidence-driven split (per-line base/IVA children), a single-child "no split"
verdict classifies the transaction in place from that lone child's selections.
The model emits no euro amount or regulated number; the registry derives every
child's base and IVA (``llm-selects-system-derives-tax-numbers``).

Also owns :func:`split_recommendation_notice`,
the typed ``info`` notice that ``classify --read-evidence`` emits when the model
flags the invoice as multi-component
(``aeat-cli-contract``).
"""

from __future__ import annotations

from collections.abc import Callable

import typer
from pydantic import BaseModel, ValidationError

from ...application.ledger.actions_manual import ledger_transaction_payload
from ...application.ledger.llm_classification import (
    apply_evidence_classification,
    derive_operator_iva_substrate,
    saturate_llm_classification,
    suggest_evidence_split,
    suggest_llm_classification,
)
from ...application.ledger.llm_review_workflow import (
    LlmReviewDecision,
    LlmReviewInvocationOrigin,
    execute_reviewed_decision,
)
from ...application.ledger.models import ManualLedgerTransactionResult
from ...application.ledger.review_projection import ledger_transaction_review_status
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.provenance_stamp import provenance_stamp_transport
from ...domain.iva.schema import IvaCategory
from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...llm.suggestions import (
    LLMClassificationSuggestion,
    LLMSaturatedSuggestion,
    LLMSplitApplyResult,
    LLMSplitSuggestion,
    LLMSuggestionRejectionResult,
)
from ._common import _bad, _state, _tx_repo, emit_envelope
from ._ledger_support import (
    _ledger_transaction_validation_no_recovery,
    _ledger_validation_bad,
    _parse_decimal,
    _resolve_id,
)

__all__ = [
    "dispatch_autosplit",
    "emit_llm_rejection",
    "ledger_classify_llm",
    "ledger_operator_iva_derive",
    "ledger_saturate_llm",
    "split_recommendation_notice",
]

type _LLMSuggestion = LLMClassificationSuggestion | LLMSaturatedSuggestion | LLMSplitSuggestion


def emit_llm_rejection(
    ctx: typer.Context,
    suggestion: _LLMSuggestion,
    *,
    origin: LlmReviewInvocationOrigin,
    bucket_id: str,
    reason: str,
    actor: str | None,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> None:
    """Record an explicit rejection of an LLM suggestion and emit the result.

    The fourth decision terminal: the row is NOT classified, but the rejection is
    captured as a ``ledger.transaction.llm_suggestion.rejected`` audit event. The
    write is routed through the one review workflow
    (:func:`~application.ledger.llm_review_workflow.execute_reviewed_decision`) with the caller's
    :class:`~application.ledger.llm_review_workflow.LlmReviewInvocationOrigin`, so the durable
    ``source_command`` audit label is derived from the origin rather than a
    CLI-owned literal. An ``info`` :class:`Notice` confirms the log and points at
    the manual-override next step
    (``aeat-cli-contract``).
    """
    from ._ledger_llm_payloads import LedgerClassifyLlmRejectResult

    result = execute_reviewed_decision(
        suggestion,
        origin=origin,
        decision=LlmReviewDecision.REJECT,
        bucket_id=bucket_id,
        reason=reason,
        actor=actor or resolve_active_bucket_id() or "operator",
        transaction_repository=transaction_repository,
    )
    assert isinstance(result, LLMSuggestionRejectionResult)
    payload = LedgerClassifyLlmRejectResult.model_validate(
        {
            "llm": True,
            "rejected": True,
            "provider": transport_from_provenance(suggestion.provenance),
            "transaction_id": result.transaction_id,
            "suggestion_kind": result.suggestion_kind,
            "provenance": result.provenance,
            "bucket_event_id": result.bucket_event_id,
            "operator_reason": result.operator_reason,
            "persisted": False,
        },
    )
    notice = Notice(
        severity=NoticeSeverity.INFO,
        code="ledger.classify.llm_rejected",
        message=tr(
            "cli.ledger.classify.llm_rejected_message",
        ),
        context={
            "transaction_id": result.transaction_id,
            "suggestion_kind": result.suggestion_kind,
        },
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.transaction_id}",
        f"{tr('cli.ledger.classify.llm_rejected_label')}\t{result.suggestion_kind}",
        notice.message,
    ]
    emit_envelope(ctx, command="ledger.classify", result=payload, lines=lines, notices=[notice])


def transport_from_provenance(provenance: str) -> str:
    """Return the transport segment of an ``llm:<transport>-<reader>:<model>`` stamp.

    Named for the transport rather than the reader because that is what it
    returns and what every one of its call sites publishes: each feeds the audit
    payload's ``provider`` key, which answers whether a document left the host.
    The earlier name and grammar sketch described the segment before the hyphen
    as the whole segment, which is the same conflation the slice made.

    The suggestion DTOs carried a ``provider`` enum until the cloud transport was
    retired; the payloads still publish this label, so it is derived from the
    provenance the suggestion already carries rather than restated. Deriving it
    keeps the field truthful if a second on-host reader is ever added, where a
    hardcoded constant would quietly misreport.

    **Delegated rather than parsed here**, for the reason the audit payload's
    sibling is: the stamp's middle segment is ``<transport>-<reader>``, so a
    colon split returned both glued together. Two implementations of one grammar
    agree only while somebody maintains both.

    Falls back to the whole string when the shape is unexpected, so a malformed
    provenance surfaces in the payload instead of being silently blanked.
    """
    return provenance_stamp_transport(provenance) or provenance


def split_recommendation_notice(transaction_id: str) -> Notice:
    """Build the typed ``info`` :class:`Notice` recommending an evidence-driven split.

    Fired when the evidence read judged the invoice multi-component. Selecting
    whether to split is an operator decision, so the notice records the
    observed transaction and does not invent a runnable next action.
    """
    return Notice(
        severity=NoticeSeverity.INFO,
        code="ledger.classify.split_recommended",
        message=tr("cli.ledger.classify.split_recommended_message"),
        context={
            "transaction_id": transaction_id,
            "source": "evidence_read",
        },
    )


def _autosplit_child_payloads(suggestion: LLMSplitSuggestion) -> list[object]:
    """Project a split suggestion's children to the shared proposal payload."""
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
        ).model_dump(mode="json")
        for child in suggestion.children
    ]


def dispatch_autosplit(
    ctx: typer.Context,
    *,
    transaction_id: str | None,
    classification: BusinessClassification | None,
    file: str | None,
    apply: bool,
    actor: str | None,
    read_evidence: bool,
    vision_model: str | None,
    reject: bool = False,
    reason: str = "",
) -> None:
    """Route ``classify --read-evidence --auto-split`` on the model's split verdict.

    One model call — the split proposer — yields the verdict. A multi-child verdict
    drives the evidence-driven split (preview, or with ``--apply`` the
    base/IVA-separating split); a single-child "no split" verdict classifies the
    transaction in place from that child's selections (preview, or with ``--apply``
    the in-place write). The model emits no euro amount or regulated number; the
    registry derives every child's base and IVA.
    """
    from ._ledger_llm_payloads import LedgerClassifyLlmSuggestResult
    from ._ledger_payloads import LedgerClassifySingleResult

    if not read_evidence:
        raise _bad(
            tr("cli.ledger.classify.auto_split_needs_evidence"),
        )
    if classification is not None or file is not None:
        raise _bad(
            tr("cli.ledger.classify.llm_exclusive"),
        )
    if reject and apply:
        raise _bad(
            tr("cli.ledger.classify.reject_apply_exclusive"),
        )
    if transaction_id is None:
        raise _bad(
            tr("cli.ledger.classify.id_required"),
        )

    state = _state()
    transaction_repository = _tx_repo(state)
    bucket_id = transaction_repository.bucket_id
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    suggestion = suggest_evidence_split(
        bucket_id=bucket_id,
        transaction_id=resolved_id,
        transaction_repository=transaction_repository,
        read_evidence=True,
        vision_model=vision_model,
    )

    if reject:
        emit_llm_rejection(
            ctx,
            suggestion,
            origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
            bucket_id=bucket_id,
            reason=reason,
            actor=actor,
            transaction_repository=transaction_repository,
        )
        return
    if suggestion.recommends_split:
        _emit_split(ctx, suggestion, bucket_id=bucket_id, apply=apply, actor=actor)
        return
    _emit_single(
        ctx,
        suggestion,
        bucket_id=bucket_id,
        apply=apply,
        actor=actor,
        result_models=(LedgerClassifyLlmSuggestResult, LedgerClassifySingleResult),
    )


def _emit_split(
    ctx: typer.Context,
    suggestion: LLMSplitSuggestion,
    *,
    bucket_id: str,
    apply: bool,
    actor: str | None,
) -> None:
    """Preview or apply the multi-child evidence-driven split for the auto-split route."""
    from ._ledger_payloads import LedgerSplitResult

    proposed_children = _autosplit_child_payloads(suggestion)
    if not apply:
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
                "proposed_children": proposed_children,
            },
        )
        lines = [
            f"{tr('cli.ledger.labels.id')}\t{suggestion.transaction_id}",
            f"{tr('cli.ledger.labels.children')}\t{len(proposed_children)}",
            tr("cli.ledger.classify.llm_review_hint"),
        ]
        emit_envelope(ctx, command="ledger.split", result=result, lines=lines)
        return
    try:
        applied = execute_reviewed_decision(
            suggestion,
            origin=LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT,
            decision=LlmReviewDecision.SPLIT,
            bucket_id=bucket_id,
            actor=actor or resolve_active_bucket_id() or "operator",
        )
    except TransactionValidationError as exc:
        raise _ledger_transaction_validation_no_recovery(exc) from None
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    assert isinstance(applied, LLMSplitApplyResult)
    result = LedgerSplitResult.model_validate(
        {
            "bucket_id": applied.bucket_id,
            "parent_transaction_id": applied.parent_transaction_id,
            "split_group_id": applied.split_group_id,
            "child_transaction_ids": list(applied.child_transaction_ids),
            "llm": True,
            "persisted": True,
            "provenance": applied.provenance,
        },
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{applied.parent_transaction_id}",
        f"{tr('cli.ledger.labels.children')}\t{len(applied.child_transaction_ids)}",
        f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{applied.provenance}",
    ]
    emit_envelope(ctx, command="ledger.split", result=result, lines=lines)


def _emit_single(
    ctx: typer.Context,
    suggestion: LLMSplitSuggestion,
    *,
    bucket_id: str,
    apply: bool,
    actor: str | None,
    result_models: tuple[type[BaseModel], type[BaseModel]],
) -> None:
    """Preview or apply the in-place single-line classification (no-split verdict)."""
    suggest_model, single_model = result_models
    child = suggestion.children[0]
    if not apply:
        suggest_result = suggest_model.model_validate(
            {
                "llm": True,
                "persisted": False,
                "transaction_id": suggestion.transaction_id,
                "provider": transport_from_provenance(suggestion.provenance),
                "classification": BusinessClassification.BUSINESS.value,
                "category": child.category.value if child.category is not None else None,
                "confidence": "1",
                "reason": suggestion.reason,
                "provenance": suggestion.provenance,
            },
        )
        lines = [
            f"{tr('cli.ledger.labels.id')}\t{suggestion.transaction_id}",
            f"{tr('cli.ledger.classify.llm_suggestion_label')}\t{BusinessClassification.BUSINESS.value}",
            f"{tr('cli.ledger.labels.category_id')}\t{child.category.value if child.category else ''}",
            f"{tr('cli.ledger.labels.iva_category')}\t{child.iva_category.value if child.iva_category else ''}",
            tr("cli.ledger.classify.auto_split_single_line"),
            tr("cli.ledger.classify.llm_review_hint"),
        ]
        emit_envelope(ctx, command="ledger.classify", result=suggest_result, lines=lines)
        return
    try:
        result = apply_evidence_classification(
            suggestion,
            bucket_id=bucket_id,
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command="aeat app ledger classify --read-evidence --auto-split --apply",
        )
    except TransactionValidationError as exc:
        raise _ledger_transaction_validation_no_recovery(exc) from None
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    transaction_payload = ledger_transaction_payload(result.transaction)
    review_status = ledger_transaction_review_status(result.transaction)
    classify_result = single_model.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.transaction.transaction_id}",
        f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{result.transaction.classified_by}",
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)


def _emit_llm_single_classify(
    ctx: typer.Context,
    result: ManualLedgerTransactionResult,
    *,
    extra_lines: tuple[str, ...] = (),
) -> None:
    """Emit the canonical single-transaction classify quintet for an LLM apply result.

    The ``--llm --apply`` and ``--llm --saturate --apply`` terminals are both
    single-transaction mutations that emit the mutation quintet
    (``LedgerClassifySingleResult``). ``extra_lines`` carries any substrate lines
    (e.g. the saturated IVA category) surfaced between the provenance and the
    review status.
    """
    from ._ledger_payloads import LedgerClassifySingleResult

    review_status = ledger_transaction_review_status(result.transaction)
    classify_result = LedgerClassifySingleResult.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": ledger_transaction_payload(result.transaction).model_dump(mode="json"),
        },
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.transaction.transaction_id}",
        f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{result.transaction.classified_by}",
        *extra_lines,
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)


def _validate_classify_llm_options(
    *,
    classification: BusinessClassification | None,
    file: str | None,
    reject: bool,
    apply: bool,
    transaction_id: str | None,
) -> str:
    """Reject the manual-override combination, the reject/apply conflict, a missing id, and an unavailable provider.

    Returns the validated ``transaction_id`` so the caller carries the
    non-``None`` guarantee this function enforces, rather than re-deriving it.

    A provider is checked for PATH availability only when one is named. With
    ``--read-evidence`` and no ``--llm``, a scanned/image invoice is read on-host
    by the local vision model, which needs no subprocess provider; a text-layer
    read with no provider is refused instructively downstream by the application.
    """
    if classification is not None or file is not None:
        raise _bad(
            tr("cli.ledger.classify.llm_exclusive"),
        )
    if reject and apply:
        raise _bad(
            tr("cli.ledger.classify.reject_apply_exclusive"),
        )
    if transaction_id is None:
        raise _bad(
            tr("cli.ledger.classify.id_required"),
        )
    return transaction_id


def _llm_suggestion_base_payload(
    suggestion: LLMClassificationSuggestion | LLMSaturatedSuggestion,
) -> dict[str, object]:
    """Build the shared non-persisting suggestion payload for a classify/saturate preview."""
    return {
        "llm": True,
        "persisted": False,
        "transaction_id": suggestion.transaction_id,
        "provider": transport_from_provenance(suggestion.provenance),
        "classification": suggestion.classification.value,
        "category": suggestion.category.value if suggestion.category is not None else None,
        "confidence": format(suggestion.confidence, "f"),
        "reason": suggestion.reason,
        "provenance": suggestion.provenance,
    }


def _render_classify_llm_preview(
    ctx: typer.Context,
    *,
    suggestion: LLMClassificationSuggestion,
) -> None:
    """Emit the non-persisting stage-1 classify suggestion. Approve = --apply, reject = --reject."""
    from ._ledger_llm_payloads import LedgerClassifyLlmSuggestResult

    suggest_result = LedgerClassifyLlmSuggestResult.model_validate(_llm_suggestion_base_payload(suggestion))
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{suggestion.transaction_id}",
        f"{tr('cli.ledger.classify.llm_suggestion_label')}\t{suggestion.classification.value}",
        f"{tr('cli.ledger.labels.category_id')}\t{suggestion.category.value if suggestion.category else ''}",
        f"{tr('cli.ledger.classify.llm_confidence_label')}\t{format(suggestion.confidence, 'f')}",
        f"{tr('cli.ledger.classify.llm_reason_label')}\t{suggestion.reason}",
        tr("cli.ledger.classify.llm_review_hint"),
    ]
    notices: list[Notice] = []
    if suggestion.recommends_split:
        notice = split_recommendation_notice(suggestion.transaction_id)
        notices.append(notice)
        lines.append(f"{tr('cli.ledger.classify.split_recommended_label')}\t{notice.message}")
    emit_envelope(ctx, command="ledger.classify", result=suggest_result, lines=lines, notices=notices)


def _saturate_derived_values(
    suggestion: LLMSaturatedSuggestion,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Return the formatted ``(iva_category, iva_rate, taxable_base, iva_amount)`` display values."""
    return (
        suggestion.iva_category.value if suggestion.iva_category is not None else None,
        format(suggestion.iva_rate, "f") if suggestion.iva_rate is not None else None,
        format(suggestion.taxable_base, "f") if suggestion.taxable_base is not None else None,
        format(suggestion.iva_amount, "f") if suggestion.iva_amount is not None else None,
    )


def _render_saturate_llm_preview(
    ctx: typer.Context,
    *,
    suggestion: LLMSaturatedSuggestion,
) -> None:
    """Emit the non-persisting saturated classify suggestion (model picks IVA category, system derives numbers)."""
    from ._ledger_llm_payloads import LedgerClassifyLlmSaturateResult

    iva_category_value, iva_rate_value, taxable_base_value, iva_amount_value = _saturate_derived_values(suggestion)
    derived_fields = {
        "iva_category": iva_category_value,
        "iva_rate": iva_rate_value,
        "taxable_base": taxable_base_value,
        "iva_amount": iva_amount_value,
        "rate_derivable": suggestion.rate_derivable,
        "derivation_note": suggestion.derivation_note or None,
    }
    classify_result = LedgerClassifyLlmSaturateResult.model_validate(
        {**_llm_suggestion_base_payload(suggestion), **derived_fields},
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{suggestion.transaction_id}",
        f"{tr('cli.ledger.classify.llm_suggestion_label')}\t{suggestion.classification.value}",
        f"{tr('cli.ledger.labels.category_id')}\t{suggestion.category.value if suggestion.category else ''}",
        f"{tr('cli.ledger.labels.iva_category')}\t{iva_category_value or ''}",
    ]
    if suggestion.rate_derivable:
        lines.extend(
            [
                f"{tr('cli.ledger.labels.taxable_base')}\t{taxable_base_value}",
                f"{tr('cli.ledger.labels.iva_rate')}\t{iva_rate_value}",
                f"{tr('cli.ledger.labels.iva_amount')}\t{iva_amount_value}",
            ],
        )
    elif suggestion.iva_category is not None:
        lines.append(f"{tr('cli.ledger.classify.saturate_non_derivable')}\t{suggestion.derivation_note}")
    lines.append(f"{tr('cli.ledger.classify.llm_confidence_label')}\t{format(suggestion.confidence, 'f')}")
    lines.append(tr("cli.ledger.classify.llm_review_hint"))
    notices: list[Notice] = []
    if suggestion.recommends_split:
        notice = split_recommendation_notice(suggestion.transaction_id)
        notices.append(notice)
        lines.append(f"{tr('cli.ledger.classify.split_recommended_label')}\t{notice.message}")
    emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines, notices=notices)


def _llm_classify_prologue[SuggestionT: (LLMClassificationSuggestion, LLMSaturatedSuggestion)](
    ctx: typer.Context,
    *,
    suggest_fn: Callable[..., SuggestionT],
    classification: BusinessClassification | None,
    file: str | None,
    transaction_id: str | None,
    apply: bool,
    actor: str | None,
    read_evidence: bool,
    vision_model: str | None,
    reject: bool,
    reason: str,
) -> tuple[SuggestionT, TransactionCatalogueRepositoryProtocol] | None:
    """Shared classify/saturate prologue: validate options, resolve, suggest, handle ``--reject``.

    Returns ``(suggestion, transaction_repository)`` for the caller to preview or
    apply, or ``None`` when ``--reject`` handled the invocation (the caller then
    returns). ``suggest_fn`` is the stage-specific suggester
    (:func:`suggest_llm_classification` or :func:`saturate_llm_classification`).
    """
    validated_transaction_id = _validate_classify_llm_options(
        classification=classification,
        file=file,
        reject=reject,
        apply=apply,
        transaction_id=transaction_id,
    )

    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, validated_transaction_id)
    suggestion = suggest_fn(
        bucket_id=transaction_repository.bucket_id,
        transaction_id=resolved_id,
        transaction_repository=transaction_repository,
        read_evidence=read_evidence,
        vision_model=vision_model,
    )

    if reject:
        emit_llm_rejection(
            ctx,
            suggestion,
            origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
            bucket_id=transaction_repository.bucket_id,
            reason=reason,
            actor=actor,
            transaction_repository=transaction_repository,
        )
        return None
    return suggestion, transaction_repository


def ledger_classify_llm(
    ctx: typer.Context,
    *,
    transaction_id: str | None,
    classification: BusinessClassification | None,
    file: str | None,
    business_pct: str | None,
    apply: bool,
    actor: str | None,
    read_evidence: bool = False,
    vision_model: str | None = None,
    reject: bool = False,
    reason: str = "",
) -> None:
    """Run the LLM suggest / apply / reject loop for ``aeat app ledger classify --llm``.

    Without ``--apply`` the model's suggestion is printed for review and nothing
    is persisted. With ``--apply`` the reviewed decision is routed through the one
    review workflow (:func:`~application.ledger.llm_review_workflow.execute_reviewed_decision`) with
    the ``CLASSIFY_LLM_APPLY`` origin, which delegates to the canonical
    classification write with ``llm:<model>`` provenance. With ``--reject`` the
    suggestion is recorded as a declined audit event and the row is left
    unchanged. ``--llm`` is mutually exclusive with the manual
    ``--classification`` / ``--file`` override.
    """
    prologue = _llm_classify_prologue(
        ctx,
        suggest_fn=suggest_llm_classification,
        classification=classification,
        file=file,
        transaction_id=transaction_id,
        apply=apply,
        actor=actor,
        read_evidence=read_evidence,
        vision_model=vision_model,
        reject=reject,
        reason=reason,
    )
    if prologue is None:
        return
    suggestion, transaction_repository = prologue

    if not apply:
        _render_classify_llm_preview(ctx, suggestion=suggestion)
        return

    try:
        result = execute_reviewed_decision(
            suggestion,
            origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
            decision=LlmReviewDecision.APPLY,
            bucket_id=transaction_repository.bucket_id,
            business_pct=_parse_decimal(business_pct, label="business-pct"),
            actor=actor or resolve_active_bucket_id() or "operator",
            transaction_repository=transaction_repository,
        )
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    assert isinstance(result, ManualLedgerTransactionResult)
    # D1: the --llm --apply path is a single-transaction mutation; it emits the
    # canonical mutation quintet with the llm provenance in the text lines.
    _emit_llm_single_classify(ctx, result)


def ledger_saturate_llm(
    ctx: typer.Context,
    *,
    transaction_id: str | None,
    classification: BusinessClassification | None,
    file: str | None,
    business_pct: str | None,
    apply: bool,
    actor: str | None,
    read_evidence: bool = False,
    vision_model: str | None = None,
    reject: bool = False,
    reason: str = "",
) -> None:
    """Run the saturating LLM suggest / apply / reject loop for ``classify --llm --saturate``.

    Extends the stage-1 loop to the rich tax substrate: the model selects an
    :class:`IvaCategory` and the system DERIVES the rate, base,
    and amount from the registry — never the model. Without ``--apply`` the full
    saturated suggestion is previewed and nothing is persisted; with ``--apply``
    the reviewed decision is routed through the one review workflow
    (:func:`~application.ledger.llm_review_workflow.execute_reviewed_decision`) with the
    ``CLASSIFY_LLM_SATURATE_APPLY`` origin, which delegates to the manual-command
    write with ``llm:<model>`` provenance; with ``--reject`` the suggestion is
    recorded as a declined audit event and the row is left unchanged. Manual
    ``classify`` flags remain the explicit per-field override.
    """
    prologue = _llm_classify_prologue(
        ctx,
        suggest_fn=saturate_llm_classification,
        classification=classification,
        file=file,
        transaction_id=transaction_id,
        apply=apply,
        actor=actor,
        read_evidence=read_evidence,
        vision_model=vision_model,
        reject=reject,
        reason=reason,
    )
    if prologue is None:
        return
    suggestion, transaction_repository = prologue

    iva_category_value = suggestion.iva_category.value if suggestion.iva_category is not None else None

    if not apply:
        _render_saturate_llm_preview(ctx, suggestion=suggestion)
        return

    try:
        result = execute_reviewed_decision(
            suggestion,
            origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_SATURATE_APPLY,
            decision=LlmReviewDecision.APPLY,
            bucket_id=transaction_repository.bucket_id,
            business_pct=_parse_decimal(business_pct, label="business-pct"),
            actor=actor or resolve_active_bucket_id() or "operator",
            transaction_repository=transaction_repository,
        )
    except TransactionValidationError as exc:
        raise _ledger_transaction_validation_no_recovery(exc) from None
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
    assert isinstance(result, ManualLedgerTransactionResult)
    # D1: the --llm --saturate --apply path is a single-transaction mutation; it
    # emits the canonical mutation quintet with the derived IVA category in the lines.
    _emit_llm_single_classify(
        ctx,
        result,
        extra_lines=(f"{tr('cli.ledger.labels.iva_category')}\t{iva_category_value or ''}",),
    )


def ledger_operator_iva_derive(
    ctx: typer.Context,
    *,
    transaction_id: str | None,
    classification: str | None,
    file: str | None,
    iva_category: IvaCategory | None,
    actor: str | None,
) -> None:
    """Derive the IVA substrate from an OPERATOR-chosen category (no LLM).

    The fallback for ``classify --saturate`` without ``--llm``: when the model
    declines (returns ``unknown``) or the operator already knows the category,
    pick it with ``--iva-category`` and the system derives the base, rate, and
    amount from the registry — the same grounded
    :func:`derive_operator_iva_substrate` path the LLM
    saturate uses, but operator-initiated and stamped with ``derived:``
    provenance. Only the IVA substrate is touched; the business classification
    and its provenance are left intact.
    """
    from ._ledger_payloads import LedgerClassifySingleResult

    if file is not None or classification is not None:
        raise _bad(
            "--saturate without --llm derives the IVA substrate from --iva-category alone; "
            "it cannot be combined with --classification or --file. Classify the row "
            "first, then run 'classify <id> --iva-category <category> --saturate'.",
        )
    if transaction_id is None:
        raise _bad(
            tr("cli.ledger.classify.id_required"),
        )
    if iva_category is None:
        raise _bad(
            tr("cli.ledger.classify.saturate_requires_llm"),
        )

    state = _state()
    transaction_repository = _tx_repo(state)
    resolved_id = _resolve_id(transaction_repository, transaction_id)
    try:
        derivation = derive_operator_iva_substrate(
            bucket_id=transaction_repository.bucket_id,
            transaction_id=resolved_id,
            iva_category=iva_category,
            actor=actor or resolve_active_bucket_id() or "operator",
            source_command=LlmReviewInvocationOrigin.CLASSIFY_IVA_CATEGORY_SATURATE.source_command,
            transaction_repository=transaction_repository,
        )
    except TransactionValidationError as exc:
        raise _ledger_transaction_validation_no_recovery(exc) from None
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc

    if not derivation.derivable:
        raise _bad(
            f"{iva_category.value} has no simple Spanish rate to derive: {derivation.note} "
            "Supply --taxable-base, --iva-rate, and --iva-amount by hand for this category.",
        )

    result = derivation.result
    taxable_base = derivation.taxable_base
    iva_rate = derivation.iva_rate
    iva_amount = derivation.iva_amount
    if result is None or taxable_base is None or iva_rate is None or iva_amount is None:
        raise _bad(
            f"{iva_category.value} was reported derivable but produced no IVA substrate; "
            "supply --taxable-base, --iva-rate, and --iva-amount by hand for this category.",
        )

    transaction_payload = ledger_transaction_payload(result.transaction)
    review_status = ledger_transaction_review_status(result.transaction)
    classify_result = LedgerClassifySingleResult.model_validate(
        {
            "bucket_id": result.ref.bucket_id,
            "transaction_id": result.transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.transaction.transaction_id}",
        f"{tr('cli.ledger.labels.iva_category')}\t{derivation.iva_category.value}",
        f"{tr('cli.ledger.labels.taxable_base')}\t{format(taxable_base, 'f')}",
        f"{tr('cli.ledger.labels.iva_rate')}\t{format(iva_rate, 'f')}",
        f"{tr('cli.ledger.labels.iva_amount')}\t{format(iva_amount, 'f')}",
        f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{result.transaction.classified_by}",
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)
