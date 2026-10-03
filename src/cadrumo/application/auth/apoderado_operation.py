"""Exact-profile apoderado operation definitions and access policy."""

from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel

from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ..operations.access_resolution import (
    OperationAccessContext,
    ResolvedOperationAccess,
    require_declared_frontend_and_action,
    require_period_independent_replay_or_authority,
)
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
)
from ..operations.secret_submission import OperationEphemeralSecretDeclaration
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .apoderado_contracts import (
    APODERADO_CHECK_OPERATION_DEFINITION_ID,
    APODERADO_CLEAR_OPERATION_DEFINITION_ID,
    APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
    APODERADO_REPRESENTED_NIF_SECRET_KIND,
    APODERADO_STATUS_OPERATION_DEFINITION_ID,
    ApoderadoCheckRequest,
    ApoderadoClearRequest,
    ApoderadoConfigureRequest,
    ApoderadoExecutionResult,
    ApoderadoOperationId,
    ApoderadoOperationProjection,
    ApoderadoOperationRequest,
    ApoderadoStatusRequest,
    project_apoderado_operation_result,
)
from .apoderado_execution import ApoderadoOperationExecutor, ApoderadoOperationPortsFactory

_IDS = (
    APODERADO_STATUS_OPERATION_DEFINITION_ID,
    APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
    APODERADO_CLEAR_OPERATION_DEFINITION_ID,
    APODERADO_CHECK_OPERATION_DEFINITION_ID,
)


_WRITE_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})


_READ_ACTIONS = frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT})


_WRITE_ACTIONS = _READ_ACTIONS | {AccessAction.COMMIT}


def _require_apoderado_access_request(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> tuple[ApoderadoOperationId, ApoderadoOperationRequest, bool]:
    payload = request.payload
    operation_id = request.definition_id
    if operation_id not in _IDS or not isinstance(
        payload, (ApoderadoStatusRequest, ApoderadoConfigureRequest, ApoderadoClearRequest, ApoderadoCheckRequest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    mutating = operation_id in {APODERADO_CONFIGURE_OPERATION_DEFINITION_ID, APODERADO_CLEAR_OPERATION_DEFINITION_ID}
    return operation_id, payload, mutating


def _apoderado_disclosures(
    operation_id: ApoderadoOperationId, context: OperationAccessContext
) -> frozenset[DisclosurePermission]:
    disclosures = frozenset[DisclosurePermission]()
    if context.action is AccessAction.OBSERVE:
        return frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
            )
        )
    if context.action is not AccessAction.RESULT:
        return disclosures
    schema = context.contract.result_schema
    if schema is None or schema.schema_id != operation_id + ".result":
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return frozenset(
        DisclosurePermission(destination_id=context.destination_id, projection_id=schema.schema_id, category=category)
        for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
    )


def _resolve_access(request: OperationRequest[BaseModel], context: OperationAccessContext) -> ResolvedOperationAccess:
    operation_id, payload, mutating = _require_apoderado_access_request(request, context)
    actions = _WRITE_ACTIONS if mutating else _READ_ACTIONS
    require_declared_frontend_and_action(
        context, frontends=_WRITE_FRONTENDS if mutating else ALL_OPERATION_FRONTENDS, actions=actions
    )
    require_period_independent_replay_or_authority(context, profile_id=payload.profile_id, definition_id=operation_id)
    disclosures = _apoderado_disclosures(operation_id, context)
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=payload.profile_id,
            definition_id=operation_id,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=operation_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=actions,
            disclosures=disclosures,
            periods=frozenset(),
            allow_period_independent=True,
            requires_all_periods=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=mutating,
        ),
    )


def build_apoderado_operation_definitions(factory: ApoderadoOperationPortsFactory) -> tuple[OperationDefinition, ...]:
    """Declare each existing verb with truthful read/write and secret custody."""
    request_types: dict[ApoderadoOperationId, type[BaseModel]] = {
        APODERADO_STATUS_OPERATION_DEFINITION_ID: ApoderadoStatusRequest,
        APODERADO_CONFIGURE_OPERATION_DEFINITION_ID: ApoderadoConfigureRequest,
        APODERADO_CLEAR_OPERATION_DEFINITION_ID: ApoderadoClearRequest,
        APODERADO_CHECK_OPERATION_DEFINITION_ID: ApoderadoCheckRequest,
    }
    definitions: list[OperationDefinition] = []
    for operation_id, request_type in request_types.items():
        mutating = operation_id in {
            APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
            APODERADO_CLEAR_OPERATION_DEFINITION_ID,
        }
        definitions.append(
            build_single_phase_definition(
                definition_id=operation_id,
                request_type=request_type,
                result_type=ApoderadoExecutionResult,
                executor_type=ApoderadoOperationExecutor,
                build=lambda: ApoderadoOperationExecutor(factory),
                capabilities=OperationCapabilities(
                    durability=OperationDurability.RECORDED,
                    cancellation=OperationCancellation.UNSUPPORTED,
                    deadline=OperationDeadline.ABSENT,
                    replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
                    baseline=OperationBaselinePolicy.NONE,
                    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
                    sensitive_input=OperationSensitiveInputPolicy.NONE,
                    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
                    owned_resources=frozenset(),
                    permitted_effects=frozenset(
                        {OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED}
                    )
                    if mutating
                    else frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
                    close_policy=OperationClosePolicy.DETACH_ALLOWED,
                ),
                permitted_frontends=_WRITE_FRONTENDS if mutating else ALL_OPERATION_FRONTENDS,
                ephemeral_secret=OperationEphemeralSecretDeclaration(
                    secret_kind=APODERADO_REPRESENTED_NIF_SECRET_KIND, lifetime=timedelta(minutes=5)
                )
                if operation_id == APODERADO_CONFIGURE_OPERATION_DEFINITION_ID
                else None,
                refusal_detail_codes=frozenset({"REFUSED_APODERADO_LIVE_CHECK_UNAVAILABLE"})
                if operation_id == APODERADO_CHECK_OPERATION_DEFINITION_ID
                else frozenset({"REFUSED_APODERADO_INVALID_REPRESENTED_NIF", "REFUSED_APODERADO_UNKNOWN_SCOPE"})
                if operation_id == APODERADO_CONFIGURE_OPERATION_DEFINITION_ID
                else frozenset(),
            )
        )
    return tuple(sorted(definitions, key=lambda definition: definition.definition_id))


def build_apoderado_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind the four closed schemas and exact-profile authorization resolvers."""
    registrations: list[OperationPublicDefinitionRegistrationV1] = []
    for definition in definitions:
        if definition.definition_id not in _IDS:
            raise ValueError("unknown apoderado operation definition")
        registrations.append(
            OperationPublicDefinitionRegistrationV1.compose_request_result(
                definition=definition,
                public_result_type=ApoderadoOperationProjection,
                result_projector=project_apoderado_operation_result,
                access_resolver=_resolve_access,
            )
        )
    return tuple(sorted(registrations, key=lambda registration: registration.contract.definition_id))
