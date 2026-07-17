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

from enum import StrEnum

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ._llm_suggestions import (
    LLMSplitApplyResult,
    LLMSuggestionRejectionResult,
    OperatorIvaDerivationResult,
)
from ._models import ManualLedgerTransactionResult


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
    ManualLedgerTransactionResult
    | LLMSuggestionRejectionResult
    | LLMSplitApplyResult
    | OperatorIvaDerivationResult
)


__all__ = [
    "LlmReviewDecision",
    "LlmReviewInvocationOrigin",
    "LlmReviewRequest",
    "LlmReviewResult",
]
