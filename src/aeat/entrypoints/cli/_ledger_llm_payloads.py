"""LLM-classify CLI result payloads (suggest / saturate / reject).

Strict :class:`OutputSchema` subclasses for the LLM decision terminals,
split out of ``_ledger_payloads.py`` to keep that registry within its size
budget. These are emitted under the ``ledger.classify`` command envelope.
"""

from __future__ import annotations

from ._schemas import OutputSchema


class LedgerClassifyLlmSuggestResult(OutputSchema):
    """JSON envelope for the ``aeat app ledger classify --llm`` (no ``--apply``) path (D1).

    The proposed decision is surfaced for operator review; nothing is
    persisted (``persisted`` is ``False``) until the operator re-runs with
    ``--apply``.
    """

    llm: bool
    provider: str
    transaction_id: str
    classification: str | None = None
    category: str | None = None
    confidence: str | None = None
    reason: str | None = None
    provenance: str | None = None
    persisted: bool = False


class LedgerClassifyLlmSaturateResult(OutputSchema):
    """JSON envelope for the ``aeat app ledger classify --llm --saturate`` path (D1).

    The model-selected IVA category plus the system-derived euro substrate.
    The numbers are present only when the category was derivable; otherwise
    ``derivation_note`` explains why the operator must complete them.
    """

    llm: bool
    provider: str
    transaction_id: str
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

    An explicit, audit-trailed rejection of an LLM suggestion: the row is NOT
    classified (``persisted`` is ``False``), but the rejection is recorded as a
    bucket event (``bucket_event_id``). ``suggestion_kind`` is ``classification``
    or ``split``; ``operator_reason`` carries the operator's free-text reason.
    """

    llm: bool
    rejected: bool
    provider: str
    transaction_id: str
    suggestion_kind: str
    provenance: str
    bucket_event_id: str
    operator_reason: str = ""
    persisted: bool = False
