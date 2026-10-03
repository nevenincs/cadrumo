"""Render registered ledger LLM reviews and their settled classification outcomes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict

import typer
from pydantic import ValidationError

from ...application.ledger.actions_common import display_decimal
from ...application.ledger.classify_result_contracts import (
    LedgerClassifyOperationResult,
)
from ...application.ledger.llm_review_contracts import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LedgerLlmReviewProjection,
    LedgerLlmReviewRequest,
    LedgerLlmReviewResponse,
    LedgerLlmSuggestionProjection,
)
from ...application.ledger.llm_review_results import LedgerLlmOperationResult
from ...application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from ...application.ledger.operator_iva_contracts import (
    LedgerOperatorIvaResult,
)
from ...application.operations.registry import OperationSchemaIdentityV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.provenance_stamp import provenance_stamp_transport
from ...domain.iva.schema import IvaCategory
from ...domain.transactions.enums import BusinessClassification
from ._ledger_support import (
    ledger_validation_bad,
    parse_decimal_option,
)
from .common import bad, emit_envelope
from .registered_operation_contracts import (
    RegisteredOperationCompletion,
    RegisteredOperationReviewCompletion,
    RegisteredOperationReviewHandler,
)
from .registered_operation_errors import invalid_completion_error, submitted_operation_error
from .runtime_ledger_classify import run_ledger_operator_iva
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

__all__ = [
    "dispatch_autosplit",
    "emit_llm_rejection",
    "ledger_classify_llm",
    "ledger_operator_iva_derive",
    "ledger_saturate_llm",
    "split_recommendation_notice",
]


def _run_review(
    ctx: typer.Context,
    *,
    transaction_id: str,
    mode: Literal["classification", "saturated", "auto_split"],
    origin: LlmReviewInvocationOrigin,
    apply: bool,
    reject: bool,
    actor: str | None,
    read_evidence: bool,
    vision_model: str | None,
    reason: str,
    business_pct: str | None = None,
) -> LedgerLlmReviewProjection | LedgerLlmOperationResult:
    """Use the canonical reviewed-operation driver and correlate the settled proposal."""
    client = bound_profile_client(ctx)
    percentage = parse_decimal_option(business_pct, label="business-pct") if apply else None
    try:
        request = LedgerLlmReviewRequest(
            profile_id=client.profile_id,
            transaction_id=transaction_id,
            mode=mode,
            origin=origin,
            preview=not (apply or reject),
            business_pct=display_decimal(percentage) if percentage is not None else None,
            actor=actor,
            read_evidence=read_evidence,
            vision_model=vision_model,
            reason=reason,
        )
    except ValidationError as error:
        raise ledger_validation_bad(error) from error
    reviewed_projections: list[LedgerLlmReviewProjection] = []

    def matches(projection: LedgerLlmReviewProjection) -> bool:
        return _matches_llm_review(projection, client.profile_id, request, mode)

    def decide(projection: LedgerLlmReviewProjection) -> Literal["apply", "reject"] | None:
        if request.preview or not matches(projection):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        reviewed_projections.append(projection)
        return "reject" if reject else "apply" if apply else None

    definition_id = LEDGER_CLASSIFY_REVIEW_DEFINITION_ID
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerLlmOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
        review=RegisteredOperationReviewHandler(
            review_type=LedgerLlmReviewProjection,
            review_schema=OperationSchemaIdentityV1.from_model(
                schema_id=definition_id + ".projection", schema_version=1, model_type=LedgerLlmReviewProjection
            ),
            response_schema=OperationSchemaIdentityV1.from_model(
                schema_id=definition_id + ".response", schema_version=1, model_type=LedgerLlmReviewResponse
            ),
            decide=decide,
        ),
    )
    reviewed = reviewed_projections[-1] if reviewed_projections else None
    if isinstance(completed, RegisteredOperationReviewCompletion):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=None,
            effect=completed.effect,
        )
    if request.preview:
        return _llm_review_preview(completed, reviewed, client.profile_id, matches)
    return _llm_review_settled(completed, reviewed, client.profile_id, mode, apply, reject)


def emit_llm_rejection(ctx: typer.Context, result: LedgerLlmOperationResult) -> None:
    """Present the admitted audit-only rejection without performing another write."""
    from ._ledger_llm_payloads import LedgerClassifyLlmRejectResult

    if result.outcome != "rejected" or result.suggestion_kind is None or result.bucket_event_id is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    payload = LedgerClassifyLlmRejectResult.model_validate(
        {
            "llm": True,
            "rejected": True,
            "provider": transport_from_provenance(result.provenance),
            "transaction_id": result.transaction_id,
            "suggestion_kind": result.suggestion_kind,
            "provenance": result.provenance,
            "bucket_event_id": result.bucket_event_id,
            "operator_reason": result.operator_reason,
            "persisted": False,
        }
    )
    notice = Notice(
        severity=NoticeSeverity.INFO,
        code="ledger.classify.llm_rejected",
        message=tr("cli.ledger.classify.llm_rejected_message"),
        context={"transaction_id": result.transaction_id, "suggestion_kind": result.suggestion_kind},
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.transaction_id}",
        f"{tr('cli.ledger.classify.llm_rejected_label')}\t{result.suggestion_kind}",
        notice.message,
    ]
    emit_envelope(ctx, command="ledger.classify", result=payload, lines=lines, notices=[notice])


def _emit_llm_single_classify(
    ctx: typer.Context, result: LedgerClassifyOperationResult, *, extra_lines: tuple[str, ...] = ()
) -> None:
    """Render the worker's admitted single-transaction classify quintet."""
    from ._ledger_payloads import LedgerClassifySingleResult, TransactionPayload

    transaction, review_status = result.transaction, result.review_status
    if transaction is None or review_status is None or result.outcome != "classified":
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    payload = LedgerClassifySingleResult.model_validate(
        {
            "bucket_id": str(result.profile_id),
            "transaction_id": transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": TransactionPayload.model_validate(transaction.model_dump(mode="json")).model_dump(
                mode="json"
            ),
        }
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{transaction.transaction_id}",
        f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{transaction.classified_by}",
        *extra_lines,
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    emit_envelope(ctx, command="ledger.classify", result=payload, lines=lines)


