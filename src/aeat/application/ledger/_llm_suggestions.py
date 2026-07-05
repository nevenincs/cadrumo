"""LLM ledger classification suggestion/result contracts."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.categories import SpendingCategory
from ...domain.iva import IvaCategory
from ...domain.transactions import BusinessClassification
from ._models import ManualLedgerTransactionResult


class LLMProvider(StrEnum):
    """Subprocess LLM provider names accepted by the classify surface."""

    CLAUDE = "claude"
    ANTIGRAVITY = "antigravity"
    CODEX = "codex"


class LLMClassificationSuggestion(BaseModel):
    """One LLM classification suggestion for a transaction, not yet persisted."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1)
    provider: LLMProvider | None = None
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


class LLMProviderAvailability(BaseModel):
    """Whether one subprocess LLM provider has a usable CLI on ``PATH``."""

    model_config = _STRICT_FROZEN

    provider: LLMProvider
    cli_binary: str = Field(min_length=1)
    available: bool
    resolved_path: str | None = None


class LLMSaturatedSuggestion(BaseModel):
    """A saturated LLM suggestion: business decision plus grounded tax substrate."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1)
    provider: LLMProvider | None = None
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

    transaction_id: str
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

    transaction_id: str = Field(min_length=1)
    provider: LLMProvider | None = None
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

    bucket_id: str = Field(min_length=1)
    parent_transaction_id: str = Field(min_length=1)
    split_group_id: str = Field(min_length=1)
    child_transaction_ids: tuple[str, ...]
    provenance: str = Field(min_length=1)
    classified_child_count: int


class LLMSuggestionRejectionResult(BaseModel):
    """Outcome of explicitly rejecting an LLM suggestion."""

    model_config = _STRICT_FROZEN

    bucket_id: str = Field(min_length=1)
    transaction_id: str = Field(min_length=1)
    bucket_event_id: str = Field(min_length=1)
    suggestion_kind: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    operator_reason: str = ""


__all__ = [
    "LLMClassificationSuggestion",
    "LLMProvider",
    "LLMProviderAvailability",
    "LLMSaturatedSuggestion",
    "LLMSplitApplyResult",
    "LLMSplitChildSuggestion",
    "LLMSplitSuggestion",
    "LLMSuggestionRejectionResult",
    "OperatorIvaDerivationResult",
]
