"""An agent's model-backed review leaves a row the person worked on alone, at both of its phases.

A review response belongs to the session that submitted the review, so an
agent answers the review it asked for. The executor therefore refuses an agent
twice: before the reader is asked, so the person's text is not handed to a
model for a proposal only the person may apply, and again where the reviewed
decision would be committed. The person's frontends run both phases on the
same row as before.

The row, the reviewed operand and the executor are real. The proposal function
and the writer are stood in for, as in the sibling suite, because what is under
test is whether the executor reaches them at all.
"""

from __future__ import annotations

from typing import cast

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.classification_origin import ClassificationOrigin
from ....domain.transactions.enums import BusinessClassification
from ....domain.transactions.models import BucketTransactionRef, TransactionCatalogue
from ...operations.registry import OperationFrontendProjection
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import llm_review_execution as review_runtime
from ..llm_classification_ports import LLMSplitApplyResult, LLMSuggestionRejectionResult
from ..llm_review_contracts import LedgerLlmReviewRequest
from ..llm_review_execution import LedgerLlmReviewExecutor
from ..llm_review_workflow import LlmReviewDecision
from ..models import ManualLedgerTransactionResult
from .test_llm_review_operation import (
    _FIRST_PHASE,
    _PROFILE,
    _THIS_MACHINE,
    _Case,
    _Mode,
    _model_calls,
    _reader_endpoint,
    _session_host_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MCP = OperationFrontendProjection.MCP
_PROPOSED_BY = "llm:local-text:test"
_MODES = pytest.mark.parametrize("mode", ["classification", "saturated", "auto_split", "split"])
_PERSONS_FRONTENDS = pytest.mark.parametrize(
    "frontend", [OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, None], ids=["cli", "tui", "unhosted"]
)


def _store(case: _Case, update: dict[str, object]) -> None:
    """Replace the case's stored row; none of these members enters the row's identifier."""
    case.baseline = case.baseline.model_copy(update=update)
    case.repository.catalogue = TransactionCatalogue.from_transactions((case.baseline,))


def _classified_by(case: _Case, origin: ClassificationOrigin, *, stamp: str = "manual") -> None:
    _store(
        case,
        {
            "business_classification": BusinessClassification.PERSONAL,
            "classified_by": stamp,
            "classification_origin": origin,
        },
    )


def _executor(case: _Case, frontend: OperationFrontendProjection | None) -> LedgerLlmReviewExecutor:
    return LedgerLlmReviewExecutor(
        case.factory, execution_caller_reader=None if frontend is None else _session_host_for(frontend)
    )


def _previewing(case: _Case, preview: bool) -> None:
    case.payload = LedgerLlmReviewRequest.model_validate({**case.payload.model_dump(), "preview": preview})
    case.request = case.request.model_copy(update={"payload": case.payload})


@pytest.mark.asyncio
@_MODES
@pytest.mark.parametrize("preview", [False, True], ids=["review", "preview"])
@pytest.mark.parametrize("stamp", ["manual", "llm:local-text:model", "derived:iva-category"])
async def test_an_agents_review_of_a_row_the_person_classified_is_refused_before_the_model_is_asked(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    mode: _Mode,
    preview: bool,
    stamp: str,
) -> None:
    """The row is read, the model is not, and no effect is declared: whatever stamp the person's decision left."""
    case = _Case(authority_operation, mode)
    _previewing(case, preview)
    _classified_by(case, ClassificationOrigin.PERSON, stamp=stamp)
    _reader_endpoint(case, _THIS_MACHINE)
    calls = _model_calls(monkeypatch, case, mode)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        await _executor(case, _MCP).execute(case.request, case.context)

    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
    assert calls == []
    assert case.repository.loads == 1
    assert case.events.phases == [_FIRST_PHASE] and case.events.effects == []
    assert case.operands.published is None and case.interactions.published is None


@pytest.mark.asyncio
@_MODES
@pytest.mark.parametrize(
    "origin", [None, ClassificationOrigin.AGENT, ClassificationOrigin.AUTOMATIC], ids=["unprocessed", "agent", "rule"]
)
async def test_an_agents_review_of_a_row_that_is_not_the_persons_asks_the_model(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    mode: _Mode,
    origin: ClassificationOrigin | None,
) -> None:
    """The hand stamp a later write left on a rule's or an agent's row does not close it to an agent."""
    case = _Case(authority_operation, mode)
    if origin is not None:
        _classified_by(case, origin)
    _reader_endpoint(case, _THIS_MACHINE)
    calls = _model_calls(monkeypatch, case, mode)

    await _executor(case, _MCP).execute(case.request, case.context)

    assert len(calls) == 1 and calls[0]["reviewed_transaction"] is case.baseline
    assert case.interactions.published is not None


@pytest.mark.asyncio
@_MODES
@pytest.mark.parametrize("link", ["attachment_ids", "purchase_invoice_evidence_id", "invoice_id"])
async def test_an_agents_review_that_may_split_is_refused_a_row_that_carries_the_persons_evidence_or_invoice(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    mode: _Mode,
    link: str,
) -> None:
    """A classification in place keeps what the row links; a split passes the invoice link to no child."""
    case = _Case(authority_operation, mode)
    _store(case, {link: ("c" * 64,) if link == "attachment_ids" else "c" * 64})
    _reader_endpoint(case, _THIS_MACHINE)
    calls = _model_calls(monkeypatch, case, mode)
    executor = _executor(case, _MCP)

    if mode in {"auto_split", "split"}:
        with pytest.raises(ProfileAccessRefusedError) as refused:
            await executor.execute(case.request, case.context)
        assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
        assert calls == [] and case.events.effects == [] and case.interactions.published is None
    else:
        await executor.execute(case.request, case.context)
        assert len(calls) == 1 and case.interactions.published is not None


@pytest.mark.asyncio
@_MODES
@_PERSONS_FRONTENDS
async def test_a_persons_review_of_the_row_they_classified_asks_the_model_as_before(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    mode: _Mode,
    frontend: OperationFrontendProjection | None,
) -> None:
    case = _Case(authority_operation, mode)
    _classified_by(case, ClassificationOrigin.PERSON)
    _store(case, {"attachment_ids": ("c" * 64,)})
    _reader_endpoint(case, _THIS_MACHINE)
    calls = _model_calls(monkeypatch, case, mode)

    await _executor(case, frontend).execute(case.request, case.context)

    assert len(calls) == 1
    assert case.events.phases == [_FIRST_PHASE, "ledger.llm.review"]
    assert case.interactions.published is not None


def _writer(monkeypatch: pytest.MonkeyPatch, case: _Case) -> list[LlmReviewDecision]:
    """Stand in for the one function that commits a reviewed decision, and record each decision it is handed."""
    decisions: list[LlmReviewDecision] = []

    def write(_suggestion: object, **kwargs: object) -> BaseModel:
        decision = cast(LlmReviewDecision, kwargs["decision"])
        decisions.append(decision)
        if decision is LlmReviewDecision.REJECT:
            return LLMSuggestionRejectionResult(
                bucket_id=str(_PROFILE),
                transaction_id=case.baseline.transaction_id,
                bucket_event_id="e" * 64,
                suggestion_kind="classification",
                provenance=_PROPOSED_BY,
                operator_reason=case.payload.reason,
            )
        if decision is LlmReviewDecision.SPLIT:
            return LLMSplitApplyResult(
                bucket_id=str(_PROFILE),
                parent_transaction_id=case.baseline.transaction_id,
                split_group_id="synthetic-group",
                child_transaction_ids=("d" * 64, "e" * 64),
                classified_child_count=2,
                provenance=_PROPOSED_BY,
            )
        return ManualLedgerTransactionResult(
            ref=BucketTransactionRef(bucket_id=str(_PROFILE), transaction_id=case.baseline.transaction_id),
            transaction=case.baseline,
            bucket_event_ids=("e" * 64,),
        )

    monkeypatch.setattr(review_runtime, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(review_runtime, "execute_reviewed_decision", write)
    return decisions


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "children"),
    [("classification", 2), ("saturated", 2), ("auto_split", 1), ("auto_split", 2), ("split", 2)],
    ids=["classification", "saturated", "single-line", "auto-split", "split"],
)
async def test_an_agents_response_does_not_apply_a_proposal_to_a_row_the_person_classified(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    mode: _Mode,
    children: int,
) -> None:
    """Refused before the commit phase: the writer is not reached and no effect is declared."""
    case = _Case(authority_operation, mode)
    _classified_by(case, ClassificationOrigin.PERSON)
    checkpoint = case.checkpoint(case.operand(mode, children=children), "apply")
    decisions = _writer(monkeypatch, case)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        await _executor(case, _MCP).resume(case.request, checkpoint, case.context)

    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
    assert decisions == []
    assert case.events.phases == [] and case.events.effects == []
    assert case.operands.published is None


