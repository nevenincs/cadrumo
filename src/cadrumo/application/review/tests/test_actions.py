"""Tests for review annotation actions."""

from __future__ import annotations

import pytest

from ...workflow import WorkflowState
from .. import LedgerReviewRecord, update_ledger_review
from .._errors import ReviewError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_update_ledger_review_records_attention_history_only() -> None:
    updated = update_ledger_review(
        WorkflowState(),
        "tx-1",
        action="inspect",
        reason="operator opened the row",
    )

    review = LedgerReviewRecord.model_validate(updated.ledger_reviews["tx-1"])
    assert review.transaction_id == "tx-1"
    assert len(review.history) == 1
    assert review.history[0].action == "inspect"
    assert review.history[0].reason == "operator opened the row"


def test_update_ledger_review_refuses_durable_field_overlay() -> None:
    with pytest.raises(ReviewError, match="must not store durable ledger fields"):
        update_ledger_review(
            WorkflowState(),
            "tx-1",
            fields={"category": "software"},
            action="edit",
            reason="classification belongs in transaction catalogue",
        )


def test_update_ledger_review_refuses_skip_and_split_overlay() -> None:
    with pytest.raises(ReviewError, match="skip state"):
        update_ledger_review(
            WorkflowState(),
            "tx-1",
            skipped=True,
            action="skip",
            reason="skip belongs in transaction classification",
        )

    with pytest.raises(ReviewError, match="allocation"):
        update_ledger_review(
            WorkflowState(),
            "tx-1",
            split=object(),
            action="allocate",
            reason="business_pct belongs in transaction catalogue",
        )
