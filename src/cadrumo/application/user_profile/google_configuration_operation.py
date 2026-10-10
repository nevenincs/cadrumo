"""Register and resolve Google configuration operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

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
    RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
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
from ..operations.subject_reference import OperationSubjectReferenceV1
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
    GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GOOGLE_STATUS_OPERATION_DEFINITION_ID,
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

# The two leaves that only report what this profile stored: the folder record
# and the sign-in record. Neither contacts the provider, changes the stored
# session or returns credential material, so they are the person's own data
# and are served to an agent as well as to a person. They are declared and
# admitted as reads: a session that holds no commit authority can run them.
GOOGLE_STORED_RECORD_READ_DEFINITION_IDS = frozenset(
    {GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID, GOOGLE_STATUS_OPERATION_DEFINITION_ID}
)
_PERSON_COMMAND_FRONTENDS = frozenset({OperationFrontendProjection.CLI})
_STORED_RECORD_READ_FRONTENDS = _PERSON_COMMAND_FRONTENDS | {OperationFrontendProjection.MCP}


def resolve_google_configuration_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind whole-profile authority and both private disclosure classes.

    Every leaf that signs in or out, contacts the provider or changes the
    folder is reserved for a person and holds the commit door it can open.
    The two stored-record reads are neither reserved nor given that door.
    """
    pair = GOOGLE_CONFIGURATION_CONTRACTS.get(request.definition_id)
    if (
        pair is None
        or type(request.payload) is not pair[0]
        or not isinstance(request.payload, GOOGLE_CONFIGURATION_REQUEST_TYPES)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    stored_record_read = request.definition_id in GOOGLE_STORED_RECORD_READ_DEFINITION_IDS
    actions = resolved.policy.actions
    if not stored_record_read:
        actions |= {AccessAction.COMMIT}
    if request.definition_id == GOOGLE_LOGIN_OPERATION_DEFINITION_ID:
        actions |= {AccessAction.REVIEW, AccessAction.RESPOND}
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
                "actions": actions,
                "requires_human": not stored_record_read,
                "disclosures": disclosures,
            }
        ),
    )


def _leaf_capabilities(*, consent: bool, stored_record_read: bool) -> OperationCapabilities:
    """Declare a read's effects for a stored-record read and every effect for the other leaves."""
    if stored_record_read:
        return RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
    return OperationCapabilities(
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
    )


def _executor_builder(
    factory: GoogleConfigurationOperationPortsFactory, *, stored_record_read: bool
) -> Callable[[], GoogleConfigurationExecutor]:
    return lambda: GoogleConfigurationExecutor(factory, stored_record_read=stored_record_read)


def build_google_configuration_definitions(
    factory: GoogleConfigurationOperationPortsFactory,
) -> tuple[OperationDefinition, ...]:
    """Enroll every configuration leaf the contract map declares."""
    definitions: list[OperationDefinition] = []
    for definition_id, (request_type, _projection_type) in GOOGLE_CONFIGURATION_CONTRACTS.items():
        consent = definition_id == GOOGLE_LOGIN_OPERATION_DEFINITION_ID
        stored_record_read = definition_id in GOOGLE_STORED_RECORD_READ_DEFINITION_IDS
        definitions.append(
            OperationDefinition(
                definition_id=definition_id,
                request_type=request_type,
                subject_reference=OperationSubjectReferenceV1.profile(),
                result_type=GoogleConfigurationExecutionResult,
                executor_factory=OperationExecutorFactory(
                    request_type=request_type,
                    executor_type=GoogleConfigurationExecutor,
                    build=_executor_builder(factory, stored_record_read=stored_record_read),
                ),
                phase_codes=(definition_id,),
                interaction_kinds=frozenset({OperationInteractionKind.REVIEW}) if consent else frozenset(),
                capabilities=_leaf_capabilities(consent=consent, stored_record_read=stored_record_read),
                reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT
                if consent
                else OperationReconciliationPolicy.INTERRUPT,
                permitted_frontends=_STORED_RECORD_READ_FRONTENDS if stored_record_read else _PERSON_COMMAND_FRONTENDS,
                refusal_detail_codes=frozenset({GOOGLE_CONFIGURATION_REFUSAL_CODE}),
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
    "GOOGLE_STORED_RECORD_READ_DEFINITION_IDS",
    "build_google_configuration_definitions",
    "build_google_configuration_registration",
    "resolve_google_configuration_access",
]
