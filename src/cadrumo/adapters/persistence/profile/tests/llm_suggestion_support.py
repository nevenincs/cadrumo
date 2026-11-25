"""LLM classification suggestion shared by the reject and review workflow suites."""

from __future__ import annotations

from decimal import Decimal

from cadrumo.application.ledger.llm_classification_ports import (
    LLMClassificationSuggestion,
)
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.transactions.enums import BusinessClassification


def classification_suggestion(tx_id: str) -> LLMClassificationSuggestion:
    return LLMClassificationSuggestion(
        transaction_id=tx_id,
        provenance="llm:claude:test-model",
        classification=BusinessClassification.BUSINESS,
        category=SpendingCategory.from_registry("material_oficina"),
        confidence=Decimal("0.9"),
        reason="looks like office supplies",
    )
