"""Typed vocabulary for the one ledger LLM review workflow.

The ledger LLM classify surface exposes several operator intents — suggest,
apply, saturate-and-apply, reject, and evidence-driven split — whose durable
writes are owned by the canonical ledger persistence primitives in
:mod:`~application.ledger._llm_classification`. Historically each primitive
accepted a free-text ``source_command`` keyword defaulting to a CLI spelling
(``"aeat app ledger classify --llm --reject"`` and siblings) *inside application
code*, so audit provenance could silently default to a command string the
application layer should not know or own.

This module defines the typed spine that removes that default: a mandatory
:class:`LlmReviewInvocationOrigin` (the operator intent), the
:class:`LlmReviewDecision` terminals, and the :class:`LlmReviewRequest`
envelope. The canonical CLI ``source_command`` spelling is *derived* from the
origin (:attr:`LlmReviewInvocationOrigin.source_command`), never defaulted in an
application function signature — so a caller must always name its origin and the
audit label follows from it. ``classify --auto-split`` and ``split --llm`` share
this vocabulary while retaining distinct origins.

The review workflow that consumes this vocabulary and delegates to the ledger
persistence authorities is built on top of these types.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.buckets import BucketEventHistoryRepositoryProtocol
from ...domain.transactions import (
    TransactionCatalogueRepositoryProtocol,
    TransactionValidationError,
)
from ._llm_classification import (
    apply_evidence_split,
    apply_llm_classification,
    apply_saturated_llm_classification,
    reject_llm_suggestion,
)
from ._llm_suggestions import (
    LLMClassificationSuggestion,
    LLMSaturatedSuggestion,
    LLMSplitApplyResult,
    LLMSplitSuggestion,
    LLMSuggestionRejectionResult,
    OperatorIvaDerivationResult,
)
from ._models import ManualLedgerTransactionResult

if TYPE_CHECKING:
    from datetime import datetime


class LlmReviewInvocationOrigin(StrEnum):
    """Mandatory provenance for one ledger LLM review invocation.

    Each member is a distinct operator intent routed into the shared review
    workflow. The member value is a stable, CLI-spelling-independent token; the
    human-facing ``source_command`` audit label is derived from the member via
    :attr:`source_command`, so application code never carries a defaulted CLI
    string. ``CLASSIFY_AUTO_SPLIT`` and ``SPLIT_LLM`` are deliberately distinct
    origins for the two CLI routes that share the split workflow.
    """

    CLASSIFY_LLM_APPLY = "classify_llm_apply"
    CLASSIFY_LLM_REJECT = "classify_llm_reject"
    CLASSIFY_LLM_SATURATE_APPLY = "classify_llm_saturate_apply"
    CLASSIFY_IVA_CATEGORY_SATURATE = "classify_iva_category_saturate"
    CLASSIFY_AUTO_SPLIT = "classify_auto_split"
    SPLIT_LLM = "split_llm"

    @property
    def source_command(self) -> str:
        """Return the canonical operator-facing CLI ``source_command`` audit label.

        The mapping is total over the enum: a new origin without a spelling
        raises :class:`KeyError` at first use, so the audit label can never be
        silently blank.
        """
        return _ORIGIN_SOURCE_COMMANDS[self]


_ORIGIN_SOURCE_COMMANDS: dict[LlmReviewInvocationOrigin, str] = {
    LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY: "aeat app ledger classify --llm --apply",
    LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT: "aeat app ledger classify --llm --reject",
    LlmReviewInvocationOrigin.CLASSIFY_LLM_SATURATE_APPLY: "aeat app ledger classify --llm --saturate --apply",
    LlmReviewInvocationOrigin.CLASSIFY_IVA_CATEGORY_SATURATE: "aeat app ledger classify --iva-category --saturate",
    LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT: "aeat app ledger classify --read-evidence --auto-split --apply",
    LlmReviewInvocationOrigin.SPLIT_LLM: "aeat app ledger split --llm",
}


class LlmReviewDecision(StrEnum):
    """The terminal decision an operator reaches on an LLM review subject.

    ``SUGGEST`` is the non-persisting preview; ``APPLY`` approves and writes;
    ``REJECT`` records an audit-trailed decline that mutates nothing; ``SPLIT``
    and ``NO_SPLIT`` are the evidence-driven split verdicts.
    """

    SUGGEST = "suggest"
    APPLY = "apply"
    REJECT = "reject"
    SPLIT = "split"
    NO_SPLIT = "no_split"


class LlmReviewRequest(BaseModel):
    """One typed ledger LLM review invocation.

    Carries the mandatory :class:`LlmReviewInvocationOrigin` (there is no
    default), the target transaction, the operator identity, and the decision
    terminal. The durable ``source_command`` audit label is read from
    ``invocation_origin.source_command`` when the workflow delegates to a ledger
    persistence primitive, so provenance is always operator-named, never an
    application-layer default.
    """

    model_config = _STRICT_FROZEN

    invocation_origin: LlmReviewInvocationOrigin
    decision: LlmReviewDecision
    bucket_id: str = Field(min_length=1)
    transaction_id: str = Field(min_length=1)
    actor: str = Field(default="operator", min_length=1)
    reason: str = ""

    @property
    def source_command(self) -> str:
        """Derived audit label for the durable event, from the invocation origin."""
        return self.invocation_origin.source_command


# The durable outcome vocabulary the review workflow returns. Each is an already
# canonical ledger result owned by its persistence primitive; naming the union
# here keeps the workflow's return contract in one place. Non-persisting suggest
# previews (the ``*Suggestion`` models) are inputs to a later decision, not
# terminal results, so they are deliberately excluded.
type LlmReviewResult = (
    ManualLedgerTransactionResult | LLMSuggestionRejectionResult | LLMSplitApplyResult | OperatorIvaDerivationResult
)

type ReviewedSuggestion = LLMClassificationSuggestion | LLMSaturatedSuggestion | LLMSplitSuggestion


def execute_reviewed_decision(
    suggestion: ReviewedSuggestion,
    *,
    origin: LlmReviewInvocationOrigin,
    decision: LlmReviewDecision,
    bucket_id: str,
    business_pct: Decimal | None = None,
    reason: str = "",
    actor: str = "operator",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> LlmReviewResult:
    """Route one reviewed LLM suggestion to its canonical persistence authority.

    This is the single persisting decision terminal of the review workflow. It
    introduces no write path: each branch delegates to the existing canonical
    ledger primitive (:func:`~application.ledger._llm_classification.apply_llm_classification`,
    :func:`apply_saturated_llm_classification`, :func:`apply_evidence_split`,
    :func:`reject_llm_suggestion`), and the durable ``source_command`` audit
    label is derived from the mandatory ``origin`` rather than defaulted inside
    application code.

    ``SUGGEST`` and ``NO_SPLIT`` are non-persisting terminals (a preview and a
    decline-to-split verdict): they never reach this dispatch and raise if
    passed. A ``decision``/``suggestion`` shape mismatch (e.g. ``SPLIT`` on a
    non-split suggestion) raises :class:`TransactionValidationError`.
    """
    source_command = origin.source_command

    if decision is LlmReviewDecision.REJECT:
        return reject_llm_suggestion(
            suggestion,
            bucket_id=bucket_id,
            reason=reason,
            actor=actor,
            source_command=source_command,
            transaction_repository=transaction_repository,
            bucket_event_repository=bucket_event_repository,
            occurred_at=occurred_at,
        )

    if decision is LlmReviewDecision.APPLY:
        if isinstance(suggestion, LLMSaturatedSuggestion):
            return apply_saturated_llm_classification(
                suggestion,
                bucket_id=bucket_id,
                business_pct=business_pct,
                actor=actor,
                source_command=source_command,
                transaction_repository=transaction_repository,
                bucket_event_repository=bucket_event_repository,
                occurred_at=occurred_at,
            )
        if isinstance(suggestion, LLMClassificationSuggestion):
            return apply_llm_classification(
                suggestion,
                bucket_id=bucket_id,
                business_pct=business_pct,
                actor=actor,
                source_command=source_command,
                transaction_repository=transaction_repository,
                bucket_event_repository=bucket_event_repository,
                occurred_at=occurred_at,
            )
        raise TransactionValidationError(
            "APPLY decision requires a classification or saturated suggestion, not a split proposal",
            context={"decision": decision.value, "origin": origin.value},
        )

    if decision is LlmReviewDecision.SPLIT:
        if isinstance(suggestion, LLMSplitSuggestion):
            return apply_evidence_split(
                suggestion,
                bucket_id=bucket_id,
                actor=actor,
                source_command=source_command,
                transaction_repository=transaction_repository,
                bucket_event_repository=bucket_event_repository,
                occurred_at=occurred_at,
            )
        raise TransactionValidationError(
            "SPLIT decision requires an evidence split proposal",
            context={"decision": decision.value, "origin": origin.value},
        )

    raise TransactionValidationError(
        f"{decision.value} is a non-persisting review terminal and cannot be executed as a durable decision",
        context={"decision": decision.value, "origin": origin.value},
    )


__all__ = [
    "LlmReviewDecision",
    "LlmReviewInvocationOrigin",
    "LlmReviewRequest",
    "LlmReviewResult",
    "ReviewedSuggestion",
    "execute_reviewed_decision",
]
