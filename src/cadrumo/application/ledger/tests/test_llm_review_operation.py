"""Registered LLM reviews bind exact operands, identities, and truthful effects."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config import Settings
from ....core.hashing import sha256_hex
from ....core.operations import (
    OperationEffect,
    OperationInteractionKind,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import BucketTransactionRef, Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.interactions import OperationInteractionRequest
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext, OperationResumeCheckpoint
from ...operations.persistence.journal import serialize_operation_operand
from ...operations.registry import OperationFrontendProjection, OperationRegistry, operation_public_schema_reference
from ...user_profile.access_contracts import AccessAction, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import llm_review_operation as operation
from ..action_ports import LedgerActionPorts
from ..llm_classification_ports import (
    LLMClassificationPorts,
    LLMClassificationSuggestion,
    LLMSaturatedSuggestion,
    LLMSplitApplyResult,
    LLMSplitChildSuggestion,
    LLMSplitSuggestion,
    LLMSuggestionRejectionResult,
)
from ..llm_review_workflow import LlmReviewDecision, LlmReviewInvocationOrigin
from ..models import ManualLedgerTransactionResult
from ..persistence_ports import LedgerPersistenceConflictError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_Mode = Literal["classification", "saturated", "auto_split", "split"]
_ORIGINS = {
    "classification": LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
    "saturated": LlmReviewInvocationOrigin.CLASSIFY_LLM_SATURATE_APPLY,
    "auto_split": LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT,
    "split": LlmReviewInvocationOrigin.SPLIT_LLM,
}


def _baseline() -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="reviewed-executor-row",
                booked_date=date(2026, 4, 15),
                amount=Decimal("121.00"),
                currency="EUR",
                description="synthetic reviewed row",
                provenance=RawProvenance(
                    source_path=Path("synthetic-review.csv"),
                    source_sha256="c" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2026, 4, 15, tzinfo=UTC),
                    provider_name="csv",
                ),
                raw_fields={"source": "synthetic"},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
        }
    )


def _payload(mode: _Mode, transaction_id: str) -> operation.LedgerLlmReviewRequest:
    return operation.LedgerLlmReviewRequest(
        profile_id=_PROFILE,
        transaction_id=transaction_id,
        mode=mode,
        origin=_ORIGINS[mode],
        reason="reviewed decline",
    )


def _identity(payload: operation.LedgerLlmReviewRequest) -> OperationIdentity:
    return OperationIdentity(
        operation_id="a" * 64,
        definition_id=operation._definition_id(payload),
        subject_ref=profile_operation_subject(str(payload.profile_id)),
    )


def _suggestion(baseline: Transaction, mode: _Mode, *, children: int = 2) -> operation._Suggestion:
    common = {
        "transaction_id": baseline.transaction_id,
        "provenance": "llm:local-text:test",
        "reason": "synthetic review",
    }
    if mode in {"auto_split", "split"}:
        return LLMSplitSuggestion(
            **common,
            parent_amount=baseline.raw.amount,
            children=tuple(
                LLMSplitChildSuggestion(
                    proportion=Decimal(1) / children,
                    amount=baseline.raw.amount / children,
                    description=f"synthetic component {index}",
                )
                for index in range(children)
            ),
        )
    basic = LLMClassificationSuggestion(
        **common,
        classification=BusinessClassification.BUSINESS,
        confidence=Decimal("0.9000"),
    )
    return LLMSaturatedSuggestion.model_validate(basic.model_dump()) if mode == "saturated" else basic


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, phase: str) -> None:
        self.phases.append(phase)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Operands:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}
        self.published: BaseModel | None = None

    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        data = serialize_operation_operand(operand)
        digest = sha256_hex(data)
        self.values[digest] = data
        self.published = operand
        return digest

    async def resolve[ModelT: BaseModel](self, digest: str, model_type: type[ModelT]) -> ModelT:
        return model_type.model_validate_json(self.values[digest])


class _Interactions:
    def __init__(self, operands: _Operands) -> None:
        self.operands = operands
        self.published: dict[str, object] | None = None

    async def publish_review(self, **kwargs: object) -> None:
        self.published = kwargs
        operand = kwargs["reviewed_operand"]
        assert isinstance(operand, operation.LedgerLlmReviewedOperand)
        await self.operands.put(operand, written_at=datetime(2026, 4, 15, tzinfo=UTC))


class _Repository:
    def __init__(self, baseline: Transaction) -> None:
        self.bucket_id = str(_PROFILE)
        self.catalogue = TransactionCatalogue.from_transactions((baseline,))
        self.loads = 0

    def load(self) -> TransactionCatalogue:
        self.loads += 1
        return self.catalogue


class _Case:
    def __init__(self, authority: PinnedAuthorityOperation, mode: _Mode = "classification") -> None:
        self.baseline = _baseline()
        self.payload = _payload(mode, self.baseline.transaction_id[:12])
        self.identity = _identity(self.payload)
        self.request = OperationRequest[operation.LedgerLlmReviewRequest](
            definition_id=self.identity.definition_id,
            subject_ref=self.identity.subject_ref,
            payload=self.payload,
        )
        self.repository = _Repository(self.baseline)
        named = SimpleNamespace(bucket_id=str(_PROFILE))
        # Only the existing executor's declared ports are controlled here. No
        # persistence or provider engine is introduced by this unit fixture.
        self.ledger = cast(
            LedgerActionPorts,
            SimpleNamespace(
                operation=authority,
                transaction_repository=self.repository,
                invoice_repository=named,
                work_unit_repository=named,
                calculation_repository=named,
                purchase_invoice_evidence_records=(),
            ),
        )
        self.ports = operation.LedgerLlmOperationPorts(
            ledger=self.ledger,
            llm=cast(LLMClassificationPorts, object()),
            settings=cast(Settings, object()),
        )
        self.events = _Events()
        self.operands = _Operands()
        self.interactions = _Interactions(self.operands)
        self.in_commit = False

        @asynccontextmanager
        async def irreversible_section():
            self.in_commit = True
            try:
                yield
            finally:
                self.in_commit = False

        self.context = cast(
            OperationExecutorContext,
            SimpleNamespace(
                identity=self.identity,
                revision=0,
                authority_operation=authority,
                events=self.events,
                operands=self.operands,
                interactions=self.interactions,
                cancellation=SimpleNamespace(irreversible_section=irreversible_section),
            ),
        )

    def factory(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> operation.LedgerLlmOperationPorts:
        assert bucket_id == str(_PROFILE) and operation is self.ledger.operation
        return self.ports

    def operand(self, mode: _Mode = "classification", *, children: int = 2) -> operation.LedgerLlmReviewedOperand:
        return operation.LedgerLlmReviewedOperand.capture(
            identity=self.identity,
            request=self.payload,
            baseline=self.baseline,
            authority_generation=self.context.authority_operation.generation.logical_generation,
            suggestion=_suggestion(self.baseline, mode, children=children),
        )

    def checkpoint(
        self, operand: operation.LedgerLlmReviewedOperand, response: str = "apply"
    ) -> OperationResumeCheckpoint:
        data = serialize_operation_operand(operand)
        digest = sha256_hex(data)
        self.operands.values[digest] = data
        return cast(
            OperationResumeCheckpoint,
            SimpleNamespace(
                consumed=True,
                reviewed_proposal_digest=digest,
                response_action=response,
            ),
        )


@pytest.mark.parametrize("mode", ["classification", "split"])
def test_registration_binds_canonical_models_and_separate_response_authority(mode: _Mode) -> None:
    def unused_factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> operation.LedgerLlmOperationPorts:
        raise AssertionError("registration must not acquire providers")

    payload = _payload(mode, "b" * 12)
    definition = operation.build_ledger_llm_review_definition(operation._definition_id(payload), unused_factory)
    registration = operation.build_ledger_llm_review_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    decoded = registry.decode_request_payload(definition.definition_id, payload.model_dump_json())
    assert decoded == payload
    assert definition.result_type is operation.LedgerLlmExecutionResult
    assert registration.result_projector is not None and registration.review_projector is not None
    for action in (AccessAction.SUBMIT, AccessAction.COMMIT, AccessAction.REVIEW, AccessAction.RESPOND):
        context = OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=action,
            frontend=OperationFrontendProjection.MCP,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
        )
        resolved = resolve_operation_access(
            registry=registry,
            request=OperationRequest[BaseModel](
                definition_id=definition.definition_id,
                subject_ref=profile_operation_subject(str(_PROFILE)),
                payload=payload,
            ),
            context=context,
        )
        assert action in resolved.policy.actions and not resolved.policy.transaction_authority_required


def test_request_normalizes_supported_prefix_and_preserves_rejection_origin() -> None:
    request = _payload("classification", "  ABCDEF123456  ")
    assert request.transaction_id == "abcdef123456"
    rejected = operation.LedgerLlmReviewRequest(
        profile_id=_PROFILE,
        transaction_id="b" * 12,
        mode="auto_split",
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
    )
    assert operation.LedgerLlmReviewRequest.model_validate_json(rejected.model_dump_json()) == rejected
    with pytest.raises(ValidationError, match="mode and invocation origin"):
        operation.LedgerLlmReviewRequest(
            profile_id=_PROFILE,
            transaction_id="b" * 12,
            mode="split",
            origin=LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["classification", "saturated", "auto_split", "split"])
async def test_acquisition_uses_exact_captured_row_and_review_projector_binds_invocation(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    mode: _Mode,
) -> None:
    case = _Case(authority_operation, mode)
    suggestion = _suggestion(case.baseline, mode)
    producer_calls: list[dict[str, object]] = []

    def producer(**kwargs: object) -> operation._Suggestion:
        producer_calls.append(kwargs)
        assert kwargs["reviewed_transaction"] is case.baseline
        return suggestion

    terminal = (
        "suggest_evidence_split"
        if mode in {"auto_split", "split"}
        else "saturate_llm_classification"
        if mode == "saturated"
        else "suggest_llm_classification"
    )
    monkeypatch.setattr(operation, terminal, producer)
    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    await operation.LedgerLlmReviewExecutor(case.factory).execute(case.request, case.context)
    assert case.repository.loads == 1 and len(producer_calls) == 1
    assert case.events.phases == ["ledger.llm.acquire", "ledger.llm.review"]
    published = case.interactions.published
    assert published is not None
    operand = published["reviewed_operand"]
    assert isinstance(operand, operation.LedgerLlmReviewedOperand)
    baseline, decoded = operand.decode(authority_operation)
    assert baseline == case.baseline and decoded == suggestion
    _, response = operation._schemas(case.identity.definition_id)
    interaction = OperationInteractionRequest(
        interaction_id="c" * 64,
        identity=case.identity,
        revision=1,
        kind=OperationInteractionKind.REVIEW,
        presentation_code="ledger.llm.review-ready",
        response_schema_ref=operation_public_schema_reference(response.identity),
        continuation_digest=cast(str, published["continuation_digest"]),
    )
    projection = operation._review_projector(operand, interaction)
    assert isinstance(projection, operation.LedgerLlmReviewProjection)
    assert projection.reviewed_proposal_digest == sha256_hex(serialize_operation_operand(operand))
    if mode in {"classification", "saturated"}:
        assert projection.suggestion.confidence == "0.9000"
    else:
        assert projection.suggestion.parent_amount == "121.00"
        assert projection.suggestion.children[0].amount == "60.50"
    with pytest.raises(ValueError, match="another invocation"):
        operation._review_projector(
            operand,
            interaction.model_copy(
                update={
                    "identity": case.identity.model_copy(update={"operation_id": "f" * 64}),
                }
            ),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "repository_name",
    ["transaction_repository", "invoice_repository", "work_unit_repository", "calculation_repository"],
)
async def test_foreign_dependent_repository_refuses_before_provider(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    repository_name: str,
) -> None:
    case = _Case(authority_operation)
    setattr(case.ledger, repository_name, SimpleNamespace(bucket_id=str(_OTHER_PROFILE)))
    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    with pytest.raises(ProfileAccessRefusedError):
        await operation.LedgerLlmReviewExecutor(case.factory).execute(case.request, case.context)
    assert not case.events.phases and case.repository.loads == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["conflict", "validation", "projection", "foreign-result", "none"])
async def test_resume_preserves_exact_baseline_and_distinguishes_prewrite_from_postwrite_failures(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    fault: str,
) -> None:
    case = _Case(authority_operation)
    operand = case.operand()
    checkpoint = case.checkpoint(operand)
    writer_calls: list[dict[str, object]] = []
    result = ManualLedgerTransactionResult(
        ref=BucketTransactionRef(
            bucket_id=str(_OTHER_PROFILE if fault == "foreign-result" else _PROFILE),
            transaction_id=case.baseline.transaction_id,
        ),
        transaction=case.baseline,
        bucket_event_ids=("e" * 64,),
    )

    def writer(suggestion: object, **kwargs: object) -> ManualLedgerTransactionResult:
        assert case.in_commit and suggestion == operand.decode(authority_operation)[1]
        assert kwargs["expected_current"] == case.baseline
        assert kwargs["origin"] is case.payload.origin
        writer_calls.append(kwargs)
        if fault == "conflict":
            raise LedgerPersistenceConflictError("stale reviewed row")
        if fault == "validation":
            raise TransactionValidationError("pre-write validation")
        return result

    def failed_projection(_result: ManualLedgerTransactionResult):
        raise TransactionValidationError("post-write projection failure")

    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation, "execute_reviewed_decision", writer)
    if fault == "projection":
        monkeypatch.setattr(operation, "ledger_transaction_result_payload", failed_projection)
    executor = operation.LedgerLlmReviewExecutor(case.factory)
    if fault == "none":
        reference = await executor.resume(case.request, checkpoint, case.context)
        assert reference is not None
        execution = case.operands.published
        assert isinstance(execution, operation.LedgerLlmExecutionResult)
        receipt = OperationTerminalReceipt(
            identity=case.identity,
            revision=2,
            condition=OperationTerminalCondition.SUCCEEDED,
            effect=OperationEffect.UPDATED,
            settled_at=datetime(2026, 4, 15, tzinfo=UTC),
            result_ref=reference,
        )
        assert operation._result_projector(execution, receipt) == execution.result
        for changed in (
            {"effect": OperationEffect.NONE},
            {"result_ref": "f" * 64},
            {"identity": case.identity.model_copy(update={"operation_id": "f" * 64})},
        ):
            with pytest.raises(ValueError, match="terminal receipt"):
                operation._result_projector(execution, receipt.model_copy(update=changed))
    else:
        error_type = (
            LedgerPersistenceConflictError
            if fault == "conflict"
            else ValueError
            if fault == "foreign-result"
            else TransactionValidationError
        )
        with pytest.raises(error_type):
            await executor.resume(case.request, checkpoint, case.context)
        assert case.operands.published is None
    expected = (
        OperationEffect.NONE
        if fault in {"conflict", "validation"}
        else OperationEffect.UNKNOWN
        if fault == "foreign-result"
        else OperationEffect.UPDATED
    )
    expected_effects = (
        [OperationEffect.UNKNOWN] if expected is OperationEffect.UNKNOWN else [OperationEffect.UNKNOWN, expected]
    )
    assert case.events.effects == expected_effects
    assert len(writer_calls) == 1 and not case.in_commit and case.repository.loads == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["request", "identity", "generation", "projection", "reject-apply"])
async def test_resume_refuses_mismatched_secure_operand_before_any_writer(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    mismatch: str,
) -> None:
    case = _Case(authority_operation)
    operand = case.operand()
    if mismatch == "request":
        operand = operand.model_copy(
            update={"request": case.payload.model_copy(update={"reason": "another invocation"})}
        )
    elif mismatch == "identity":
        operand = operand.model_copy(update={"identity": case.identity.model_copy(update={"operation_id": "f" * 64})})
    elif mismatch == "generation":
        operand = operand.model_copy(update={"authority_generation": "f" * 64})
    elif mismatch == "projection":
        operand = operand.model_copy(
            update={"suggestion": operand.suggestion.model_copy(update={"reason": "unreviewed proposal"})}
        )
    else:
        case.payload = case.payload.model_copy(update={"origin": LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT})
        case.request = case.request.model_copy(update={"payload": case.payload})
        operand = operand.model_copy(update={"request": case.payload})
    checkpoint = case.checkpoint(operand)

    def forbidden_writer(*args: object, **kwargs: object) -> BaseModel:
        raise AssertionError("invalid continuation reached its writer")

    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation, "execute_reviewed_decision", forbidden_writer)
    error_type = TransactionValidationError if mismatch == "reject-apply" else LedgerPersistenceConflictError
    with pytest.raises(error_type):
        await operation.LedgerLlmReviewExecutor(case.factory).resume(case.request, checkpoint, case.context)
    assert not case.events.effects and case.operands.published is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,response,children", [("auto_split", "apply", 1), ("split", "apply", 2), ("auto_split", "reject", 2)]
)
async def test_resume_routes_single_classification_split_and_audit_rejection(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    mode: _Mode,
    response: str,
    children: int,
) -> None:
    case = _Case(authority_operation, mode)
    operand = case.operand(mode, children=children)
    checkpoint = case.checkpoint(operand, response)
    decisions: list[LlmReviewDecision] = []

    def writer(_suggestion: object, **kwargs: object) -> BaseModel:
        decisions.append(cast(LlmReviewDecision, kwargs["decision"]))
        if response == "reject":
            return LLMSuggestionRejectionResult(
                bucket_id=str(_PROFILE),
                transaction_id=case.baseline.transaction_id,
                bucket_event_id="e" * 64,
                suggestion_kind="split",
                provenance=operand.suggestion.provenance,
                operator_reason=case.payload.reason,
            )
        if children == 1:
            return ManualLedgerTransactionResult(
                ref=BucketTransactionRef(bucket_id=str(_PROFILE), transaction_id=case.baseline.transaction_id),
                transaction=case.baseline,
                bucket_event_ids=("e" * 64,),
            )
        return LLMSplitApplyResult(
            bucket_id=str(_PROFILE),
            parent_transaction_id=case.baseline.transaction_id,
            split_group_id="synthetic-group",
            child_transaction_ids=("d" * 64, "e" * 64),
            classified_child_count=2,
            provenance=operand.suggestion.provenance,
        )

    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation, "execute_reviewed_decision", writer)
    assert await operation.LedgerLlmReviewExecutor(case.factory).resume(case.request, checkpoint, case.context)
    expected = (
        LlmReviewDecision.REJECT
        if response == "reject"
        else LlmReviewDecision.APPLY
        if children == 1
        else LlmReviewDecision.SPLIT
    )
    assert decisions == [expected] and case.events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert isinstance(case.operands.published, operation.LedgerLlmExecutionResult)
    assert case.operands.published.result.outcome == (
        "rejected" if response == "reject" else "classified" if children == 1 else "split"
    )


@pytest.mark.parametrize("outcome", ["classified", "split", "rejected"])
def test_public_result_refuses_facts_from_another_outcome(
    authority_operation: PinnedAuthorityOperation,
    outcome: str,
) -> None:
    case = _Case(authority_operation)
    operand = case.operand()
    if outcome == "classified":
        result: BaseModel = ManualLedgerTransactionResult(
            ref=BucketTransactionRef(bucket_id=str(_PROFILE), transaction_id=case.baseline.transaction_id),
            transaction=case.baseline,
            bucket_event_ids=("e" * 64,),
        )
    elif outcome == "split":
        result = LLMSplitApplyResult(
            bucket_id=str(_PROFILE),
            parent_transaction_id=case.baseline.transaction_id,
            split_group_id="synthetic-group",
            child_transaction_ids=("d" * 64, "e" * 64),
            classified_child_count=2,
            provenance=operand.suggestion.provenance,
        )
    else:
        result = LLMSuggestionRejectionResult(
            bucket_id=str(_PROFILE),
            transaction_id=case.baseline.transaction_id,
            bucket_event_id="e" * 64,
            suggestion_kind="classification",
            provenance=operand.suggestion.provenance,
        )
    projected = operation._writer_projection(result, operand=operand, baseline=case.baseline, digest="f" * 64)
    changed = (
        {**projected.model_dump(), "child_transaction_ids": ("a" * 64,)}
        if outcome == "rejected"
        else {**projected.model_dump(), "bucket_event_id": "f" * 64}
    )
    with pytest.raises(ValidationError):
        operation.LedgerLlmOperationResult.model_validate(changed)


@pytest.mark.parametrize("bad_json", ['{"transaction_id":"a","transaction_id":"b"}', '{"transaction_id":NaN}'])
def test_reviewed_operand_refuses_ambiguous_or_nonfinite_domain_json(
    authority_operation: PinnedAuthorityOperation,
    bad_json: str,
) -> None:
    case = _Case(authority_operation)
    operand = case.operand()
    with pytest.raises(ValidationError):
        operation.LedgerLlmReviewedOperand.model_validate({**operand.model_dump(), "baseline_json": bad_json})


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["classification", "saturated", "auto_split", "split"])
async def test_terminal_preview_captures_exact_proposal_without_pending_review_or_writer(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    mode: _Mode,
) -> None:
    case = _Case(authority_operation, mode)
    case.payload = operation.LedgerLlmReviewRequest.model_validate({**case.payload.model_dump(), "preview": True})
    case.request = case.request.model_copy(update={"payload": case.payload})
    suggestion = _suggestion(case.baseline, mode)
    calls: list[dict[str, object]] = []

    def producer(**kwargs: object) -> operation._Suggestion:
        calls.append(kwargs)
        assert kwargs["reviewed_transaction"] is case.baseline
        return suggestion

    def forbidden_writer(*args: object, **kwargs: object) -> BaseModel:
        raise AssertionError("terminal preview must not invoke a domain writer")

    async def forbidden_review(**kwargs: object) -> None:
        raise AssertionError("terminal preview must not retain a pending interaction")

    producer_name = (
        "suggest_evidence_split"
        if mode in {"auto_split", "split"}
        else "saturate_llm_classification"
        if mode == "saturated"
        else "suggest_llm_classification"
    )
    monkeypatch.setattr(operation, producer_name, producer)
    monkeypatch.setattr(operation, "execute_reviewed_decision", forbidden_writer)
    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(case.interactions, "publish_review", forbidden_review)
    reference = await operation.LedgerLlmReviewExecutor(case.factory).execute(case.request, case.context)
    assert reference is not None
    assert case.repository.loads == 1 and len(calls) == 1
    assert case.interactions.published is None and not case.in_commit
    assert case.events.effects == [OperationEffect.NONE]
    assert "ledger.llm.review" not in case.events.phases and "ledger.llm.commit" not in case.events.phases
    execution = await case.operands.resolve(reference, operation.LedgerLlmExecutionResult)
    assert execution.identity == case.identity and execution.request == case.payload
    assert execution.response == "preview" and execution.result.outcome == "preview"
    preview = execution.result.preview
    assert preview is not None
    captured = operation.LedgerLlmReviewedOperand.capture(
        identity=case.identity,
        request=case.payload,
        baseline=case.baseline,
        authority_generation=authority_operation.generation.logical_generation,
        suggestion=suggestion,
    )
    expected_digest = sha256_hex(serialize_operation_operand(captured))
    assert preview.profile_id == execution.result.profile_id == _PROFILE
    assert preview.suggestion.transaction_id == execution.result.transaction_id == case.baseline.transaction_id
    assert preview.suggestion.provenance == execution.result.provenance == suggestion.provenance
    assert preview.suggestion == captured.suggestion
    assert preview.reviewed_proposal_digest == execution.result.reviewed_proposal_digest == expected_digest
    assert reference == sha256_hex(serialize_operation_operand(execution))
    receipt = OperationTerminalReceipt(
        identity=case.identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=datetime(2026, 4, 15, tzinfo=UTC),
        result_ref=reference,
    )
    assert operation._result_projector(execution, receipt) == execution.result
    for changed in (
        {"effect": OperationEffect.UPDATED},
        {"result_ref": "f" * 64},
        {"identity": case.identity.model_copy(update={"operation_id": "f" * 64})},
        {"condition": OperationTerminalCondition.REFUSED},
    ):
        with pytest.raises(ValueError, match="terminal receipt"):
            operation._result_projector(execution, receipt.model_copy(update=changed))


@pytest.mark.parametrize(
    "mismatch",
    ["request", "response", "profile", "transaction", "provenance", "digest", "kind", "missing-preview", "mutation"],
)
def test_terminal_preview_refuses_cross_invocation_and_mutation_facts(
    authority_operation: PinnedAuthorityOperation,
    mismatch: str,
) -> None:
    case = _Case(authority_operation)
    payload = operation.LedgerLlmReviewRequest.model_validate({**case.payload.model_dump(), "preview": True})
    preview = operation.LedgerLlmReviewProjection(
        profile_id=_PROFILE,
        reviewed_proposal_digest="d" * 64,
        suggestion=case.operand().suggestion,
    )
    result = operation.LedgerLlmOperationResult(
        outcome="preview",
        profile_id=_PROFILE,
        reviewed_proposal_digest=preview.reviewed_proposal_digest,
        transaction_id=case.baseline.transaction_id,
        provenance=preview.suggestion.provenance,
        preview=preview,
    )
    execution = operation.LedgerLlmExecutionResult(
        identity=case.identity, request=payload, response="preview", result=result
    )
    changed = execution.model_dump()
    if mismatch == "request":
        changed["request"]["preview"] = False
    elif mismatch == "response":
        changed["response"] = "apply"
    elif mismatch == "profile":
        changed["result"]["preview"]["profile_id"] = _OTHER_PROFILE
    elif mismatch == "transaction":
        changed["result"]["preview"]["suggestion"]["transaction_id"] = "f" * 64
    elif mismatch == "provenance":
        changed["result"]["preview"]["suggestion"]["provenance"] = "llm:another-provider:test"
    elif mismatch == "digest":
        changed["result"]["preview"]["reviewed_proposal_digest"] = "f" * 64
    elif mismatch == "kind":
        changed["result"]["preview"]["suggestion"]["kind"] = "saturated"
    elif mismatch == "missing-preview":
        changed["result"]["preview"] = None
    else:
        changed["result"]["bucket_event_id"] = "e" * 64
    with pytest.raises(ValidationError):
        operation.LedgerLlmExecutionResult.model_validate(changed)


@pytest.mark.asyncio
async def test_terminal_preview_cannot_be_reopened_as_pending_review_or_resumed_mutation(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    case = _Case(authority_operation)
    case.payload = operation.LedgerLlmReviewRequest.model_validate({**case.payload.model_dump(), "preview": True})
    case.request = case.request.model_copy(update={"payload": case.payload})
    operand = case.operand()
    _, response = operation._schemas(case.identity.definition_id)
    interaction = OperationInteractionRequest(
        interaction_id="c" * 64,
        identity=case.identity,
        revision=1,
        kind=OperationInteractionKind.REVIEW,
        presentation_code="ledger.llm.review-ready",
        response_schema_ref=operation_public_schema_reference(response.identity),
        continuation_digest="d" * 64,
    )
    with pytest.raises(ValueError, match="invalid ledger reviewed operand"):
        operation._review_projector(operand, interaction)

    def forbidden_writer(*args: object, **kwargs: object) -> BaseModel:
        raise AssertionError("terminal preview cannot authorize a resumed mutation")

    monkeypatch.setattr(operation, "execute_reviewed_decision", forbidden_writer)
    with pytest.raises(ValueError, match="terminal preview"):
        await operation.LedgerLlmReviewExecutor(case.factory).resume(
            case.request, case.checkpoint(operand), case.context
        )
    assert not case.events.effects and case.operands.published is None
