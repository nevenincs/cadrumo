"""Execution stages for the existing guarded ledger LLM review workflow."""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import Settings
from ...core.hashing import content_hash_hex, sha256_hex
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.transactions.errors import TransactionNotFoundError, TransactionValidationError
from ...domain.transactions.models import Transaction
from ..operations.interactions import OperationResponseIntentValue
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext, OperationResumeCheckpoint
from ..operations.persistence.journal import serialize_operation_operand
from ..operations.registry import OperationSchemaBindingV1, operation_public_schema_reference
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts
from .id_resolution import resolve_transaction_id
from .llm_classification import saturate_llm_classification, suggest_evidence_split, suggest_llm_classification
from .llm_classification_ports import (
    LLMClassificationPorts,
    LLMSplitSuggestion,
)
from .llm_review_contracts import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LEDGER_SPLIT_REVIEW_DEFINITION_ID,
    LedgerLlmReviewProjection,
    LedgerLlmReviewRequest,
    LedgerLlmReviewResponse,
    LedgerLlmSuggestion,
    bound_ledger_llm_projection,
)
from .llm_review_operand import LedgerLlmReviewedOperand
from .llm_review_results import LedgerLlmExecutionResult, LedgerLlmOperationResult
from .llm_review_workflow import LlmReviewDecision, LlmReviewInvocationOrigin, execute_reviewed_decision
from .llm_review_writer_projection import (
    project_ledger_llm_writer_result,
    validate_ledger_llm_writer_effect,
)
from .persistence_ports import LedgerPersistenceConflictError


def ledger_llm_review_schemas(
    definition_id: str,
) -> tuple[OperationSchemaBindingV1, OperationSchemaBindingV1]:
    """Bind the closed review and authority-free response model pair."""
    return (
        OperationSchemaBindingV1.bind(
            schema_id=definition_id + ".projection", schema_version=1, model_type=LedgerLlmReviewProjection
        ),
        OperationSchemaBindingV1.bind(
            schema_id=definition_id + ".response", schema_version=1, model_type=LedgerLlmReviewResponse
        ),
    )


@dataclass(frozen=True, slots=True)
class LedgerLlmOperationPorts:
    """One exact-profile composition of the existing ledger and suggestion services."""

    ledger: LedgerActionPorts
    llm: LLMClassificationPorts
    settings: Settings


