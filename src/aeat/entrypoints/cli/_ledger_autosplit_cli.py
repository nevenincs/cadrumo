"""Evidence-driven auto-split routing for ``aeat app ledger classify --auto-split``.

Extracted from ``_ledger.py`` (SPLIT-CANDIDATE) so the ledger command module
stays within its size budget. The router makes one model call — the split
proposer — and routes on its verdict: a multi-child verdict drives the
evidence-driven split (per-line base/IVA children), a single-child "no split"
verdict classifies the transaction in place from that lone child's selections.
The model emits no euro amount or regulated number; the registry derives every
child's base and IVA (``llm-selects-system-derives-tax-numbers``).

Also owns :func:`split_recommendation_notice`, the typed ``info`` notice that
``classify --read-evidence`` emits when the model flags the invoice as
multi-component (``cli-notices-are-the-only-diagnostic-channel``).
"""

from __future__ import annotations

import typer
from pydantic import BaseModel, ValidationError

from ...application.ledger import (
    LLMProvider,
    LLMSplitSuggestion,
    apply_evidence_classification,
    apply_evidence_split,
    is_llm_provider_available,
    ledger_transaction_payload,
    ledger_transaction_review_status,
    suggest_evidence_split,
)
from ...core import resolve_active_bucket_id
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.transactions import (
    BusinessClassification,
    LLMClassifierError,
    TransactionValidationError,
)
from ._common import _bad, _emit_envelope, _state, _tx_repo
from ._ledger_support import _ledger_validation_bad, _resolve_id

__all__ = ["dispatch_autosplit", "split_recommendation_notice"]


def split_recommendation_notice(transaction_id: str, *, provider: LLMProvider | None) -> Notice:
    """Build the typed ``info`` notice recommending an evidence-driven split.

    Fired when the evidence read judged the invoice multi-component. The
    ``suggestion`` is the exact runnable command that actions the split, preserving
    the provider the operator used (``cli-notices-are-the-only-diagnostic-channel``;
    the recommendation rides the Notice channel, never a bespoke result field).
    """
    provider_flag = f" --llm {provider.value}" if provider is not None else ""
    command = (
        f"aeat app ledger classify {transaction_id} "
        f"--read-evidence --saturate --auto-split --apply{provider_flag}"
    )
    return Notice(
        severity=NoticeSeverity.INFO,
        code="ledger.classify.split_recommended",
        message=tr(
            "cli.ledger.classify.split_recommended_message",
            default=(
                "The attached invoice appears to carry multiple rate or category lines. "
                "Re-run with --auto-split to separate them into independently-filable "
                "base and IVA children."
            ),
        ),
        suggestion=command,
        context={"transaction_id": transaction_id, "source": "evidence_read"},
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
    from_csv: str | None,
    provider: LLMProvider | None,
    apply: bool,
    actor: str | None,
    read_evidence: bool,
    evidence_acknowledged: bool,
    vision_model: str | None,
) -> None:
    """Route ``classify --read-evidence --auto-split`` on the model's split verdict.

    One model call — the split proposer — yields the verdict. A multi-child verdict
    drives the evidence-driven split (preview, or with ``--apply`` the
    base/IVA-separating split); a single-child "no split" verdict classifies the
    transaction in place from that child's selections (preview, or with ``--apply``
    the in-place write). The model emits no euro amount or regulated number; the
    registry derives every child's base and IVA.
    """
    from ._ledger_payloads import LedgerClassifyLlmSuggestResult, LedgerClassifySingleResult

    if not read_evidence:
        raise _bad(
            tr(
                "cli.ledger.classify.auto_split_needs_evidence",
                default="--auto-split requires --read-evidence: the split decision is read from the invoice.",
            ),
        )
    if classification is not None or from_csv is not None:
        raise _bad(
            tr(
                "cli.ledger.classify.llm_exclusive",
                default="--llm cannot be combined with --classification or --from-csv; "
                "the manual path is the explicit operator override.",
            ),
        )
    if transaction_id is None:
        raise _bad(
            tr(
                "cli.ledger.classify.id_required",
                default="A transaction id is required when --from-csv is not provided.",
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
            read_evidence=True,
            evidence_acknowledged=evidence_acknowledged,
            vision_model=vision_model,
        )
    except LLMClassifierError as exc:
        raise _bad(
            tr("cli.ledger.classify.llm_failed", reason=str(exc), default=f"LLM split proposal failed: {exc}"),
        ) from exc

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
                "provider": suggestion.provider.value if suggestion.provider is not None else None,
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
        _emit_envelope(ctx, command="ledger.split", result=result, lines=lines)
        return
    try:
        applied = apply_evidence_split(
            suggestion,
            bucket_id=bucket_id,
            actor=actor or resolve_active_bucket_id() or "operator",
        )
    except TransactionValidationError as exc:
        raise _bad(str(exc)) from exc
    except ValidationError as exc:
        raise _ledger_validation_bad(exc) from exc
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
    _emit_envelope(ctx, command="ledger.split", result=result, lines=lines)


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
                "provider": suggestion.provider.value if suggestion.provider is not None else "local-vision",
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
        _emit_envelope(ctx, command="ledger.classify", result=suggest_result, lines=lines)
        return
    try:
        result = apply_evidence_classification(
            suggestion,
            bucket_id=bucket_id,
            actor=actor or resolve_active_bucket_id() or "operator",
        )
    except TransactionValidationError as exc:
        raise _bad(str(exc)) from exc
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
    _emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)