@pytest.mark.asyncio
async def test_an_agents_response_does_not_split_a_row_that_links_an_invoice_but_classifies_it_in_place(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The decision committed, not the mode asked for, is what the commit is held to."""
    split = _Case(authority_operation, "auto_split")
    _store(split, {"invoice_id": "c" * 64})
    refused_decisions = _writer(monkeypatch, split)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        await _executor(split, _MCP).resume(
            split.request, split.checkpoint(split.operand("auto_split", children=2), "apply"), split.context
        )

    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
    assert refused_decisions == [] and split.events.effects == []

    in_place = _Case(authority_operation, "auto_split")
    _store(in_place, {"invoice_id": "c" * 64})
    applied = _writer(monkeypatch, in_place)

    assert await _executor(in_place, _MCP).resume(
        in_place.request, in_place.checkpoint(in_place.operand("auto_split", children=1), "apply"), in_place.context
    )
    assert applied == [LlmReviewDecision.APPLY]


@pytest.mark.asyncio
async def test_an_agents_rejection_is_recorded_whoever_classified_the_row(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A rejection changes no row, so it replaces nothing the person decided."""
    case = _Case(authority_operation)
    _classified_by(case, ClassificationOrigin.PERSON)
    checkpoint = case.checkpoint(case.operand(), "reject")
    decisions = _writer(monkeypatch, case)

    assert await _executor(case, _MCP).resume(case.request, checkpoint, case.context)

    assert decisions == [LlmReviewDecision.REJECT]
    assert case.events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]