class LedgerLlmOperationPortsFactory(Protocol):
    """Compose providers only inside the immutable profile worker."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerLlmOperationPorts:
        """Return exact-profile ledger services and lazy suggestion ports."""
        ...


def project_captured_ledger_llm_review(operand: LedgerLlmReviewedOperand) -> LedgerLlmReviewProjection:
    """Copy one captured proposal without granting response authority."""
    return bound_ledger_llm_projection(
        LedgerLlmReviewProjection(
            profile_id=operand.request.profile_id,
            reviewed_proposal_digest=sha256_hex(serialize_operation_operand(operand)),
            suggestion=operand.suggestion,
        )
    )


def _expected_review_definition_id(request: LedgerLlmReviewRequest) -> str:
    return LEDGER_SPLIT_REVIEW_DEFINITION_ID if request.mode == "split" else LEDGER_CLASSIFY_REVIEW_DEFINITION_ID


def _require_review_profile_binding(
    request: OperationRequest[LedgerLlmReviewRequest],
    context: OperationExecutorContext,
    *,
    profile: str,
    definition_id: str,
) -> None:
    if (
        request.definition_id != definition_id
        or context.identity.definition_id != definition_id
        or request.subject_ref != profile_operation_subject(profile)
        or context.identity.subject_ref != request.subject_ref
        or require_active_bucket_id() != profile
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_owned_ledger_profile(
    ports: LedgerLlmOperationPorts,
    context: OperationExecutorContext,
    profile: str,
) -> None:
    if (
        ports.ledger.operation is not context.authority_operation
        or ports.ledger.transaction_repository.bucket_id != profile
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_dependency_profiles(ports: LedgerLlmOperationPorts, profile: str) -> None:
    for repository in (
        ports.ledger.invoice_repository,
        ports.ledger.work_unit_repository,
        ports.ledger.calculation_repository,
    ):
        if getattr(repository, "bucket_id", None) != profile:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if any(record.bucket_id != profile for record in ports.ledger.purchase_invoice_evidence_records):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


async def _resolve_reviewed_continuation(
    request: OperationRequest[LedgerLlmReviewRequest],
    checkpoint: OperationResumeCheckpoint,
    context: OperationExecutorContext,
) -> tuple[str, LedgerLlmReviewedOperand]:
    digest = checkpoint.reviewed_proposal_digest
    with validating_governed_facts(context.authority_operation):
        operand = await context.operands.resolve(digest, LedgerLlmReviewedOperand)
    if (
        operand.request != request.payload
        or operand.identity != context.identity
        or operand.authority_generation != context.authority_operation.generation.logical_generation
    ):
        raise LedgerPersistenceConflictError("ledger review request or authority generation changed")
    if sha256_hex(serialize_operation_operand(operand)) != digest:
        raise LedgerPersistenceConflictError("ledger reviewed operand digest changed")
    return digest, operand


def _review_response_action(
    checkpoint: OperationResumeCheckpoint,
    operand: LedgerLlmReviewedOperand,
) -> OperationResponseIntentValue:
    response_action = checkpoint.response_action
    if response_action is None or response_action not in {"apply", "reject"}:
        raise TransactionValidationError("ledger review response has no declared intent")
    if response_action == "apply" and operand.request.origin is LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT:
        raise TransactionValidationError("explicit rejection invocation cannot apply a proposal")
    return response_action


def _review_decision(response_action: OperationResponseIntentValue, suggestion: object) -> LlmReviewDecision:
    if response_action == "reject":
        return LlmReviewDecision.REJECT
    if isinstance(suggestion, LLMSplitSuggestion) and suggestion.recommends_split:
        return LlmReviewDecision.SPLIT
    return LlmReviewDecision.APPLY


async def _commit_reviewed_decision(
    *,
    context: OperationExecutorContext,
    digest: str,
    operand: LedgerLlmReviewedOperand,
    baseline: Transaction,
    suggestion: LedgerLlmSuggestion,
    ports: LedgerLlmOperationPorts,
    response_action: OperationResponseIntentValue,
    decision: LlmReviewDecision,
) -> str:
    await context.events.phase("ledger.llm.commit")

    async def commit() -> str:
        async with context.cancellation.irreversible_section():
            await context.events.effect(OperationEffect.UNKNOWN)

            def write() -> BaseModel:
                with validating_governed_facts(context.authority_operation):
                    return execute_reviewed_decision(
                        suggestion,
                        origin=operand.request.origin,
                        decision=decision,
                        bucket_id=str(operand.request.profile_id),
                        business_pct=Decimal(operand.request.business_pct)
                        if operand.request.business_pct is not None
                        else None,
                        reason=operand.request.reason,
                        actor=operand.request.actor or str(operand.request.profile_id),
                        ports=ports.ledger,
                        settings=ports.settings,
                        expected_current=baseline,
                    )

            try:
                written = await asyncio.to_thread(write)
            except (LedgerPersistenceConflictError, TransactionNotFoundError, TransactionValidationError):
                await context.events.effect(OperationEffect.NONE)
                raise
            effect = validate_ledger_llm_writer_effect(
                written,
                operand=operand,
                baseline=baseline,
                decision=decision,
            )
            await context.events.effect(effect)

            def project() -> LedgerLlmOperationResult:
                with validating_governed_facts(context.authority_operation):
                    return project_ledger_llm_writer_result(
                        written,
                        operand=operand,
                        baseline=baseline,
                        digest=digest,
                    )

            result = await asyncio.to_thread(project)
            execution = LedgerLlmExecutionResult(
                identity=context.identity,
                request=operand.request,
                response=response_action,
                result=result,
            )
            return await context.operands.put(execution, written_at=now())

    return await await_cancellation_complete(commit(), task_name="ledger-llm-reviewed-commit")


class LedgerLlmReviewExecutor:
    """Acquire once and resume existing writers from the persisted reviewed operand."""

    def __init__(self, factory: LedgerLlmOperationPortsFactory) -> None:
        """Retain the trusted profile-worker composition."""
        self._factory = factory

    def _ports(
        self, request: OperationRequest[LedgerLlmReviewRequest], context: OperationExecutorContext
    ) -> LedgerLlmOperationPorts:
        """Require every dependent ledger repository to retain the exact profile."""
        payload = request.payload
        profile = str(payload.profile_id)
        expected_id = _expected_review_definition_id(payload)
        _require_review_profile_binding(request, context, profile=profile, definition_id=expected_id)
        ports = self._factory(bucket_id=profile, operation=context.authority_operation)
        _require_owned_ledger_profile(ports, context, profile)
        _require_dependency_profiles(ports, profile)
        return ports

    async def execute(
        self, request: OperationRequest[LedgerLlmReviewRequest], context: OperationExecutorContext
    ) -> str | None:
        """Capture once, then settle a preview or publish the secure REVIEW checkpoint."""
        ports = self._ports(request, context)
        payload = request.payload
        await context.events.phase("ledger.llm.acquire")

        def acquire() -> LedgerLlmReviewedOperand:
            with validating_governed_facts(context.authority_operation):
                catalogue = ports.ledger.transaction_repository.load()
                transaction_id = resolve_transaction_id(payload.transaction_id, catalogue.transactions)
                baseline = catalogue.transactions[transaction_id]
                suggest = (
                    suggest_evidence_split
                    if payload.mode in {"split", "auto_split"}
                    else saturate_llm_classification
                    if payload.mode == "saturated"
                    else suggest_llm_classification
                )
                suggestion = suggest(
                    bucket_id=str(payload.profile_id),
                    transaction_id=transaction_id,
                    operation=context.authority_operation,
                    transaction_repository=ports.ledger.transaction_repository,
                    read_evidence=payload.read_evidence,
                    vision_model=payload.vision_model,
                    settings=ports.settings,
                    ports=ports.llm,
                    reviewed_transaction=baseline,
                )
                return LedgerLlmReviewedOperand.capture(
                    identity=context.identity,
                    request=payload,
                    baseline=baseline,
                    suggestion=suggestion,
                    authority_generation=context.authority_operation.generation.logical_generation,
                )

        operand = await asyncio.to_thread(acquire)
        if payload.preview:
            digest = sha256_hex(serialize_operation_operand(operand))
            stored = await context.operands.put(operand, written_at=now())
            if stored != digest:
                raise ValueError("preview operand storage returned another proposal")
            projection = project_captured_ledger_llm_review(operand)
            result = bound_ledger_llm_projection(
                LedgerLlmOperationResult(
                    profile_id=payload.profile_id,
                    reviewed_proposal_digest=digest,
                    outcome="preview",
                    transaction_id=operand.suggestion.transaction_id,
                    preview=projection,
                    provenance=operand.suggestion.provenance,
                )
            )
            await context.events.effect(OperationEffect.NONE)
            return await context.operands.put(
                LedgerLlmExecutionResult(identity=context.identity, request=payload, response="preview", result=result),
                written_at=now(),
            )
        await context.events.phase("ledger.llm.review")
        _, response = ledger_llm_review_schemas(request.definition_id)
        digest = sha256_hex(serialize_operation_operand(operand))
        await context.interactions.publish_review(
            interaction_id=secrets.token_hex(32),
            identity=context.identity,
            revision=context.revision + 1,
            presentation_code="ledger.llm.review-ready",
            response_schema_ref=operation_public_schema_reference(response.identity),
            continuation_digest=content_hash_hex({"operation_id": context.identity.operation_id, "proposal": digest}),
            expires_at=None,
            reviewed_operand=operand,
            baseline_digest=sha256_hex(operand.baseline_json.encode("utf-8")),
            proposed_effect_digest=digest,
        )

    async def resume(
        self,
        request: OperationRequest[LedgerLlmReviewRequest],
        checkpoint: OperationResumeCheckpoint,
        context: OperationExecutorContext,
    ) -> str | None:
        """Validate the consumed continuation and invoke its original guarded writer."""
        if request.payload.preview:
            raise ValueError("terminal preview has no resumable response")
        if not checkpoint.consumed:
            return None
        digest, operand = await _resolve_reviewed_continuation(request, checkpoint, context)
        response_action = _review_response_action(checkpoint, operand)
        baseline, suggestion = operand.decode(context.authority_operation)
        ports = self._ports(request, context)
        decision = _review_decision(response_action, suggestion)
        return await _commit_reviewed_decision(
            context=context,
            digest=digest,
            operand=operand,
            baseline=baseline,
            suggestion=suggestion,
            ports=ports,
            response_action=response_action,
            decision=decision,
        )
