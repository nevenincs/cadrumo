"""LLM ledger classification suggestion/result contracts.

These strict frozen DTOs carry the reviewable output of the governed ledger
LLM workflow: stage-1 business classification suggestions, saturated IVA
category suggestions with system-derived tax substrate, evidence-driven split
proposals, provider availability rows, and explicit rejection receipts. They
are application-layer contracts only; classifier engines and prompt parsing live
in :mod:`~domain.transactions`, while persistence and audit events are handled
by the application services that consume these records.

The contracts preserve the review loop: a suggestion
is not persisted until the operator applies it, a rejection records an audit
event without mutating the transaction, and regulated euro amounts / IVA rates
are derived by the system rather than emitted by the model.

PROVENANCE STAMP: ``llm:<transport>:<model>``
---------------------------------------------

Every suggestion carries a ``provenance`` stamp recording which transport read
the document and with which model, so a persisted classification can always
answer how it was reached.

**The transport axis is multi-valued, and it stayed that way.** It once ranged
over cloud provider CLIs -- ``llm:claude:...``, ``llm:codex:...`` -- alongside the
on-host reader. Those subprocess transports were deleted permanently. The axis
briefly collapsed to the local runtime with them, and then did not stay
collapsed: off-host reading was re-sanctioned over the in-memory HTTP providers
behind a per-invocation consent gate, so a fresh stamp names a local transport
by default and names the off-host one when a consented read used it.

The stamp's SHAPE is unchanged and **no persisted record is rewritten.**
Pre-existing rows keep the provider they were stamped with, because that is the
honest history of how those classifications were actually reached -- rewriting
them would erase the fact that some data did once leave the host.

The consequence for code: treat the axis as multi-valued in BOTH directions.
Do not assume a fresh classification is on-host, and do not assume a stored
stamp names a local transport when reading history. The paragraph this replaced
said the opposite of the first half, and a consent withdrawal enumerates
cloud-derived artefacts by exactly that segment -- so code written to its
instruction would survey for a value it had been told could not occur.

See Also:
    :mod:`~application.ledger.llm_classification`
        Application service that builds, applies, saturates, splits, and rejects
        these suggestions.
    :func:`~application.ledger.llm_classification.suggest_llm_classification`
        Stage-1 suggestion path that persists nothing.
    :func:`~application.ledger.llm_classification.saturate_llm_classification`
        Path that adds model-selected IVA category plus system-derived substrate.
    :func:`~application.ledger.llm_classification.suggest_evidence_split`
        Evidence-driven split/no-split proposal builder.
    :func:`~application.ledger.llm_classification.reject_llm_suggestion`
        Audit-trailed rejection terminal for any suggestion kind.
    :mod:`~entrypoints.cli._ledger_llm_payloads`
        CLI JSON-envelope projections for suggest, saturate, and reject paths.
    :class:`~domain.transactions.LLMClassificationResponse`
        Domain classifier response projected into
        :class:`LLMClassificationSuggestion`.
    :class:`~domain.transactions.LLMSplitResponse`
        Domain split response projected into :class:`LLMSplitSuggestion`.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..application.ledger.models import ManualLedgerTransactionResult
from ..core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..core import FieldOrigin
from ..core.identity import BucketId, TaxIdIdentityToken, TransactionId
from ..domain.categories.spending_category import SpendingCategory
from ..domain.iva import IvaCategory
from ..domain.transactions.enums import BusinessClassification


class LLMClassificationSuggestion(BaseModel):
    """One LLM classification suggestion for a transaction, not yet persisted."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    provenance: str = Field(min_length=1)
    classification: BusinessClassification
    category: SpendingCategory | None = None
    confidence: Decimal
    reason: str = Field(min_length=1)
    evidence_id: str | None = None
    multiple_components: bool | None = None
    """True when the evidence read judged a split may be warranted."""

    @property
    def recommends_split(self) -> bool:
        """True when the evidence read flagged the invoice as multi-component."""
        return self.multiple_components is True


class LLMSaturatedSuggestion(BaseModel):
    """A saturated LLM suggestion: business decision plus grounded tax substrate."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    provenance: str = Field(min_length=1)
    classification: BusinessClassification
    category: SpendingCategory | None = None
    confidence: Decimal
    reason: str = Field(min_length=1)
    iva_category: IvaCategory | None = None
    business_pct: Decimal | None = None
    iva_rate: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    rate_derivable: bool = False
    derivation_note: str = ""
    evidence_id: str | None = None
    evidence_advisory: str = ""
    multiple_components: bool | None = None
    """True when the evidence read judged a split may be warranted."""

    @property
    def recommends_split(self) -> bool:
        """True when the evidence read flagged the invoice as multi-component."""
        return self.multiple_components is True


class OperatorIvaDerivationResult(BaseModel):
    """Result of an operator-initiated IVA derivation for one transaction."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    iva_category: IvaCategory
    derivable: bool
    iva_rate: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    note: str = ""
    result: ManualLedgerTransactionResult | None = None


