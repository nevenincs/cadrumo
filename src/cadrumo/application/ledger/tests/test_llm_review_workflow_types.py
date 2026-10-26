"""Contract tests for the typed LLM review workflow vocabulary.

Proves the mandatory-invocation-origin spine: the origin-to-source-command map
is total, distinct, and preserves separate provenance for the two split routes.
"""

from __future__ import annotations

import pytest

from ..llm_review_workflow import (
    LlmReviewInvocationOrigin,
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
