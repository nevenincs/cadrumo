"""The draft review terminal: no confidence, one writer, and a decline that shows.

Three properties, each of which was a ruling rather than a detail:

* The subject carries **no numeric confidence**. A model's self-assessed
  certainty is not evidence, and a number beside a field invites an operator to
  treat one reading as more checked than another when nothing checked either.
* **Apply delegates** to the draft store's single writer. A second path to the
  same record would fork two drafts for one document.
* **Reject writes no draft.** A no-op rewrite would make a decline
  indistinguishable from a re-read that came out the same, and the operator's
  "no" is the only thing the decision produced.

The dispatch structure is asserted too, because the reject branch runs before
any type dispatch and catches every reject: a draft decline added *beside* it
rather than *inside* it would never be reached, and every behavioural test here
would still pass against the version that put it in the wrong place.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from decimal import Decimal

import pytest

from ._confirmation_profile_fixture import profile

__all__ = ["profile"]

from ....core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from ....domain.transactions.errors import TransactionNotFoundError
from ....tests.secure_sql import TestRuntimeProfile
from ..evidence_draft import InvoiceDraft
from ..extraction_draft_store import load_extraction_drafts, read_extraction_draft
from ..llm_review_workflow import (
    InvoiceDraftDeclineResult,
    LlmReviewDecision,
    LlmReviewInvocationOrigin,
    ReviewedInvoiceDraft,
    execute_reviewed_decision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_STAMP = "llm:local-text-extract:qwen2.5:3b:rates-2026A-abc"


def _subject(reference: str = "ev-draft-1") -> ReviewedInvoiceDraft:
    return ReviewedInvoiceDraft(
        evidence_reference=reference,
        draft=InvoiceDraft(),
        extractor=_STAMP,
        read_transports=(LOCAL_TRANSPORT_LABEL,),
        provenance=_STAMP,
    )


# ── The confidence prohibition ───────────────────────────────────────────────


def test_the_draft_subject_carries_no_confidence_field_at_all() -> None:
    """Confidence-free by construction, not by leaving a field unset.

    An optional confidence would satisfy any test that merely declined to set
    it, while leaving the field available for the next caller to populate. The
    prohibition is load-bearing, so the absence has to be structural.
    """
    assert "confidence" not in ReviewedInvoiceDraft.model_fields

    with pytest.raises(ValueError, match="confidence"):
        ReviewedInvoiceDraft(
            evidence_reference="ev",
            draft=InvoiceDraft(),
            extractor=_STAMP,
            provenance=_STAMP,
            confidence=Decimal("0.9"),
        )


def test_its_siblings_do_require_confidence_so_the_absence_is_a_choice() -> None:
    """POSITIVE CONTROL: the three transaction-bound subjects still carry it.

    Without this, the assertion above passes equally against a codebase where
    no suggestion has ever had a confidence, and the ruling it encodes would be
    invisible.
    """
    from ....llm.suggestions import LLMClassificationSuggestion, LLMSaturatedSuggestion

    assert "confidence" in LLMClassificationSuggestion.model_fields
    assert "confidence" in LLMSaturatedSuggestion.model_fields


# ── Apply delegates, reject does not write ───────────────────────────────────


def test_apply_persists_through_the_draft_store(profile: TestRuntimeProfile) -> None:
    """The applied draft is readable from the store's own reader."""
    execute_reviewed_decision(
        _subject(),
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
        decision=LlmReviewDecision.APPLY,
        bucket_id=profile.bucket_id,
        settings=profile.settings,
    )

    stored = read_extraction_draft(
        bucket_id=profile.bucket_id,
        evidence_reference="ev-draft-1",
        settings=profile.settings,
    )
    assert stored is not None
    assert stored.extractor == _STAMP
    assert stored.read_transports == (LOCAL_TRANSPORT_LABEL,)