def _render_autosplit_preview(ctx: typer.Context, review: LedgerLlmReviewProjection) -> None:
    """Render the same split or lone-child preview from admitted wire facts."""
    from ._ledger_llm_payloads import LedgerClassifyLlmSuggestResult
    from ._ledger_payloads import LedgerSplitResult

    suggestion = review.suggestion
    child = next(iter(suggestion.children), None)
    if child is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if len(suggestion.children) > 1:
        children = _autosplit_child_payloads(suggestion)
        payload = LedgerSplitResult.model_validate(
            {
                "bucket_id": str(review.profile_id),
                "parent_transaction_id": suggestion.transaction_id,
                "llm": True,
                "persisted": False,
                "provider": transport_from_provenance(suggestion.provenance),
                "provenance": suggestion.provenance,
                "reason": suggestion.reason,
                "parent_amount": suggestion.parent_amount,
                "proposed_children": children,
            }
        )
        lines = [
            f"{tr('cli.ledger.labels.id')}\t{suggestion.transaction_id}",
            f"{tr('cli.ledger.labels.children')}\t{len(children)}",
            tr("cli.ledger.classify.llm_review_hint"),
        ]
        emit_envelope(ctx, command="ledger.split", result=payload, lines=lines)
        return
    payload = LedgerClassifyLlmSuggestResult.model_validate(
        {
            "llm": True,
            "persisted": False,
            "transaction_id": suggestion.transaction_id,
            "provider": transport_from_provenance(suggestion.provenance),
            "classification": BusinessClassification.BUSINESS.value,
            "category": child.category,
            "confidence": "1",
            "reason": suggestion.reason,
            "provenance": suggestion.provenance,
        }
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{suggestion.transaction_id}",
        f"{tr('cli.ledger.classify.llm_suggestion_label')}\t{BusinessClassification.BUSINESS.value}",
        f"{tr('cli.ledger.labels.category_id')}\t{child.category or ''}",
        f"{tr('cli.ledger.labels.iva_category')}\t{child.iva_category or ''}",
        tr("cli.ledger.classify.auto_split_single_line"),
        tr("cli.ledger.classify.llm_review_hint"),
    ]
    emit_envelope(ctx, command="ledger.classify", result=payload, lines=lines)


