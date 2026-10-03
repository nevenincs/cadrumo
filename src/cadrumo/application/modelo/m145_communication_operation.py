"""Exact-profile registered operations for the local Modelo 145 workflow.

The canonical record service remains the sole owner of validation, rendering,
state transitions, and history payloads. This module adds encrypted request and
result custody, exact-profile admission, and a gate at the service's actual
repository mutation calls. Exported bytes stay in the encrypted operation
result until the local CLI reads them; only their receipt is written to bucket
history.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    OBSERVATION_DISCLOSING_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access,
    operation_disclosures,
    require_period_independent_admission,
)
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
from ..operations.profile_guard import require_access_request_profile_payload
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, Availability, DisclosureCategory
from ._ports import FicheroBoeRecordRenderer
from .m145_communication_contracts import (
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_OPERATION_IDS,
    M145_COMMUNICATION_REFUSAL_CODES_BY_OPERATION,
    M145_COMMUNICATION_REQUEST_TYPES,
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID,
    M145CommunicationExecutionResult,
    M145CommunicationOperationId,
    M145CommunicationOperationResult,
    M145CommunicationRequest,
)
from .m145_communication_execution import (
    M145CommunicationExecutor,
)
from .m145_communication_projection import (
    project_m145_communication_result,
)
from .m145_communication_records_ports import M145CommunicationRecordsPortsFactory


def _resolve_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    operation_id: M145CommunicationOperationId,
    request_type: type[M145CommunicationRequest],
    permission: AccessAction,
) -> ResolvedOperationAccess:
    require_access_request_profile_payload(
        request, definition_id=operation_id, payload_type=request_type, access_profile_id=context.profile_id
    )
    admitted = context.admitted_request
    if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
        require_period_independent_admission(admitted, profile_id=context.profile_id, definition_id=operation_id)
    disclosures = operation_disclosures(
        context,
        observed_by=OBSERVATION_DISCLOSING_ACTIONS,
        result_categories=frozenset({DisclosureCategory.TAX_VALUES}),
        result_schema_id=None,
    )
    return bind_operation_access(
        context,
        profile_id=context.profile_id,
        definition_id=operation_id,
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
                permission,
            }
        ),
        disclosures=disclosures,
        periods=frozenset(),
        period_independent=True,
        requires_all_periods=True,
        requires_human=False,
        provider=Availability.NOT_REQUIRED,
    )


def _build_definition(
    *,
    operation_id: M145CommunicationOperationId,
    request_type: type[M145CommunicationRequest],
    records_ports_factory: M145CommunicationRecordsPortsFactory,
    renderer_factory: Callable[[], FicheroBoeRecordRenderer],
) -> OperationDefinition:
    mutating = operation_id != M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID
    return OperationDefinition(
        definition_id=operation_id,
        request_type=request_type,
        result_type=M145CommunicationExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=M145CommunicationExecutor,
            build=lambda: M145CommunicationExecutor(
                records_ports_factory=records_ports_factory,
                renderer_factory=renderer_factory,
            ),
        ),
        phase_codes=(operation_id,),
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset(
                {OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED}
                if mutating
                else {OperationEffect.NONE, OperationEffect.UNKNOWN}
            ),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=M145_COMMUNICATION_REFUSAL_CODES_BY_OPERATION[operation_id],
    )


def build_m145_communication_operation_definitions(
    *,
    records_ports_factory: M145CommunicationRecordsPortsFactory,
    renderer_factory: Callable[[], FicheroBoeRecordRenderer],
) -> tuple[OperationDefinition, ...]:
    """Build all five existing CLI identities over the canonical record service."""
    return tuple(
        sorted(
            (
                _build_definition(
                    operation_id=operation_id,
                    request_type=request_type,
                    records_ports_factory=records_ports_factory,
                    renderer_factory=renderer_factory,
                )
                for operation_id, request_type in M145_COMMUNICATION_REQUEST_TYPES.items()
            ),
            key=lambda definition: definition.definition_id,
        ),
    )


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[M145CommunicationRequest],
    permission: AccessAction,
) -> OperationPublicDefinitionRegistrationV1:
    operation_id = definition.definition_id
    if operation_id not in M145_COMMUNICATION_OPERATION_IDS:
        raise ValueError("M145 registration received an unknown operation definition")

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        return _resolve_access(
            request,
            context,
            operation_id=operation_id,
            request_type=request_type,
            permission=permission,
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=operation_id + ".request",
            schema_version=1,
            model_type=request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=operation_id + ".result",
            schema_version=1,
            model_type=M145CommunicationOperationResult,
        ),
        result_projector=project_m145_communication_result,
        access_resolver=resolve,
    )


def build_m145_communication_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Register strict schemas and exact-profile all-period access for each command."""
    permissions: dict[M145CommunicationOperationId, AccessAction] = {
        M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: AccessAction.COMMIT,
        M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID: AccessAction.SUBMIT,
        M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID: AccessAction.COMMIT,
        M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: AccessAction.COMMIT,
        M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: AccessAction.COMMIT,
    }
    registrations: list[OperationPublicDefinitionRegistrationV1] = []
    for definition in definitions:
        operation_id = definition.definition_id
        if operation_id not in M145_COMMUNICATION_REQUEST_TYPES:
            raise ValueError("M145 registration population contains an unknown operation")
        typed_id = operation_id  # narrowed by membership above
        registrations.append(
            _registration(
                definition,
                request_type=M145_COMMUNICATION_REQUEST_TYPES[typed_id],
                permission=permissions[typed_id],
            ),
        )
    return tuple(sorted(registrations, key=lambda registration: registration.contract.definition_id))


__all__ = [
    "build_m145_communication_operation_definitions",
    "build_m145_communication_operation_registrations",
]
