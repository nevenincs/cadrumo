"""Propose and apply evidence-backed transaction splits."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.config import Settings
from ...core.logging import get_logger
from ...domain.categories.spending_category import SpendingCategory
from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.errors import TransactionNotFoundError, TransactionValidationError
from ...domain.transactions.llm import (
    LLMSplitChild,
    LLMSplitProposer,
    LLMSplitResponse,
    prompt_spec_with_saturation_fields,
)
from ...domain.transactions.models import Transaction
from .action_ports import LedgerActionPorts
from .actions_common import (
    resolve_transaction_repository,
)
from .actions_split_merge import split_transaction_with_classified_children
from .evidence_split import derive_child_amounts
from .llm_classification import (
    derive_iva_substrate,
    effective_ledger_date,
    evidence_text_and_reference,
    load_llm_transaction,
    resolve_requested_llm_evidence,
)
from .llm_classification_ports import (
    LLMClassificationPorts,
    LLMSplitApplyResult,
    LLMSplitChildSuggestion,
    LLMSplitSuggestion,
    VisionClassifier,
)
from .llm_evidence import split_with_evidence
from .models import ManualLedgerTransactionPatch, SplitChildCommand
from .protocols import TransactionCatalogueCoCommitWriterProtocol

_logger = get_logger(__name__)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


# The CLI binary each subprocess provider shells out to. Used by


def _split_child_description(child_index: int, *, citation: str, category: SpendingCategory | None) -> str:
    """Build a distinct, operator-facing description for one split child.

    The 1-based ordinal prefix guarantees distinct child descriptions (hence
    distinct split-child ids) even when two children share an amount and a
    category; the label prefers the model's evidence citation, then the expense
    category, then a neutral fallback.
    """
    label = citation.strip() or (category.value if category is not None else "línea")
    return f"{child_index + 1}. {label}"


def _split_child_iva_values(
    child: LLMSplitChild,
    *,
    amount: Decimal,
    on_date: date,
    operation: PinnedAuthorityOperation,
) -> tuple[Decimal | None, Decimal | None, Decimal | None, bool, str]:
    """Derive one split child's optional IVA substrate."""
    if child.iva_category is None:
        return None, None, None, False, ""
    return derive_iva_substrate(child.iva_category, gross=amount, on_date=on_date, operation=operation)