def _render_settled(ctx: typer.Context, result: LedgerLlmOperationResult, *, saturated: bool = False) -> None:
    """Select presentation from the worker's settled outcome without another service call."""
    if result.outcome == "rejected":
        emit_llm_rejection(ctx, result)
    elif result.outcome == "split":
        from ._ledger_payloads import LedgerSplitResult

        payload = LedgerSplitResult.model_validate(
            {
                "bucket_id": str(result.profile_id),
                "parent_transaction_id": result.transaction_id,
                "split_group_id": result.split_group_id,
                "child_transaction_ids": list(result.child_transaction_ids),
                "llm": True,
                "persisted": True,
                "provenance": result.provenance,
            }
        )
        lines = [
            f"{tr('cli.ledger.labels.id')}\t{result.transaction_id}",
            f"{tr('cli.ledger.labels.children')}\t{len(result.child_transaction_ids)}",
            f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{result.provenance}",
        ]
        emit_envelope(ctx, command="ledger.split", result=payload, lines=lines)
    else:
        classified = result.classification
        if classified is None or classified.transaction is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        extra = (
            (f"{tr('cli.ledger.labels.iva_category')}\t{classified.transaction.iva_category or ''}",)
            if saturated
            else ()
        )
        _emit_llm_single_classify(ctx, classified, extra_lines=extra)


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


def _autosplit_child_payloads(suggestion: LedgerLlmSuggestionProjection) -> list[object]:
    """Project a split suggestion's children to the shared proposal payload."""
    from ._ledger_payloads import LedgerSplitChildProposalPayload

    return [
        LedgerSplitChildProposalPayload.model_validate(
            {
                "proportion": child.proportion,
                "amount": child.amount,
                "description": child.description,
                "category": child.category if child.category is not None else None,
                "iva_category": child.iva_category if child.iva_category is not None else None,
                "iva_rate": child.iva_rate if child.iva_rate is not None else None,
                "taxable_base": child.taxable_base if child.taxable_base is not None else None,
                "iva_amount": child.iva_amount if child.iva_amount is not None else None,
                "rate_derivable": child.rate_derivable,
            },
        ).model_dump(mode="json")
        for child in suggestion.children
    ]


def _validate_classify_llm_options(
    *,
    classification: BusinessClassification | None,
    file: str | None,
    reject: bool,
    apply: bool,
    transaction_id: str | None,
) -> str:
    """Reject the manual-override combination, the reject/apply conflict, and a missing id.

    These three are argv-shape rules: they judge which flags were typed
    together, so they belong at the boundary that parsed them rather than in a
    service a second frontend would call with a structured request.

    Returns the validated ``transaction_id`` so the caller carries the
    non-``None`` guarantee this function enforces, rather than re-deriving it.

    Reader availability is deliberately NOT checked here. With
    ``--read-evidence`` and no ``--llm``, a scanned or image invoice is read
    on-host by the local vision model, which needs no subprocess provider at
    all; and a text-layer read whose semantic reader is missing is refused by
    :func:`~application.ledger.invoice_draft_extraction._refuse_a_text_read_with_no_reader`,
    which says so instructively and declines to escalate to a heavier engine the
    operator did not ask for. Repeating that judgement here would put an
    environment check in an adapter and give the two answers room to disagree.
    """
    if classification is not None or file is not None:
        raise bad(
            tr("cli.ledger.classify.llm_exclusive"),
        )
    if reject and apply:
        raise bad(
            tr("cli.ledger.classify.reject_apply_exclusive"),
        )
    if transaction_id is None:
        raise bad(
            tr("cli.ledger.classify.id_required"),
        )
    return transaction_id


def _llm_suggestion_base_payload(
    suggestion: LedgerLlmSuggestionProjection,
) -> dict[str, object]:
    """Build the shared non-persisting suggestion payload for a classify/saturate preview."""
    return {
        "llm": True,
        "persisted": False,
        "transaction_id": suggestion.transaction_id,
        "provider": transport_from_provenance(suggestion.provenance),
        "classification": suggestion.classification,
        "category": suggestion.category if suggestion.category is not None else None,
        "confidence": suggestion.confidence,
        "reason": suggestion.reason,
        "provenance": suggestion.provenance,
    }