@pytest.mark.asyncio
@_PERSONS_FRONTENDS
@pytest.mark.parametrize(
    ("mode", "children", "decision"),
    [("classification", 2, LlmReviewDecision.APPLY), ("split", 2, LlmReviewDecision.SPLIT)],
    ids=["classification", "split"],
)
async def test_a_persons_response_applies_the_proposal_to_the_row_they_classified_as_before(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection | None,
    mode: _Mode,
    children: int,
    decision: LlmReviewDecision,
) -> None:
    case = _Case(authority_operation, mode)
    _classified_by(case, ClassificationOrigin.PERSON)
    checkpoint = case.checkpoint(case.operand(mode, children=children), "apply")
    decisions = _writer(monkeypatch, case)

    assert await _executor(case, frontend).resume(case.request, checkpoint, case.context)

    assert decisions == [decision]
    assert case.events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "children"),
    [("classification", 2), ("saturated", 2), ("split", 2)],
    ids=["classification", "saturated", "split"],
)
async def test_an_agents_response_is_refused_when_the_person_classified_the_row_after_the_proposal_was_made(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    mode: _Mode,
    children: int,
) -> None:
    """The stored row is read at the commit: the reviewed row was an agent's, and the row now stored is not."""
    case = _Case(authority_operation, mode)
    _classified_by(case, ClassificationOrigin.AGENT)
    checkpoint = case.checkpoint(case.operand(mode, children=children), "apply")
    reviewed = case.baseline
    _classified_by(case, ClassificationOrigin.PERSON)
    decisions = _writer(monkeypatch, case)
    loads_before = case.repository.loads

    with pytest.raises(ProfileAccessRefusedError) as refused:
        await _executor(case, _MCP).resume(case.request, checkpoint, case.context)

    assert reviewed.classification_origin is ClassificationOrigin.AGENT
    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
    assert case.repository.loads == loads_before + 1
    assert decisions == []
    assert case.events.phases == [] and case.events.effects == []
    assert case.operands.published is None


@pytest.mark.asyncio
@_PERSONS_FRONTENDS
async def test_a_persons_response_commits_without_the_stored_row_being_read_for_this(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection | None,
) -> None:
    """The person's frontends are held to nothing here, so they pay for no further read."""
    case = _Case(authority_operation)
    _classified_by(case, ClassificationOrigin.AGENT)
    checkpoint = case.checkpoint(case.operand(), "apply")
    _classified_by(case, ClassificationOrigin.PERSON)
    decisions = _writer(monkeypatch, case)
    loads_before = case.repository.loads

    assert await _executor(case, frontend).resume(case.request, checkpoint, case.context)

    assert decisions == [LlmReviewDecision.APPLY]
    assert case.repository.loads == loads_before
