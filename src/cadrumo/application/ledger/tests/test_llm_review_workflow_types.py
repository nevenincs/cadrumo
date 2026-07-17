"""Contract tests for the typed LLM review workflow vocabulary.

Proves the mandatory-invocation-origin spine: the origin->source_command map is
total (no silently blank audit label), the request model rejects a missing
origin (there is no application-layer CLI default), and the audit label is
derived from the origin.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._llm_review_workflow import (
    LlmReviewDecision,
    LlmReviewInvocationOrigin,
    LlmReviewRequest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_every_origin_derives_a_non_empty_source_command() -> None:
    # Totality: a new origin without a spelling must fail loudly here, never
    # produce a blank audit label.
    for origin in LlmReviewInvocationOrigin:
        assert origin.source_command
        assert origin.source_command.startswith("aeat app ledger ")


def test_source_commands_are_distinct_per_origin() -> None:
    labels = [origin.source_command for origin in LlmReviewInvocationOrigin]
    assert len(labels) == len(set(labels))


def test_auto_split_and_split_llm_are_distinct_origins() -> None:
    # The two CLI routes share the split workflow but keep distinct provenance.
    assert LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT is not LlmReviewInvocationOrigin.SPLIT_LLM
    assert (
        LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT.source_command
        != LlmReviewInvocationOrigin.SPLIT_LLM.source_command
    )


def test_request_requires_an_invocation_origin() -> None:
    # No application-layer default: omitting the origin is a validation error,
    # not a silently-defaulted CLI spelling.
    with pytest.raises(ValidationError):
        LlmReviewRequest(
            decision=LlmReviewDecision.REJECT,
            bucket_id="bucket-1",
            transaction_id="tx-1",
        )


def test_request_source_command_is_derived_from_the_origin() -> None:
    request = LlmReviewRequest(
        invocation_origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
        decision=LlmReviewDecision.REJECT,
        bucket_id="bucket-1",
        transaction_id="tx-1",
    )
    assert request.source_command == "aeat app ledger classify --llm --reject"
    assert request.actor == "operator"


def test_request_is_frozen() -> None:
    request = LlmReviewRequest(
        invocation_origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
        decision=LlmReviewDecision.APPLY,
        bucket_id="bucket-1",
        transaction_id="tx-1",
    )
    with pytest.raises(ValidationError):
        request.transaction_id = "tx-2"
