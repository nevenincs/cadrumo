"""Pure application checks for LLM review-dispatch policy.

Persistence-backed review behavior lives under the persistence adapter test
owner. This module keeps the decisions that can be proved without storage:
invalid terminal combinations are refused and every invocation origin owns its
durable command label.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from cadrumo.application.ledger.action_ports import LedgerActionPorts
from cadrumo.application.ledger.llm_classification_ports import (
    LLMClassificationSuggestion,
    LLMSaturatedSuggestion,
    LLMSplitApplyResult,
    LLMSplitChildSuggestion,
    LLMSplitSuggestion,
)
from cadrumo.application.ledger.llm_review_workflow import (
    LlmReviewDecision,
    LlmReviewInvocationOrigin,
    LlmReviewResult,
    ReviewedSuggestion,
    execute_reviewed_decision,
)
from cadrumo.application.ledger.models import ManualLedgerTransactionResult
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.errors import TransactionValidationError
from cadrumo.domain.transactions.models import BucketTransactionRef, Transaction
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_UNKNOWN_TRANSACTION_ID = "f" * 64
_BUCKET = "6b7f51be-0795-4e5a-9a22-7ec622d39b3b"


def _baseline() -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="unit-review-row",
                booked_date=date(2026, 1, 1),
                amount=Decimal("10.00"),
                currency="EUR",
                description="synthetic review row",
                provenance=RawProvenance(
                    source_path=Path("synthetic-review.csv"),
                    source_sha256="c" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2026, 1, 1, tzinfo=UTC),
                    provider_name="csv",
                ),
                raw_fields={"description": "synthetic review row"},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
        }
    )


def _split_suggestion(baseline: Transaction, *, count: int) -> LLMSplitSuggestion:
    return LLMSplitSuggestion(
        transaction_id=baseline.transaction_id,
        provenance="llm:test:test-model",
        reason="focused evidence dispatch fixture",
        parent_amount=baseline.raw.amount,
        children=tuple(
            LLMSplitChildSuggestion(
                proportion=Decimal(1) / count,
                amount=baseline.raw.amount / count,
                description=f"synthetic component {index}",
            )
            for index in range(count)
        ),
    )


def _dispatch_ports() -> LedgerActionPorts:
    # These tests substitute only canonical persistence terminals. The actual
    # dispatcher needs these two port identities for its ordinary apply branch.
    return cast("LedgerActionPorts", SimpleNamespace(transaction_repository=object(), bucket_event_repository=object()))


def _classification_suggestion(tx_id: str) -> LLMClassificationSuggestion:
    return LLMClassificationSuggestion(
        transaction_id=tx_id,
        provenance="llm:test:test-model",
        classification=BusinessClassification.BUSINESS,
        category=SpendingCategory.from_registry("material_oficina"),
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


def test_every_invocation_origin_derives_a_distinct_nonblank_source_command() -> None:
    commands = {origin: origin.source_command for origin in LlmReviewInvocationOrigin}
    assert all(command.strip().startswith("aeat app ledger") for command in commands.values())
    assert len(set(commands.values())) == len(LlmReviewInvocationOrigin)


@pytest.mark.parametrize("kind", ["classification", "saturated", "split", "one-child"])
@pytest.mark.usefixtures("authority_operation")
def test_review_dispatch_forwards_exact_immutable_baseline_and_origin(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    baseline = _baseline()
    ports = _dispatch_ports()
    subject: ReviewedSuggestion
    result: LlmReviewResult = ManualLedgerTransactionResult(
        ref=BucketTransactionRef(bucket_id=_BUCKET, transaction_id=baseline.transaction_id), transaction=baseline
    )
    if kind == "classification":
        subject = _classification_suggestion(baseline.transaction_id)
        origin = LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY
        terminal = "apply_llm_classification"
        decision = LlmReviewDecision.APPLY
    elif kind == "saturated":
        subject = LLMSaturatedSuggestion.model_validate(
            _classification_suggestion(baseline.transaction_id).model_dump()
        )
        origin = LlmReviewInvocationOrigin.CLASSIFY_LLM_SATURATE_APPLY
        terminal = "apply_saturated_llm_classification"
        decision = LlmReviewDecision.APPLY
    else:
        subject = _split_suggestion(baseline, count=1 if kind == "one-child" else 2)
        origin = (
            LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT
            if kind == "one-child"
            else LlmReviewInvocationOrigin.SPLIT_LLM
        )
        terminal = "apply_evidence_classification" if kind == "one-child" else "apply_evidence_split"
        decision = LlmReviewDecision.APPLY if kind == "one-child" else LlmReviewDecision.SPLIT
        if kind == "split":
            result = LLMSplitApplyResult(
                bucket_id=_BUCKET,
                parent_transaction_id=baseline.transaction_id,
                split_group_id="synthetic-split-group",
                child_transaction_ids=("a" * 64, "b" * 64),
                provenance=subject.provenance,
                classified_child_count=2,
            )
    calls: list[dict[str, object]] = []

    def apply(received: ReviewedSuggestion, **kwargs: object) -> LlmReviewResult:
        assert received is subject
        calls.append(kwargs)
        return result

    monkeypatch.setattr(f"cadrumo.application.ledger.llm_review_workflow.{terminal}", apply)
    observed = execute_reviewed_decision(
        subject, origin=origin, decision=decision, bucket_id=_BUCKET, ports=ports, expected_current=baseline
    )
    assert observed is result and len(calls) == 1
    assert calls[0]["expected_current"] is baseline
    assert calls[0]["source_command"] == origin.source_command
    assert calls[0]["actor"] == "operator"
    assert calls[0]["bucket_id"] == _BUCKET
    if kind == "classification":
        assert calls[0]["transaction_repository"] is ports.transaction_repository
        assert calls[0]["bucket_event_repository"] is ports.bucket_event_repository
    else:
        assert calls[0]["ports"] is ports


@pytest.mark.parametrize(
    ("origin", "count"),
    [
        (LlmReviewInvocationOrigin.SPLIT_LLM, 1),
        (LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT, 0),
        (LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT, 2),
    ],
)
@pytest.mark.usefixtures("authority_operation")
def test_apply_split_subject_requires_exact_single_child_auto_split_origin(
    origin: LlmReviewInvocationOrigin, count: int
) -> None:
    baseline = _baseline()
    with pytest.raises(TransactionValidationError, match="APPLY decision requires"):
        execute_reviewed_decision(
            _split_suggestion(baseline, count=count),
            origin=origin,
            decision=LlmReviewDecision.APPLY,
            bucket_id=_BUCKET,
            ports=_dispatch_ports(),
            expected_current=baseline,
        )
