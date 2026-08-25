"""LLM-classify CLI result payloads (suggest / saturate / reject).

Strict :class:`OutputSchema` subclasses for the
LLM decision terminals, split out of
:mod:`._ledger_payloads` to keep that registry within its
size budget. These nested branch payloads share the graph-declared
:class:`LedgerClassifySingleResult`
``ledger.classify`` command key, and validated instances enter
:class:`SchemaEnvelope` through
:func:`emit_envelope`. They are imported directly
by :mod:`._ledger_llm_cli` rather than re-exported from the
parent payload module.

The application layer owns the suggestion contracts:
:class:`LLMClassificationSuggestion`,
:class:`LLMSaturatedSuggestion`, and
:class:`LLMSuggestionRejectionResult`.  These schemas
only validate the transport payloads emitted while the operator reviews,
applies elsewhere, or rejects a model proposal.
"""

from __future__ import annotations

from ...core.identity import TransactionId
from ...core.json_contract import OutputSchema


class LedgerClassifyLlmSuggestResult(OutputSchema):
    """JSON envelope for the ``aeat app ledger classify --llm`` (no ``--apply``) path (D1).

    Mirrors the review fields from
    :class:`LLMClassificationSuggestion`: model
    provider, transaction id, business/personal classification, optional
    spending category, confidence, reason, and ``llm:<model>`` provenance.
    The proposed decision is surfaced for operator review; nothing is
    persisted (``persisted`` is ``False``) until the operator re-runs with
    ``--apply``. That apply branch calls
    :func:`apply_llm_classification` and emits the
    normal
    :class:`LedgerClassifySingleResult`
    because persistence then follows the shared manual-classification write.
    """

    llm: bool
    provider: str
    transaction_id: TransactionId
    classification: str | None = None
    category: str | None = None
    confidence: str | None = None
    reason: str | None = None
    provenance: str | None = None
    persisted: bool = False


class LedgerClassifyLlmSaturateResult(OutputSchema):
    """JSON envelope for the ``aeat app ledger classify --llm --saturate`` path (D1).

    Mirrors :class:`LLMSaturatedSuggestion`, extending
    the stage-1 review fields with the model-selected IVA category plus the
    system-derived euro substrate. The model never supplies ``iva_rate``,
    ``taxable_base``, or ``iva_amount``; those values are derived by the
    :func:`saturate_llm_classification` path through
    :func:`derive_operator_iva_substrate` when
    ``rate_derivable`` is true. Otherwise ``derivation_note`` explains why the
    operator must complete them.
    """

    llm: bool
    provider: str
    transaction_id: TransactionId
    # Stage-1 classification decision carried alongside the saturated substrate.
    classification: str | None = None
    category: str | None = None
    confidence: str | None = None
    reason: str | None = None
    provenance: str | None = None
    # Saturated IVA substrate (system-derived from the registry).
    iva_category: str | None = None
    iva_rate: str | None = None
    taxable_base: str | None = None
    iva_amount: str | None = None
    rate_derivable: bool | None = None
    derivation_note: str | None = None
    persisted: bool = False


class LedgerClassifyLlmRejectResult(OutputSchema):
    """JSON envelope for ``aeat app ledger classify ... --reject``.

    Projects :class:`LLMSuggestionRejectionResult`
    after :func:`reject_llm_suggestion` records the
    declined proposal in the bucket-event history as
    :attr:`BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED`.
    An explicit, audit-trailed rejection of an LLM suggestion: the row is NOT
    classified (``persisted`` is ``False``), but the rejection is recorded as a
    bucket event (``bucket_event_id``). ``suggestion_kind`` is
    ``classification`` or ``split``; ``operator_reason`` carries the operator's
    free-text reason.
    """

    llm: bool
    rejected: bool
    provider: str
    transaction_id: TransactionId
    suggestion_kind: str
    provenance: str
    bucket_event_id: str
    operator_reason: str = ""
    persisted: bool = False