def _render_classify_llm_preview(
    ctx: typer.Context,
    *,
    suggestion: LedgerLlmSuggestionProjection,
) -> None:
    """Emit the non-persisting stage-1 classify suggestion. Approve = --apply, reject = --reject."""
    from ._ledger_llm_payloads import LedgerClassifyLlmSuggestResult

    suggest_result = LedgerClassifyLlmSuggestResult.model_validate(_llm_suggestion_base_payload(suggestion))
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{suggestion.transaction_id}",
        f"{tr('cli.ledger.classify.llm_suggestion_label')}\t{suggestion.classification}",
        f"{tr('cli.ledger.labels.category_id')}\t{suggestion.category if suggestion.category else ''}",
        f"{tr('cli.ledger.classify.llm_confidence_label')}\t{suggestion.confidence}",
        f"{tr('cli.ledger.classify.llm_reason_label')}\t{suggestion.reason}",
        tr("cli.ledger.classify.llm_review_hint"),
    ]
    notices: list[Notice] = []
    if suggestion.multiple_components is True:
        notice = split_recommendation_notice(suggestion.transaction_id)
        notices.append(notice)
        lines.append(f"{tr('cli.ledger.classify.split_recommended_label')}\t{notice.message}")
    emit_envelope(ctx, command="ledger.classify", result=suggest_result, lines=lines, notices=notices)