class LLMSplitChildSuggestion(BaseModel):
    """One reviewed child of an evidence-driven split, with derived numbers."""

    model_config = _STRICT_FROZEN

    proportion: Decimal
    amount: Decimal
    description: str = Field(min_length=1)
    category: SpendingCategory | None = None
    iva_category: IvaCategory | None = None
    iva_rate: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    rate_derivable: bool = False
    derivation_note: str = ""
    evidence_citation: str = ""


class LLMSplitSuggestion(BaseModel):
    """An evidence-driven N-way split proposal with derived child amounts."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    provenance: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    parent_amount: Decimal
    children: tuple[LLMSplitChildSuggestion, ...]
    evidence_id: str | None = None

    @property
    def recommends_split(self) -> bool:
        """True when the model proposed more than one child."""
        return len(self.children) > 1


class LLMSplitApplyResult(BaseModel):
    """Outcome of applying a reviewed evidence-driven split."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    parent_transaction_id: TransactionId
    split_group_id: str = Field(min_length=1)
    child_transaction_ids: tuple[str, ...]
    provenance: str = Field(min_length=1)
    classified_child_count: int


class LLMSuggestionRejectionResult(BaseModel):
    """Outcome of explicitly rejecting an LLM suggestion."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    transaction_id: TransactionId
    bucket_event_id: str = Field(min_length=1)
    suggestion_kind: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    operator_reason: str = ""


__all__ = [
    "LLMClassificationSuggestion",
    "LLMSaturatedSuggestion",
    "LLMSplitApplyResult",
    "LLMSplitChildSuggestion",
    "LLMSplitSuggestion",
    "LLMSuggestionRejectionResult",
    "OperatorIvaDerivationResult",
]


# ---------------------------------------------------------------------------
# The core-to-extension interchange contract
# ---------------------------------------------------------------------------

_INTERCHANGE_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid")


class ExtractionProducer(BaseModel):
    """Identity of whatever produced an extraction payload.

    Carried so a persisted record can always answer HOW each field was
    recovered. For a model that means the exact model identity and revision;
    for the deterministic readers it means which parser and which syntax. A
    payload constructed without a producer does not validate, because a value
    whose origin cannot be named is not reviewable.
    """

    model_config = _INTERCHANGE_CONFIG

    source_kind: FieldOrigin
    identity: str = Field(min_length=1)
    """Model identity (``qwen2.5vl:3b``) or parser identity (``en16931-cii``)."""
    revision: str = Field(min_length=1)
    """Model revision/digest, or the parser's syntax revision."""


class ExtractionPayload(BaseModel):
    """The ONLY shape the core accepts from an extension reading path.

    Strict, frozen and ``extra="forbid"`` over a fixed key set: an unexpected
    key does not survive validation, it raises. That is the point of the
    boundary. Free text is never the interchange value -- handing the core raw
    model output would make the boundary a laundering channel rather than a
    validation point, and extraction fields have no allow-list the way
    classification categories do, so hostile document text promoted across the
    boundary is exactly where prompt injection gets worse.

    Markdown or raw model text may exist INSIDE the extension as an
    intermediate. It may not cross.

    Every field is optional in VALUE and mandatory in PROVENANCE: a reader that
    could not ground a field leaves it ``None`` rather than guessing, but the
    payload as a whole cannot omit its ``legal_refs``, ``source_refs`` or
    ``producer``.
    """

    model_config = _INTERCHANGE_CONFIG

    supplier_tax_id: TaxIdIdentityToken | None = None
    customer_tax_id: TaxIdIdentityToken | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    currency: str | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    grand_total: Decimal | None = None
    recargo_amount: Decimal | None = None
    iva_category: IvaCategory | None = None

    producer: ExtractionProducer
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]

    @field_validator("taxable_base", "iva_amount", "grand_total", "recargo_amount")
    @classmethod
    def _finite_amount(cls, value: Decimal | None) -> Decimal | None:
        """Refuse a non-finite amount rather than carrying it into a filing.

        A NaN or infinity reaching the core would propagate silently through
        every arithmetic consumer downstream and surface as a nonsense total
        far from its origin.
        """
        if value is not None and not value.is_finite():
            raise ValueError("amount must be a finite decimal")
        return value

    @field_validator("legal_refs", "source_refs")
    @classmethod
    def _non_empty_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require at least one grounding reference, each non-blank.

        An empty tuple would satisfy the type while carrying no grounding at
        all, which is the shape this field exists to prevent.
        """
        if not value:
            raise ValueError("at least one reference is required")
        if any(not ref.strip() for ref in value):
            raise ValueError("references must be non-blank")
        return value
