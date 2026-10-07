"""Register human-only Google publication with exact disclosure and settlement."""

from __future__ import annotations

from dataclasses import replace

from pydantic import BaseModel

from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ..ledger.read_access import resolve_ledger_read_access
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
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .google_review_operation_contracts import (
    GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
    GOOGLE_REVIEW_RESPONSE_SCHEMA_BINDING,
    GOOGLE_REVIEW_REVIEW_SCHEMA_BINDING,
    GoogleReviewExecutionResult,
    GoogleReviewOperationPortsFactory,
    GoogleReviewProjection,
    GoogleReviewProposal,
    GoogleReviewRequest,
    GoogleReviewResult,
)
from .google_review_operation_executor import GoogleReviewExecutor


def resolve_google_review_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require a human, whole-profile authority and explicit financial disclosure."""
    if (
        request.definition_id != GOOGLE_REVIEW_OPERATION_DEFINITION_ID
        or type(request.payload) is not GoogleReviewRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    disclosures = resolved.policy.disclosures
    if context.action in {AccessAction.RESULT, AccessAction.REVIEW, AccessAction.RESPOND}:
        schema = (
            context.contract.result_schema
            if context.action is AccessAction.RESULT
            else context.contract.review_projection_schema
        )
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset(
            DisclosurePermission(
                destination_id=context.destination_id, projection_id=schema.schema_id, category=category
            )
            for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
        )
    return replace(
        resolved,
        policy=OperationAccessPolicy.model_validate(
            {
                **dict(resolved.policy),
                "actions": resolved.policy.actions | {AccessAction.COMMIT, AccessAction.REVIEW, AccessAction.RESPOND},
                "requires_human": True,
                "disclosures": disclosures,
            }
        ),
    )


def project_google_review(value: BaseModel, interaction: OperationInteractionRequest, /) -> BaseModel:
    """Release only the matching immutable disclosure proposal."""
    if type(value) is not GoogleReviewProposal:
        raise ValueError("invalid Google review proposal")
    proposal = GoogleReviewProposal.model_validate(value.model_dump(mode="python"), strict=True)
    if (
        proposal.identity != interaction.identity
        or proposal.revision != interaction.revision
        or proposal.digest != interaction.continuation_digest
    ):
        raise ValueError("Google review differs from its interaction")
    return GoogleReviewProjection(
        identity=proposal.identity,
        revision=proposal.revision,
        profile_id=proposal.request.profile_id,
        publication_id=proposal.request.publication_id,
        calculation_revision_id=proposal.request.calculation_revision_id,
        filing_record_id=proposal.request.filing_record_id,
        root_folder_id=proposal.publication.root.artifact_id,
        snapshot_digest=proposal.snapshot_digest,
        payload_categories=proposal.payload_categories,
        reviewed_proposal_digest=proposal.digest,
    )


def project_google_review_result(value: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release a verified link only under its exact successful terminal receipt."""
    if type(value) is not GoogleReviewExecutionResult:
        raise ValueError("invalid Google review result")
    private = GoogleReviewExecutionResult.model_validate(value.model_dump(mode="python"), strict=True)
    if (
        private.identity != receipt.identity
        or receipt.identity.definition_id != GOOGLE_REVIEW_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(private.result.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
        or receipt.effect.value != private.effect
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("Google review result differs from its terminal receipt")
    return private.result


def build_google_review_operation_definition(factory: GoogleReviewOperationPortsFactory) -> OperationDefinition:
    """Enroll one resumable human disclosure followed by guarded native publication."""
    return OperationDefinition(
        definition_id=GOOGLE_REVIEW_OPERATION_DEFINITION_ID,
        request_type=GoogleReviewRequest,
        result_type=GoogleReviewExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=GoogleReviewRequest,
            executor_type=GoogleReviewExecutor,
            build=lambda: GoogleReviewExecutor(factory),
        ),
        phase_codes=(
            GOOGLE_REVIEW_OPERATION_DEFINITION_ID + ".prepare",
            GOOGLE_REVIEW_OPERATION_DEFINITION_ID + ".publish",
        ),
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
            permitted_effects=frozenset(OperationEffect),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_google_review_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Compile the exact request, review, response and result contracts."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=GoogleReviewRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=GoogleReviewResult
        ),
        review_projection_schema=GOOGLE_REVIEW_REVIEW_SCHEMA_BINDING,
        interaction_response_schema=GOOGLE_REVIEW_RESPONSE_SCHEMA_BINDING,
        access_resolver=resolve_google_review_access,
        result_projector=project_google_review_result,
        review_projector=project_google_review,
        reviewed_operand_type=GoogleReviewProposal,
    )
