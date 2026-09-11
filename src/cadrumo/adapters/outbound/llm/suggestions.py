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
from typing import Self

from pydantic import BaseModel, Field, model_validator

from ....application.ledger.models import ManualLedgerTransactionResult
from ....core.identity.bucket import BucketId
from ....core.identity.transaction_ids import TransactionId
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....domain.categories.spending_category import SpendingCategory
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification


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
    """Result of an operator-initiated IVA derivation for one transaction.

    ``derivable`` and the substrate are ONE answer, not a flag beside four
    optional numbers. A category the registry can rate yields a rate, a base,
    an amount and the persisted write; one it cannot yields none of them and a
    note saying why. The four fields are optional because the second case
    exists, not because either case is partial.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    iva_category: IvaCategory
    derivable: bool
    iva_rate: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    note: str = ""
    result: ManualLedgerTransactionResult | None = None

    @model_validator(mode="after")
    def _the_substrate_agrees_with_derivability(self) -> Self:
        """Refuse a result whose substrate disagrees with its own flag.

        Both directions are wrong, and only one of them was ever checked. A
        derivable result missing its substrate leaves a caller with a success
        it cannot use -- the command that reads this had to hand-check for
        exactly that. A NON-derivable result CARRYING a substrate was checked
        nowhere: a consumer trusting the numbers over the flag would persist a
        rate the derivation explicitly declined to make, which is the more
        dangerous direction and the reason this is stated on the model rather
        than at whichever surface remembers to ask.

        Raises:
            ValueError: When the flag and the substrate disagree.
        """
        substrate = (self.iva_rate, self.taxable_base, self.iva_amount, self.result)
        if self.derivable and any(value is None for value in substrate):
            raise ValueError("a derivable IVA derivation must carry its whole substrate")
        if not self.derivable and any(value is not None for value in substrate):
            raise ValueError("a non-derivable IVA derivation must carry no substrate")
        return self


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
