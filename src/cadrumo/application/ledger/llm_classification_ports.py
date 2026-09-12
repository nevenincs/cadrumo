"""Application boundary for supervised ledger LLM classification."""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, Self

from pydantic import BaseModel, Field, model_validator

from ...core.hashing import sha256_hex
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.identity.transaction_ids import TransactionId
from ...core.image_media_type import ImageMediaType
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.categories.spending_category import SpendingCategory
from ...domain.iva.schema import IvaCategory
from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.llm import LLMClassificationResponse, LLMClassifier, LLMSplitResponse, PromptSpec
from ...domain.transactions.models import Transaction
from .evidence_input import EvidenceInput
from .models import ManualLedgerTransactionResult


class LLMClassificationSuggestion(BaseModel):
    """A reviewable LLM classification that has not been persisted."""

    model_config = STRICT_FROZEN_CONFIG
    transaction_id: TransactionId
    provenance: str = Field(min_length=1)
    classification: BusinessClassification
    category: SpendingCategory | None = None
    confidence: Decimal
    reason: str = Field(min_length=1)
    evidence_id: str | None = None
    multiple_components: bool | None = None

    @property
    def recommends_split(self) -> bool:
        return self.multiple_components is True


class LLMSaturatedSuggestion(LLMClassificationSuggestion):
    """A classification review with system-derived IVA substrate."""

    iva_category: IvaCategory | None = None
    business_pct: Decimal | None = None
    iva_rate: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    rate_derivable: bool = False
    derivation_note: str = ""
    evidence_advisory: str = ""


class OperatorIvaDerivationResult(BaseModel):
    """Outcome of an operator-selected IVA category derivation."""

    model_config = STRICT_FROZEN_CONFIG
    transaction_id: TransactionId
    iva_category: IvaCategory
    derivable: bool
    iva_rate: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    note: str = ""
    result: ManualLedgerTransactionResult | None = None

    @model_validator(mode="after")
    def _substrate_matches_derivability(self) -> Self:
        substrate = (self.iva_rate, self.taxable_base, self.iva_amount, self.result)
        if self.derivable and any(value is None for value in substrate):
            raise ValueError("a derivable IVA derivation must carry its whole substrate")
        if not self.derivable and any(value is not None for value in substrate):
            raise ValueError("a non-derivable IVA derivation must carry no substrate")
        return self


class LLMSplitChildSuggestion(BaseModel):
    """One reviewable evidence-driven split child."""

    model_config = STRICT_FROZEN_CONFIG
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
    """Reviewable evidence-driven split proposal."""

    model_config = STRICT_FROZEN_CONFIG
    transaction_id: TransactionId
    provenance: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    parent_amount: Decimal
    children: tuple[LLMSplitChildSuggestion, ...]
    evidence_id: str | None = None

    @property
    def recommends_split(self) -> bool:
        return len(self.children) > 1


class LLMSplitApplyResult(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    bucket_id: BucketId
    parent_transaction_id: TransactionId
    split_group_id: str = Field(min_length=1)
    child_transaction_ids: tuple[str, ...]
    provenance: str = Field(min_length=1)
    classified_child_count: int


class LLMSuggestionRejectionResult(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    bucket_id: BucketId
    transaction_id: TransactionId
    bucket_event_id: str = Field(min_length=1)
    suggestion_kind: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    operator_reason: str = ""


class EvidenceImage(BaseModel):
    """Transient evidence image prepared for an application-owned reader port."""

    model_config = STRICT_FROZEN_CONFIG
    content_sha256: ContentDigest
    base64_data: str = Field(min_length=1, repr=False)
    media_type: ImageMediaType

    @classmethod
    def from_base64(cls, base64_data: str, media_type: ImageMediaType) -> EvidenceImage:
        return cls(
            content_sha256=sha256_hex(base64.b64decode(base64_data)),
            base64_data=base64_data,
            media_type=media_type,
        )


@dataclass(frozen=True)
class ResolvedEvidenceInput:
    """Document bytes and stable reference supplied by outer composition."""

    evidence_input: EvidenceInput
    reference: str


class VisionClassifier(Protocol):
    @property
    def decided_by(self) -> str: ...

    def classify(
        self, transaction: Transaction, *, evidence_images: tuple[EvidenceImage, ...]
    ) -> LLMClassificationResponse: ...

    def propose_split(
        self, transaction: Transaction, *, evidence_images: tuple[EvidenceImage, ...]
    ) -> LLMSplitResponse: ...


@dataclass(frozen=True)
class LLMClassificationPorts:
    """Outer-owned I/O required by the ledger LLM review use case."""

    resolve_evidence_input: Callable[[str, str | None, tuple[str, ...]], ResolvedEvidenceInput]
    rasterise_pdf: Callable[[bytes], tuple[str, ...]]
    make_text_classifier: Callable[[PromptSpec], LLMClassifier]
    make_vision_classifier: Callable[[PromptSpec, str | None], VisionClassifier]
    run_reader: Callable[[Callable[[], object]], object]
    record_classifier_run: Callable[[Callable[[], object], str], object]


__all__ = [
    "EvidenceImage",
    "LLMClassificationPorts",
    "LLMClassificationSuggestion",
    "LLMSaturatedSuggestion",
    "LLMSplitApplyResult",
    "LLMSplitChildSuggestion",
    "LLMSplitSuggestion",
    "LLMSuggestionRejectionResult",
    "OperatorIvaDerivationResult",
    "ResolvedEvidenceInput",
    "VisionClassifier",
]
