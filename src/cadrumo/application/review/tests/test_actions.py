"""Tests for review annotation actions."""

from __future__ import annotations

import hashlib

import pytest

from ...workflow import WorkflowState
from .. import LedgerReviewRecord, update_ledger_review
from .._errors import ReviewError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: A conforming transaction identity. ``transaction_id`` is a content-addressed
#: 64-hex digest, so a short readable token is not a legal value; it is derived
#: from a label here so the assertions stay readable.
_TRANSACTION_ID = hashlib.sha256(b"tx-1").hexdigest()


def test_update_ledger_review_records_attention_history_only() -> None:
    updated = update_ledger_review(
        WorkflowState(),
        _TRANSACTION_ID,
        action="inspect",
        reason="operator opened the row",
    )

    review = LedgerReviewRecord.model_validate(updated.ledger_reviews[_TRANSACTION_ID])
    assert review.transaction_id == _TRANSACTION_ID
    assert len(review.history) == 1
    assert review.history[0].action == "inspect"
    assert review.history[0].reason == "operator opened the row"


def test_update_ledger_review_refuses_durable_field_overlay() -> None:
    with pytest.raises(ReviewError):
        update_ledger_review(
            WorkflowState(),
            "tx-1",
            fields={"category": "software"},
            action="edit",
            reason="classification belongs in transaction catalogue",
        )


def test_update_ledger_review_refuses_skip_and_split_overlay() -> None:
    with pytest.raises(ReviewError):
        update_ledger_review(
            WorkflowState(),
            "tx-1",
            skipped=True,
            action="skip",
            reason="skip belongs in transaction classification",
        )

    with pytest.raises(ReviewError):
        update_ledger_review(
            WorkflowState(),
            "tx-1",
            split=object(),
            action="allocate",
            reason="business_pct belongs in transaction catalogue",
        )
