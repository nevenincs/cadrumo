"""Registered review and guarded commit of existing ledger classification services."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.hashing import sha256_hex
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationTerminalCondition,
)
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.interactions import OperationInteractionRequest
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.persistence.journal import serialize_operation_operand
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
    operation_public_schema_reference,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .llm_review_contracts import (
    LEDGER_LLM_REVIEW_DEFINITION_IDS,
    LedgerLlmReviewRequest,
    bound_ledger_llm_projection,
    ledger_llm_review_definition_id,
)
from .llm_review_execution import (
    LedgerLlmOperationPortsFactory,
    LedgerLlmReviewExecutor,
    ledger_llm_review_schemas,
    project_captured_ledger_llm_review,
)
from .llm_review_operand import LedgerLlmReviewedOperand
from .llm_review_results import LedgerLlmExecutionResult, LedgerLlmOperationResult
from .read_access import resolve_ledger_read_access


def _review_projector(operand: BaseModel, interaction: OperationInteractionRequest) -> BaseModel:
    """Release only this invocation's digest-bound authority-free review facts."""
    if not isinstance(operand, LedgerLlmReviewedOperand) or operand.request.preview:
        raise ValueError("invalid ledger reviewed operand")
    _, response = ledger_llm_review_schemas(ledger_llm_review_definition_id(operand.request))
    if (
        interaction.identity != operand.identity
        or interaction.kind is not OperationInteractionKind.REVIEW
        or interaction.presentation_code != "ledger.llm.review-ready"
        or interaction.response_schema_ref != operation_public_schema_reference(response.identity)
    ):
        raise ValueError("ledger review belongs to another invocation or response contract")
    return project_captured_ledger_llm_review(operand)


def resolve_ledger_llm_review_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind ordinary operation actions; RESPOND's capability is supervisor-owned."""
    if request.definition_id not in LEDGER_LLM_REVIEW_DEFINITION_IDS or not isinstance(
        request.payload, LedgerLlmReviewRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.definition_id != ledger_llm_review_definition_id(request.payload):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    disclosures = resolved.policy.disclosures
    if context.action in {AccessAction.REVIEW, AccessAction.RESPOND}:
        schema = context.contract.review_projection_schema
        if schema is None or context.contract.interaction_response_schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=schema.schema_id,
                    category=DisclosureCategory.TAX_VALUES,
                ),
            )
        )
    policy = OperationAccessPolicy.model_validate(
        {
            **dict(resolved.policy),
            "actions": resolved.policy.actions | {AccessAction.COMMIT, AccessAction.REVIEW, AccessAction.RESPOND},
            "disclosures": disclosures,
            "transaction_authority_required": False,
        }
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def _result_projector(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    """Match the complete private invocation to its exact settled public receipt."""
    if not isinstance(result, LedgerLlmExecutionResult):
        raise ValueError("invalid ledger review terminal result")
    validated = LedgerLlmExecutionResult.model_validate(result.model_dump())
    projection = validated.result
    expected_effect = (
        OperationEffect.NONE
        if projection.outcome == "preview"
        or (projection.classification is not None and not projection.classification.bucket_event_ids)
        else OperationEffect.UPDATED
    )
    if (
        receipt.identity != validated.identity
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref != sha256_hex(serialize_operation_operand(validated))
        or receipt.effect is not expected_effect
    ):
        raise ValueError("ledger review result and terminal receipt disagree")
    return bound_ledger_llm_projection(projection)


def build_ledger_llm_review_definition(
    definition_id: str, factory: LedgerLlmOperationPortsFactory
) -> OperationDefinition:
    """Declare the existing suggestion/review/writer workflow with secure continuation."""
    if definition_id not in LEDGER_LLM_REVIEW_DEFINITION_IDS:
        raise ValueError("unknown ledger LLM review definition")
    return OperationDefinition(
        definition_id=definition_id,
        request_type=LedgerLlmReviewRequest,
        result_type=LedgerLlmExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerLlmReviewRequest,
            executor_type=LedgerLlmReviewExecutor,
            build=lambda: LedgerLlmReviewExecutor(factory),
        ),
        phase_codes=("ledger.llm.acquire", "ledger.llm.review", "ledger.llm.commit"),
        interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RESUMABLE,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.RESUMABLE,
            baseline=OperationBaselinePolicy.EXACT_APPROVAL,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def build_ledger_llm_review_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Register distinct private outcome and strict public projection models."""
    if (
        definition.definition_id not in LEDGER_LLM_REVIEW_DEFINITION_IDS
        or definition.request_type is not LedgerLlmReviewRequest
        or definition.result_type is not LedgerLlmExecutionResult
    ):
        raise ValueError("invalid ledger LLM review definition binding")
    review, response = ledger_llm_review_schemas(definition.definition_id)
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=LedgerLlmReviewRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=LedgerLlmOperationResult
        ),
        review_projection_schema=review,
        interaction_response_schema=response,
        reviewed_operand_type=LedgerLlmReviewedOperand,
        review_projector=_review_projector,
        result_projector=_result_projector,
        access_resolver=resolve_ledger_llm_review_access,
    )