def _build_split_child_suggestion(
    child: LLMSplitChild,
    *,
    index: int,
    amount: Decimal,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> LLMSplitChildSuggestion:
    """Materialize one model child with system-derived amounts and tax values."""
    iva_rate, taxable_base, iva_amount, rate_derivable, derivation_note = _split_child_iva_values(
        child,
        amount=amount,
        on_date=effective_date,
        operation=operation,
    )
    return LLMSplitChildSuggestion(
        proportion=child.proportion,
        amount=amount,
        description=_split_child_description(index, citation=child.evidence_citation, category=child.category),
        category=child.category,
        iva_category=child.iva_category,
        iva_rate=iva_rate,
        taxable_base=taxable_base,
        iva_amount=iva_amount,
        rate_derivable=rate_derivable,
        derivation_note=derivation_note,
        evidence_citation=child.evidence_citation,
    )


def _materialize_split_children(
    response: LLMSplitResponse,
    *,
    transaction: Transaction,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> list[LLMSplitChildSuggestion]:
    """Derive exact child amounts and materialize them in model order."""
    proportions = tuple(child.proportion for child in response.children)
    amounts = derive_child_amounts(transaction.raw.amount, proportions)
    children: list[LLMSplitChildSuggestion] = []
    for index, (child, amount) in enumerate(zip(response.children, amounts, strict=True)):
        children.append(
            _build_split_child_suggestion(
                child,
                index=index,
                amount=amount,
                effective_date=effective_date,
                operation=operation,
            ),
        )
    return children


def suggest_evidence_split(
    *,
    bucket_id: str,
    transaction_id: str,
    operation: PinnedAuthorityOperation,
    proposer: LLMSplitProposer | None = None,
    vision_classifier: VisionClassifier | None = None,
    transaction_repository: TransactionCatalogueCoCommitWriterProtocol,
    on_date: date | None = None,
    read_evidence: bool = True,
    settings: Settings,
    ports: LLMClassificationPorts,
    reviewed_transaction: Transaction | None = None,
) -> LLMSplitSuggestion:
    """Propose an evidence-driven N-way split for one transaction.

    Loads the transaction, runs the injected proposer (default-resolved with
    the saturation prompt spec) over the optional on-host evidence text,
    DERIVES each child's euro amount from the parent gross and the model's
    proportion (summing exactly to the parent), and DERIVES each child's
    regulated tax substrate from the registry rate for the model-selected IVA
    category. **Persists nothing** — this is the suggest step.

    Args:
        bucket_id: Active profile bucket id.
        transaction_id: Stable id of the transaction to split.
        operation: Generation-pinned authority operation for the prompt's
            dated category and IVA projections.
        proposer: Injected split proposer (dependency injection for tests). The
            agent's vision-transcription reader is the default, so an injected
            proposer is the only non-default case.
        vision_classifier: Injected vision classifier used when the evidence is
            a scan-only PDF or image; default-resolved otherwise.
        transaction_repository: Injected catalogue repository.
        on_date: Effective date used to resolve each child's registry rate;
            defaults to the transaction's value date (or booked date).
        read_evidence: When True (default for splitting), resolve the
            transaction's linked evidence, extract its text on-host, and inject it
            into the prompt.
        settings: Injected settings; defaults to ``load_settings()``.
        ports: Injected evidence-reading and classifier execution ports.
        reviewed_transaction: Immutable caller-captured parent used instead of
            reloading the catalogue before provider work; its id must match.

    Returns:
        A :class:`~application.ledger.llm_classification_ports.LLMSplitSuggestion`
        whose child amounts sum exactly to the parent.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        LLMClassifierError: When the proposer fails (provider CLI unavailable,
            hallucinated out-of-allow-list value, or a malformed split response).
    """
    _, transaction = load_llm_transaction(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        transaction_repository=transaction_repository,
        reviewed_transaction=reviewed_transaction,
    )
    resolved_settings = settings
    resolved_proposer = proposer
    evidence = resolve_requested_llm_evidence(
        transaction,
        bucket_id=bucket_id,
        settings=resolved_settings,
        ports=ports,
        read_evidence=read_evidence,
    )
    response, provenance = split_with_evidence(
        transaction,
        evidence,
        proposer=resolved_proposer,
        spec=prompt_spec_with_saturation_fields(
            year=transaction.raw.booked_date.year,
            operation=operation,
        ),
        vision_classifier=vision_classifier,
        settings=resolved_settings,
        ports=ports,
    )
    _, evidence_reference = evidence_text_and_reference(evidence)
    effective_date = effective_ledger_date(transaction, on_date)
    children = _materialize_split_children(
        response,
        transaction=transaction,
        effective_date=effective_date,
        operation=operation,
    )
    _logger.info(
        "llm split suggest: provider=%s children=%d",
        provenance,
        len(children),
    )
    return LLMSplitSuggestion(
        transaction_id=transaction_id,
        provenance=provenance,
        reason=response.reason,
        parent_amount=transaction.raw.amount,
        children=tuple(children),
        evidence_id=evidence_reference,
    )


def _split_child_patch_fields(child: LLMSplitChildSuggestion, *, evidence_link: dict[str, object]) -> dict[str, object]:
    """Build the classification patch fields for one evidence-split child.

    Assembles the ``BUSINESS`` classification, the inherited evidence link, and
    the model-selected category / IVA substrate (the euro figures only when the
    category was registry-derivable). Shared by the atomic split writer's
    per-child classification so the split and no-split paths stamp identical
    fields.
    """
    patch_fields: dict[str, object] = {
        "business_classification": BusinessClassification.BUSINESS,
        **evidence_link,
    }
    if child.category is not None:
        patch_fields["category_id"] = child.category.value
    if child.iva_category is not None:
        patch_fields["iva_category"] = child.iva_category
    if child.rate_derivable:
        patch_fields["taxable_base"] = child.taxable_base
        patch_fields["iva_rate"] = child.iva_rate
        patch_fields["iva_amount"] = child.iva_amount
    return patch_fields


def apply_evidence_split(
    suggestion: LLMSplitSuggestion,
    *,
    bucket_id: str,
    actor: str = "operator",
    source_command: str,
    ports: LedgerActionPorts,
    occurred_at: datetime | None = None,
    expected_current: Transaction | None = None,
) -> LLMSplitApplyResult:
    """Apply a reviewed evidence-driven split through the single-writer split path.

    Delegates the whole mutation to the established single writer rather than
    re-implementing it: :func:`split_transaction_with_classified_children`
    redistributes the parent into children whose magnitudes sum exactly to the
    parent and stamps each child's model-selected expense and IVA category, the
    registry-DERIVED regulated numbers, the parent's inherited evidence link, and
    the ``llm:<model>`` provenance. This function only translates the reviewed
    suggestion into that writer's arguments; it performs no write of its own and
    no follow-up per-child field patch.

    Because the writer persists the parent transition, every classified child, and
    all bucket events in one transaction, a child can never come to rest split but
    unclassified or missing its evidence link. The writer enforces
    children-sum-to-parent, the non-negative-magnitude invariant, and
    ``gross == taxable_base + iva_amount`` per child. The LLM never supplies a
    persisted euro amount or regulated number.

    Args:
        suggestion: The accepted
            :class:`~application.ledger.llm_classification_ports.LLMSplitSuggestion`.
        bucket_id: Active profile bucket id.
        actor: Operator identity for the audit events.
        source_command: Source-command label recording the operator's verb.
        ports: Injected ledger action ports for the catalogue and audit-event
            repositories.
        occurred_at: Override clock for deterministic tests.
        expected_current: Immutable parent reviewed before provider work.

    Returns:
        An :class:`~application.ledger.llm_classification_ports.LLMSplitApplyResult`
        naming the split group and its children.

    Raises:
        TransactionNotFoundError: When the parent transaction id is unknown.
        TransactionValidationError: When the split invariants are violated.
    """
    if not suggestion.recommends_split:
        # A single-child suggestion is the no-split verdict; applying it as a
        # one-way split is degenerate. The CLI routes this to single-transaction
        # classification instead — never here.
        raise TransactionValidationError(
            "this proposal is a no-split verdict (one line); classify the transaction instead of splitting it",
            context={"transaction_id": suggestion.transaction_id, "child_count": len(suggestion.children)},
        )
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=ports.transaction_repository)
    parent = repository.load().get(suggestion.transaction_id)
    if parent is None:
        raise TransactionNotFoundError(
            translated_message="application.ledger.errors.transaction_not_found",
            context={"transaction_id": suggestion.transaction_id},
        )

    commands = tuple(
        SplitChildCommand(amount=child.amount, description=child.description) for child in suggestion.children
    )

    # Every split child inherits the parent's validated evidence link.
    evidence_link: dict[str, object] = {}
    if parent.purchase_invoice_evidence_id is not None:
        evidence_link["purchase_invoice_evidence_id"] = parent.purchase_invoice_evidence_id
    elif parent.attachment_ids:
        evidence_link["attachment_ids"] = parent.attachment_ids

    child_classifications = tuple(
        ManualLedgerTransactionPatch.model_validate(_split_child_patch_fields(child, evidence_link=evidence_link))
        for child in suggestion.children
    )

    # One atomic transaction: parent transition + every classified,
    # evidence-bearing child + all events persist together, or nothing does.
    # No generic field patch re-enters evidence after the split.
    split_result = split_transaction_with_classified_children(
        bucket_id=bucket_id,
        transaction_id=suggestion.transaction_id,
        children=commands,
        child_classifications=child_classifications,
        classified_by=suggestion.provenance,
        actor=actor,
        source_command=source_command,
        reason=suggestion.reason,
        ports=ports,
        occurred_at=occurred_at,
        expected_current=expected_current,
    )
    classified = len(split_result.child_transactions)

    _logger.info(
        "llm split apply: children=%d classified=%d classified_by=%s",
        len(split_result.child_transaction_ids),
        classified,
        suggestion.provenance,
    )
    return LLMSplitApplyResult(
        bucket_id=bucket_id,
        parent_transaction_id=split_result.parent_transaction_id,
        split_group_id=split_result.split_group_id,
        child_transaction_ids=split_result.child_transaction_ids,
        provenance=suggestion.provenance,
        classified_child_count=classified,
    )