def test_reject_records_the_decline_and_writes_no_draft(profile: TestRuntimeProfile) -> None:
    """The decline leaves an event and no stored draft.

    The empty store is the load-bearing half. A decline that wrote the draft
    back unchanged would be indistinguishable from a re-read that came out the
    same -- one stored draft, fresh timestamp -- and the operator's decision
    would be the part not recorded.
    """
    outcome = execute_reviewed_decision(
        _subject(),
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
        decision=LlmReviewDecision.REJECT,
        bucket_id=profile.bucket_id,
        reason="the supplier is wrong",
        settings=profile.settings,
    )

    assert isinstance(outcome, InvoiceDraftDeclineResult)
    assert outcome.bucket_event_id
    assert outcome.operator_reason == "the supplier is wrong"
    assert load_extraction_drafts(profile.bucket_id, profile.settings).drafts == ()


def test_a_declined_draft_is_distinguishable_from_one_never_reviewed(
    profile: TestRuntimeProfile,
) -> None:
    """The event is the only trace, so it has to exist and name the evidence.

    Both states leave the draft store empty. If the decline emitted nothing,
    "the operator looked and said no" and "nobody has looked" would be the same
    absence, which is the distinction the whole terminal exists to record.
    """
    outcome = execute_reviewed_decision(
        _subject("ev-declined"),
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
        decision=LlmReviewDecision.REJECT,
        bucket_id=profile.bucket_id,
        settings=profile.settings,
    )

    assert isinstance(outcome, InvoiceDraftDeclineResult)
    assert outcome.evidence_reference == "ev-declined"
    assert outcome.provenance == _STAMP


def test_a_transaction_bound_reject_still_takes_the_original_path(
    profile: TestRuntimeProfile,
) -> None:
    """POSITIVE CONTROL: the split did not capture every reject.

    A draft branch placed too early would swallow the transaction-bound
    rejections that shared this branch before it, and every draft assertion
    above would still pass.
    """
    from ....domain.transactions.enums import BusinessClassification
    from ....llm.suggestions import LLMClassificationSuggestion

    suggestion = LLMClassificationSuggestion(
        transaction_id="a" * 64,
        provenance=_STAMP,
        classification=BusinessClassification.BUSINESS,
        confidence=Decimal("0.5"),
        reason="a reason",
    )

    with pytest.raises(TransactionNotFoundError) as raised:
        execute_reviewed_decision(
            suggestion,
            origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
            decision=LlmReviewDecision.REJECT,
            bucket_id=profile.bucket_id,
            settings=profile.settings,
        )

    # The transaction does not exist in this bucket, so the ORIGINAL primitive
    # refuses. That refusal is the evidence: a draft-shaped branch would have
    # returned a decline result instead of reaching a transaction lookup.
    assert not isinstance(raised.value, TypeError), "the transaction path was not reached at all"


# ── The structural hazard ────────────────────────────────────────────────────


def test_the_draft_split_lives_inside_the_reject_branch_not_beside_it() -> None:
    """The draft check must be nested under the reject test, not a sibling of it.

    The reject branch returns for every reject, so a sibling ``if`` placed after
    it is unreachable and a sibling placed before it would capture rejects it
    does not own. Only nesting is correct, and no behavioural test can see the
    difference on the cases that currently exist.

    Walked as an AST over the dispatch rather than matched against source text,
    because this module's own prose names both branches.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(execute_reviewed_decision)))
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)

    reject_branches = [node for node in function.body if isinstance(node, ast.If) and "REJECT" in ast.dump(node.test)]
    assert len(reject_branches) == 1, "the reject terminal should be one branch, not several"

    nested = [
        node
        for node in ast.walk(reject_branches[0])
        if isinstance(node, ast.If) and "ReviewedInvoiceDraft" in ast.dump(node.test)
    ]
    assert nested, (
        "the draft decline is not nested inside the reject branch. Placed beside it, it is either "
        "unreachable (after the branch returns) or captures rejects it does not own (before it)."
    )
