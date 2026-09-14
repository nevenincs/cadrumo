"""Pure application checks for LLM review-dispatch policy.

Persistence-backed review behavior lives under the persistence adapter test
owner. This module keeps the decisions that can be proved without storage:
invalid terminal combinations are refused and every invocation origin owns its
durable command label.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.application.ledger.llm_classification_ports import LLMClassificationSuggestion
from cadrumo.application.ledger.llm_review_workflow import (
    LlmReviewDecision,
    LlmReviewInvocationOrigin,
    execute_reviewed_decision,
)
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.transactions.enums import BusinessClassification
from cadrumo.domain.transactions.errors import TransactionValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_UNKNOWN_TRANSACTION_ID = "f" * 64


def _classification_suggestion(tx_id: str) -> LLMClassificationSuggestion:
    return LLMClassificationSuggestion(
        transaction_id=tx_id,
        provenance="llm:test:test-model",
        classification=BusinessClassification.BUSINESS,
        category=SpendingCategory.MATERIAL_OFICINA,
        confidence=Decimal("0.9"),
        reason="focused dispatch fixture",
    )


def test_split_decision_on_classification_suggestion_refuses() -> None:
    with pytest.raises(TransactionValidationError):
        execute_reviewed_decision(
            _classification_suggestion(_UNKNOWN_TRANSACTION_ID),
            origin=LlmReviewInvocationOrigin.SPLIT_LLM,
            decision=LlmReviewDecision.SPLIT,
            bucket_id="test-bucket",
        )


@pytest.mark.parametrize("decision", [LlmReviewDecision.SUGGEST, LlmReviewDecision.NO_SPLIT])
def test_non_persisting_terminals_refuse_durable_execution(decision: LlmReviewDecision) -> None:
    with pytest.raises(TransactionValidationError):
        execute_reviewed_decision(
            _classification_suggestion(_UNKNOWN_TRANSACTION_ID),
            origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
            decision=decision,
            bucket_id="test-bucket",
        )


def test_every_invocation_origin_derives_a_distinct_nonblank_source_command() -> None:
    commands = {origin: origin.source_command for origin in LlmReviewInvocationOrigin}
    assert all(command.strip().startswith("aeat app ledger") for command in commands.values())
    assert len(set(commands.values())) == len(LlmReviewInvocationOrigin)
