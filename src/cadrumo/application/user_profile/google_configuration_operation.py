"""Register and resolve human Google configuration operations."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from pydantic import BaseModel

from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
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
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operations.secret_submission import OperationEphemeralSecretDeclaration
from .access_contracts import (
    AccessAction,
    AccessDenialCode,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
)
from .access_errors import ProfileAccessRefusedError
from .google_configuration_executor import GoogleConfigurationExecutor
from .google_configuration_operation_contracts import (
    GOOGLE_CONFIGURATION_CONTRACTS,
    GOOGLE_CONFIGURATION_REQUEST_TYPES,
    GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING,
    GOOGLE_CONSENT_REVIEW_SCHEMA_BINDING,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GOOGLE_REGISTER_INPUT_KIND,
    GOOGLE_REGISTER_OPERATION_DEFINITION_ID,
    GoogleConfigurationExecutionResult,
    GoogleConfigurationOutcome,
    GoogleConsentProposal,
)
from .google_configuration_operation_ports import GoogleConfigurationOperationPortsFactory
from .google_configuration_operation_refusal import GOOGLE_CONFIGURATION_REFUSAL_CODE
from .google_configuration_result_projection import (
    project_google_configuration_result,
    project_google_consent_review,
)


def resolve_google_configuration_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require human whole-profile authority and both current private disclosure classes."""
    pair = GOOGLE_CONFIGURATION_CONTRACTS.get(request.definition_id)
    if (
        pair is None
        or type(request.payload) is not pair[0]
        or not isinstance(request.payload, GOOGLE_CONFIGURATION_REQUEST_TYPES)
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
                "actions": resolved.policy.actions
                | {AccessAction.COMMIT}
                | (
                    {AccessAction.REVIEW, AccessAction.RESPOND}
                    if request.definition_id == GOOGLE_LOGIN_OPERATION_DEFINITION_ID
                    else set()
                ),
                "requires_human": True,
                "disclosures": disclosures,
            }
        ),
    )


def build_google_configuration_definitions(
    factory: GoogleConfigurationOperationPortsFactory,
) -> tuple[OperationDefinition, ...]:
    """Enroll exactly the nine existing human CLI configuration leaves."""
    definitions: list[OperationDefinition] = []
    for definition_id, (request_type, _projection_type) in GOOGLE_CONFIGURATION_CONTRACTS.items():
        consent = definition_id == GOOGLE_LOGIN_OPERATION_DEFINITION_ID
        definitions.append(
            OperationDefinition(
                definition_id=definition_id,
                request_type=request_type,
                result_type=GoogleConfigurationExecutionResult,
                executor_factory=OperationExecutorFactory(
                    request_type=request_type,
                    executor_type=GoogleConfigurationExecutor,
                    build=lambda: GoogleConfigurationExecutor(factory),
                ),
                phase_codes=(definition_id,),
                interaction_kinds=frozenset({OperationInteractionKind.REVIEW}) if consent else frozenset(),
                capabilities=OperationCapabilities(
                    durability=OperationDurability.RESUMABLE if consent else OperationDurability.RECORDED,
                    cancellation=OperationCancellation.UNSUPPORTED,
                    deadline=OperationDeadline.ABSENT,
                    replay=OperationReplayPolicy.RESUMABLE if consent else OperationReplayPolicy.IDEMPOTENT_SUBMIT,
                    baseline=OperationBaselinePolicy.EXACT_APPROVAL if consent else OperationBaselinePolicy.NONE,
                    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
                    sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
                    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
                    owned_resources=frozenset(),
                    permitted_effects=frozenset(OperationEffect),
                    close_policy=OperationClosePolicy.DETACH_ALLOWED,
                ),
                reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT
                if consent
                else OperationReconciliationPolicy.INTERRUPT,
                permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
                refusal_detail_codes=frozenset({GOOGLE_CONFIGURATION_REFUSAL_CODE}),
                ephemeral_secret=OperationEphemeralSecretDeclaration(
                    secret_kind=GOOGLE_REGISTER_INPUT_KIND, lifetime=timedelta(minutes=5)
                )
                if definition_id == GOOGLE_REGISTER_OPERATION_DEFINITION_ID
                else None,
            )
        )
    return tuple(definitions)


def build_google_configuration_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Compile closed request/result schemas and exact human consent projections."""
    request_type, _projection_type = GOOGLE_CONFIGURATION_CONTRACTS[definition.definition_id]
    consent = definition.definition_id == GOOGLE_LOGIN_OPERATION_DEFINITION_ID
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=request_type
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=GoogleConfigurationOutcome
        ),
        review_projection_schema=GOOGLE_CONSENT_REVIEW_SCHEMA_BINDING if consent else None,
        interaction_response_schema=GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING if consent else None,
        access_resolver=resolve_google_configuration_access,
        result_projector=project_google_configuration_result,
        review_projector=project_google_consent_review if consent else None,
        reviewed_operand_type=GoogleConsentProposal if consent else None,
    )


__all__ = [
    "GOOGLE_CONSENT_RESPONSE_SCHEMA_BINDING",
    "GOOGLE_CONSENT_REVIEW_SCHEMA_BINDING",
    "build_google_configuration_definitions",
    "build_google_configuration_registration",
    "resolve_google_configuration_access",
]
