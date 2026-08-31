"""Typed vocabulary for the one ledger LLM review workflow.

The ledger LLM classify surface exposes several operator intents — suggest,
apply, saturate-and-apply, reject, and evidence-driven split — whose durable
writes are owned by the canonical ledger persistence primitives in
:mod:`~application.ledger.llm_classification`. Historically each primitive
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

from ...core.config import Settings, load_settings
from ...core.identity import BucketId, TransactionId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time import now
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...llm.suggestions import (
    LLMClassificationSuggestion,
    LLMSaturatedSuggestion,
    LLMSplitApplyResult,
    LLMSplitSuggestion,
    LLMSuggestionRejectionResult,
    OperatorIvaDerivationResult,
)
from .extraction_draft_store import ExtractionDraftDocument, write_extraction_draft
from .invoice_draft_records import InvoiceDraft
from .llm_classification import (
    apply_evidence_split,
    apply_llm_classification,
    apply_saturated_llm_classification,
    reject_llm_suggestion,
)
from .models import ManualLedgerTransactionResult

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
    bucket_id: BucketId
    transaction_id: TransactionId
    actor: str = Field(default="operator", min_length=1)
    reason: str = ""

    @property
    def source_command(self) -> str:
        """Derived audit label for the durable event, from the invocation origin."""
        return self.invocation_origin.source_command


class ReviewedInvoiceDraft(BaseModel):
    """A read invoice draft awaiting the operator's apply-or-decline.

    **Carries no confidence, and that is the point.** Its three sibling
    suggestion models each require a ``Decimal`` confidence, and the ingestion
    decision forbids a numeric confidence anywhere in this chain: a model's
    self-assessed certainty is not evidence, and a number beside a field invites
    an operator to treat one reading as more checked than another when nothing
    checked either. The prohibition is load-bearing rather than stylistic, so
    the subject type is confidence-free by construction instead of carrying the
    field and leaving it unset.

    Keyed by the evidence it was read from rather than by a transaction. A draft
    exists before any ledger row does -- that is what the operator is deciding
    about -- so requiring a transaction id here would be requiring the answer to
    the question under review.

    Attributes:
        evidence_reference: The evidence or attachment id the draft was read
            from, and the key its store is addressed by.
        draft: The proposed fields, exactly as the reader produced them.
        extractor: Which reader produced it.
        read_transports: Every transport that carried the reading, so a
            withdrawal can classify what an apply persists.
        provenance: The reader's own stamp, carried for the audit trail.
    """

    model_config = _STRICT_FROZEN

    evidence_reference: str = Field(min_length=1)
    draft: InvoiceDraft
    extractor: str = Field(min_length=1)
    read_transports: tuple[str, ...] = ()
    provenance: str = Field(min_length=1)


class InvoiceDraftDeclineResult(BaseModel):
    """The durable trace of an operator declining a read draft.

    Distinct from :class:`LLMSuggestionRejectionResult`, which is keyed by the
    transaction its suggestion targeted. A declined draft has no transaction --
    that is what was not created -- so reusing that shape would have required
    inventing one.

    Attributes:
        bucket_id: The profile bucket the decision was taken in.
        evidence_reference: Which read was declined.
        bucket_event_id: The audit event this decline emitted.
        provenance: The reader stamp of the declined draft.
        operator_reason: What the operator said, when they said anything.
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    evidence_reference: str = Field(min_length=1)
    bucket_event_id: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    operator_reason: str = ""


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
    | ExtractionDraftDocument
    | InvoiceDraftDeclineResult
)

type ReviewedSuggestion = (
    LLMClassificationSuggestion | LLMSaturatedSuggestion | LLMSplitSuggestion | ReviewedInvoiceDraft
)


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
    settings: Settings | None = None,
) -> LlmReviewResult:
    """Route one reviewed LLM suggestion to its canonical persistence authority.

    This is the single persisting decision terminal of the review workflow. It
    introduces no write path: each branch delegates to the existing canonical
    ledger primitive (:func:`~application.ledger.llm_classification.apply_llm_classification`,
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
        # The split lives HERE, inside the reject branch, rather than as a second
        # handler beside it. This branch runs before any type dispatch and
        # currently catches every reject, so a draft decline added alongside it
        # would never be reached -- and a parallel reject path is exactly the
        # duplicate write surface this terminal exists to avoid.
        if isinstance(suggestion, ReviewedInvoiceDraft):
            return _decline_invoice_draft(
                suggestion,
                bucket_id=bucket_id,
                reason=reason,
                actor=actor,
                bucket_event_repository=bucket_event_repository,
                occurred_at=occurred_at,
            )
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
        if isinstance(suggestion, ReviewedInvoiceDraft):
            # Delegates to the draft store's single writer rather than opening a
            # second path to the same record: that store is keyed by bucket and
            # evidence reference so a correction updates the review in place,
            # and a parallel writer would fork a second draft for one document.
            return write_extraction_draft(
                bucket_id=bucket_id,
                evidence_reference=suggestion.evidence_reference,
                draft=suggestion.draft,
                extractor=suggestion.extractor,
                read_transports=suggestion.read_transports,
                settings=settings if settings is not None else load_settings(),
            )
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


def _decline_invoice_draft(
    suggestion: ReviewedInvoiceDraft,
    *,
    bucket_id: str,
    reason: str,
    actor: str,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None,
    occurred_at: datetime | None,
) -> InvoiceDraftDeclineResult:
    """Record a declined draft as an audit event, writing no draft.

    **The draft is deliberately not written back.** Storing it unchanged would
    make a decline indistinguishable from a re-read that happened to come out
    the same: both would leave one stored draft with a fresh timestamp, and the
    operator's "no" -- the only thing the decision produced -- would be exactly
    the part not recorded.

    So the trace is the event, scoped to the evidence rather than to a
    transaction, because a declined draft never became one.

    The audit sink is resolved through the ledger's one default-resolution
    helper, the same way every sibling branch of the dispatch above resolves
    its own. Constructing the concrete repository here would both name an
    adapter from the application layer and reproduce the bare
    ``BucketEventHistoryRepository()`` form -- which, unlike the sibling reject
    path, is saved to DIRECTLY here rather than riding a transaction
    repository's secure-write batch, so it would not bind to the operation
    bucket's store at all.
    """
    from ...domain.buckets.event import BucketEventType
    from .actions_common import resolve_bucket_event_repository
    from .evidence import emit_evidence_event as _emit_evidence_event

    event_id = _emit_evidence_event(
        event_repository=resolve_bucket_event_repository(
            bucket_id=bucket_id,
            repository=bucket_event_repository,
        ),
        bucket_id=bucket_id,
        event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_DRAFT_DECLINED,
        evidence_id=suggestion.evidence_reference,
        actor=actor,
        occurred_at=occurred_at or now(),
        payload={"provenance": suggestion.provenance, "operator_reason": reason},
    )
    return InvoiceDraftDeclineResult(
        bucket_id=bucket_id,
        evidence_reference=suggestion.evidence_reference,
        bucket_event_id=event_id,
        provenance=suggestion.provenance,
        operator_reason=reason,
    )