def _saturate_derived_values(
    suggestion: LedgerLlmSuggestionProjection,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Return the formatted ``(iva_category, iva_rate, taxable_base, iva_amount)`` display values."""
    return (
        suggestion.iva_category if suggestion.iva_category is not None else None,
        suggestion.iva_rate if suggestion.iva_rate is not None else None,
        suggestion.taxable_base if suggestion.taxable_base is not None else None,
        suggestion.iva_amount if suggestion.iva_amount is not None else None,
    )


def _render_saturate_llm_preview(
    ctx: typer.Context,
    *,
    suggestion: LedgerLlmSuggestionProjection,
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
        f"{tr('cli.ledger.classify.llm_suggestion_label')}\t{suggestion.classification}",
        f"{tr('cli.ledger.labels.category_id')}\t{suggestion.category if suggestion.category else ''}",
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
    lines.append(f"{tr('cli.ledger.classify.llm_confidence_label')}\t{suggestion.confidence}")
    lines.append(tr("cli.ledger.classify.llm_review_hint"))
    notices: list[Notice] = []
    if suggestion.multiple_components is True:
        notice = split_recommendation_notice(suggestion.transaction_id)
        notices.append(notice)
        lines.append(f"{tr('cli.ledger.classify.split_recommended_label')}\t{notice.message}")
    emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines, notices=notices)


class LedgerLlmRouteArguments(TypedDict):
    """The argument set both LLM ledger routes accept.

    ``ledger_classify_llm`` and ``ledger_saturate_llm`` take the same
    parameters, and the root ``ledger`` verb chooses between them after
    building one argument set. Naming that shape keeps the choice a single
    branch instead of two duplicated call sites.
    """

    ctx: typer.Context
    transaction_id: str | None
    classification: BusinessClassification | None
    file: str | None
    business_pct: str | None
    apply: bool
    actor: str | None
    read_evidence: bool
    vision_model: str | None
    reject: bool
    reason: str


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
    if not read_evidence:
        raise bad(tr("cli.ledger.classify.auto_split_needs_evidence"))
    transaction_id = _validate_classify_llm_options(
        classification=classification, file=file, reject=reject, apply=apply, transaction_id=transaction_id
    )
    outcome = _run_review(
        ctx,
        transaction_id=transaction_id,
        mode="auto_split",
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT
        if reject
        else LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT,
        apply=apply,
        reject=reject,
        actor=actor,
        read_evidence=read_evidence,
        vision_model=vision_model,
        reason=reason,
    )
    if isinstance(outcome, LedgerLlmReviewProjection):
        _render_autosplit_preview(ctx, outcome)
    else:
        _render_settled(ctx, outcome)


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
    transaction_id = _validate_classify_llm_options(
        classification=classification, file=file, reject=reject, apply=apply, transaction_id=transaction_id
    )
    outcome = _run_review(
        ctx,
        transaction_id=transaction_id,
        mode="classification",
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT
        if reject
        else LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
        apply=apply,
        reject=reject,
        actor=actor,
        read_evidence=read_evidence,
        vision_model=vision_model,
        reason=reason,
        business_pct=business_pct,
    )
    if isinstance(outcome, LedgerLlmReviewProjection):
        _render_classify_llm_preview(ctx, suggestion=outcome.suggestion)
    else:
        _render_settled(ctx, outcome)


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
    transaction_id = _validate_classify_llm_options(
        classification=classification, file=file, reject=reject, apply=apply, transaction_id=transaction_id
    )
    outcome = _run_review(
        ctx,
        transaction_id=transaction_id,
        mode="saturated",
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT
        if reject
        else LlmReviewInvocationOrigin.CLASSIFY_LLM_SATURATE_APPLY,
        apply=apply,
        reject=reject,
        actor=actor,
        read_evidence=read_evidence,
        vision_model=vision_model,
        reason=reason,
        business_pct=business_pct,
    )
    if isinstance(outcome, LedgerLlmReviewProjection):
        _render_saturate_llm_preview(ctx, suggestion=outcome.suggestion)
    else:
        _render_settled(ctx, outcome, saturated=True)


def _validate_operator_iva_request(
    *,
    transaction_id: str | None,
    classification: str | None,
    file: str | None,
    iva_category: IvaCategory | None,
) -> tuple[str, IvaCategory]:
    """Validate the operator-only saturation route and return its required inputs."""
    if file is not None or classification is not None:
        raise bad(
            "--saturate without --llm derives the IVA substrate from --iva-category alone; "
            "it cannot be combined with --classification or --file. Classify the row "
            "first, then run 'classify <id> --iva-category <category> --saturate'.",
        )
    if transaction_id is None:
        raise bad(
            tr("cli.ledger.classify.id_required"),
        )
    if iva_category is None:
        raise bad(
            tr("cli.ledger.classify.saturate_requires_llm"),
        )
    return transaction_id, iva_category


def _emit_operator_iva_result(
    ctx: typer.Context,
    *,
    derivation: LedgerOperatorIvaResult,
) -> None:
    """Emit the canonical single-result envelope for operator IVA derivation."""
    from ._ledger_payloads import LedgerClassifySingleResult

    result = derivation.classification
    if result is None or result.transaction is None or result.review_status is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    transaction_payload = result.transaction
    review_status = result.review_status
    classify_result = LedgerClassifySingleResult.model_validate(
        {
            "bucket_id": str(result.profile_id),
            "transaction_id": result.transaction.transaction_id,
            "bucket_event_ids": list(result.bucket_event_ids),
            "review_status": review_status,
            "transaction": transaction_payload.model_dump(mode="json"),
        },
    )
    lines = [
        f"{tr('cli.ledger.labels.id')}\t{result.transaction.transaction_id}",
        f"{tr('cli.ledger.labels.iva_category')}\t{derivation.iva_category}",
        f"{tr('cli.ledger.labels.taxable_base')}\t{derivation.taxable_base}",
        f"{tr('cli.ledger.labels.iva_rate')}\t{derivation.iva_rate}",
        f"{tr('cli.ledger.labels.iva_amount')}\t{derivation.iva_amount}",
        f"{tr('cli.ledger.classify.llm_classified_by_label')}\t{result.transaction.classified_by}",
        f"{tr('cli.ledger.labels.review_status')}\t{review_status}",
    ]
    emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)


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
    transaction_id, iva_category = _validate_operator_iva_request(
        transaction_id=transaction_id,
        classification=classification,
        file=file,
        iva_category=iva_category,
    )

    derivation = run_ledger_operator_iva(
        ctx,
        transaction_id=transaction_id,
        iva_category=iva_category.value,
        actor=actor,
    )
    if derivation.outcome == "validation_error":
        raise bad(tr("cli.ledger.errors.command_input_invalid", details="; ".join(derivation.validation_messages)))
    if not derivation.derivable:
        raise bad(
            tr("cli.ledger.classify.derive_non_derivable", category=derivation.iva_category, note=derivation.note)
        )
    _emit_operator_iva_result(ctx, derivation=derivation)


def _matches_llm_review(
    projection: LedgerLlmReviewProjection,
    profile_id: UUID,
    request: LedgerLlmReviewRequest,
    mode: Literal["classification", "saturated", "auto_split"],
) -> bool:
    """Correlate review identity, suggestion kind, and required suggestion data."""
    suggestion = projection.suggestion
    expected_kind = "split" if mode == "auto_split" else mode
    return not (
        projection.profile_id != profile_id
        or not suggestion.transaction_id.startswith(request.transaction_id)
        or suggestion.kind != expected_kind
        or (mode == "auto_split" and not suggestion.children)
        or (mode != "auto_split" and (suggestion.classification is None or suggestion.confidence is None))
    )


def _llm_review_preview(
    completed: RegisteredOperationCompletion[LedgerLlmOperationResult],
    reviewed: LedgerLlmReviewProjection | None,
    profile_id: UUID,
    matches: Callable[[LedgerLlmReviewProjection], bool],
) -> LedgerLlmReviewProjection:
    """Admit a nonpersisted preview only when proposal and receipt agree."""
    result = completed.projection
    preview = result.preview
    if (
        _invalid_llm_preview_receipt(completed, reviewed, profile_id)
        or preview is None
        or not matches(preview)
        or result.transaction_id != preview.suggestion.transaction_id
        or (result.reviewed_proposal_digest != preview.reviewed_proposal_digest)
        or (result.provenance != preview.suggestion.provenance)
    ):
        raise invalid_completion_error(completed)
    return preview


def _invalid_llm_preview_receipt(
    completed: RegisteredOperationCompletion[LedgerLlmOperationResult],
    reviewed: LedgerLlmReviewProjection | None,
    profile_id: UUID,
) -> bool:
    """Require an unreviewed, unchanged, successful preview receipt."""
    result = completed.projection
    return (
        reviewed is not None
        or result.outcome != "preview"
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or (completed.effect is not OperationEffect.NONE)
        or (completed.refusal_code is not None)
        or (result.profile_id != profile_id)
    )


def _expected_llm_review_outcome(
    mode: Literal["classification", "saturated", "auto_split"], reject: bool, reviewed: LedgerLlmReviewProjection | None
) -> str:
    """Derive the settled outcome from the explicit decision and reviewed child count."""
    return (
        "rejected"
        if reject
        else "split"
        if mode == "auto_split" and reviewed is not None and (len(reviewed.suggestion.children) > 1)
        else "classified"
    )


def _expected_llm_review_effect(result: LedgerLlmOperationResult) -> OperationEffect:
    """Keep an already classified result without event writes unchanged."""
    return (
        OperationEffect.NONE
        if result.outcome == "classified"
        and result.classification is not None
        and (not result.classification.bucket_event_ids)
        else OperationEffect.UPDATED
    )


def _invalid_llm_settled_receipt(
    completed: RegisteredOperationCompletion[LedgerLlmOperationResult],
    apply: bool,
    reject: bool,
    expected_effect: OperationEffect,
    profile_id: UUID,
) -> bool:
    """Correlate an explicit review decision with its terminal receipt."""
    result = completed.projection
    return (
        not (apply or reject)
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or (completed.effect is not expected_effect)
        or (result.profile_id != profile_id)
    )


def _invalid_llm_review_proposal(result: LedgerLlmOperationResult, reviewed: LedgerLlmReviewProjection) -> bool:
    """Require the exact reviewed digest, transaction, and provenance."""
    return (
        result.reviewed_proposal_digest != reviewed.reviewed_proposal_digest
        or result.transaction_id != reviewed.suggestion.transaction_id
        or result.provenance != reviewed.suggestion.provenance
    )


def _llm_review_settled(
    completed: RegisteredOperationCompletion[LedgerLlmOperationResult],
    reviewed: LedgerLlmReviewProjection | None,
    profile_id: UUID,
    mode: Literal["classification", "saturated", "auto_split"],
    apply: bool,
    reject: bool,
) -> LedgerLlmOperationResult:
    """Admit only the settled result of the exact reviewed proposal."""
    result = completed.projection
    expected_outcome = _expected_llm_review_outcome(mode, reject, reviewed)
    expected_effect = _expected_llm_review_effect(result)
    if (
        reviewed is None
        or _invalid_llm_settled_receipt(completed, apply, reject, expected_effect, profile_id)
        or _invalid_llm_review_proposal(result, reviewed)
        or result.outcome != expected_outcome
        or (result.classification is not None and result.classification.profile_id != profile_id)
        or (result.outcome == "split" and len(result.child_transaction_ids) != len(reviewed.suggestion.children))
    ):
        raise invalid_completion_error(completed)
    return result
