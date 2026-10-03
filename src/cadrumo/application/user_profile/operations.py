"""Canonical public registered operations for active user-profile maintenance."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from pydantic import BaseModel

from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
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
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operations.secret_submission import OperationEphemeralSecretDeclaration
from .bundle_export_contracts import (
    ProfileBundleExportResult,
)
from .profile_operation_access import (
    resolve_profile_bundle_export_access,
    resolve_profile_mutation_access,
    resolve_profile_view_access,
)
from .profile_operation_contracts import (
    PROFILE_BUNDLE_EXPORT_INPUT_KIND,
    PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
    PROFILE_BUNDLE_EXPORT_PHASES,
    PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
    PROFILE_COMPLETE_SETUP_PHASES,
    PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
    PROFILE_DESCENDANTS_PHASES,
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    PROFILE_FIELD_MUTATION_PHASES,
    PROFILE_LOGOUT_OPERATION_DEFINITION_ID,
    PROFILE_LOGOUT_PHASES,
    PROFILE_PATCH_OPERATION_DEFINITION_ID,
    PROFILE_PATCH_PHASES,
    PROFILE_PLANTILLA_MEDIA_OPERATION_DEFINITION_ID,
    PROFILE_PLANTILLA_MEDIA_PHASES,
    PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_MUTATION_PHASES,
    PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_REMOVE_PHASES,
    PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_UPDATE_PHASES,
    ProfileBundleExportOperationProjection,
    ProfileBundleExportOperationRequest,
    ProfileCompleteSetupOperationProjection,
    ProfileCompleteSetupOperationRequest,
    ProfileCompleteSetupOperationResult,
    ProfileDescendantsOperationProjection,
    ProfileDescendantsOperationRequest,
    ProfileDescendantsOperationResult,
    ProfileFieldMutationOperationRequest,
    ProfileLogoutOperationRequest,
    ProfileLogoutOperationResult,
    ProfileMutationOperationProjection,
    ProfileMutationOperationResult,
    ProfilePatchOperationProjection,
    ProfilePatchOperationRequest,
    ProfilePatchOperationResult,
    ProfilePlantillaMediaOperationProjection,
    ProfilePlantillaMediaOperationRequest,
    ProfilePlantillaMediaOperationResult,
    ProfileRepeatableRowChangeOperationProjection,
    ProfileRepeatableRowChangeOperationResult,
    ProfileRepeatableRowMutationOperationProjection,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowMutationOperationResult,
    ProfileRepeatableRowRemoveOperationRequest,
    ProfileRepeatableRowUpdateOperationRequest,
    project_profile_bundle_export_result,
    project_profile_mutation_result,
)
from .profile_operation_execution import (
    ProfileBundleExportOperationExecutor,
    ProfileCompleteSetupOperationExecutor,
    ProfileDescendantsOperationExecutor,
    ProfileFieldMutationOperationExecutor,
    ProfileLogoutOperationExecutor,
    ProfilePatchOperationExecutor,
    ProfilePlantillaMediaOperationExecutor,
    ProfileRepeatableRowMutationOperationExecutor,
    ProfileRepeatableRowRemoveOperationExecutor,
    ProfileRepeatableRowUpdateOperationExecutor,
    ProfileViewOperationExecutor,
)
from .view_operation import (
    PROFILE_VIEW_OPERATION_DEFINITION_ID,
    PROFILE_VIEW_PHASES,
    ProfileViewOperationProjection,
    ProfileViewOperationRequest,
    ProfileViewOperationResult,
    project_profile_view_result,
)


def _definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[object],
    phase_codes: tuple[str, ...],
    ephemeral_secret: OperationEphemeralSecretDeclaration | None = None,
    permitted_effects: frozenset[OperationEffect] = EFFECTS_WITHOUT_PARTIAL_COMMIT,
) -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=executor_type,
        ),
        phase_codes=phase_codes,
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
            permitted_effects=permitted_effects,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
        ephemeral_secret=ephemeral_secret,
    )


USER_PROFILE_OPERATION_DEFINITIONS = (
    _definition(
        definition_id=PROFILE_VIEW_OPERATION_DEFINITION_ID,
        request_type=ProfileViewOperationRequest,
        result_type=ProfileViewOperationResult,
        executor_type=ProfileViewOperationExecutor,
        phase_codes=PROFILE_VIEW_PHASES,
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
    ),
    _definition(
        definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
        request_type=ProfileFieldMutationOperationRequest,
        result_type=ProfileMutationOperationResult,
        executor_type=ProfileFieldMutationOperationExecutor,
        phase_codes=PROFILE_FIELD_MUTATION_PHASES,
    ),
    _definition(
        definition_id=PROFILE_PATCH_OPERATION_DEFINITION_ID,
        request_type=ProfilePatchOperationRequest,
        result_type=ProfilePatchOperationResult,
        executor_type=ProfilePatchOperationExecutor,
        phase_codes=PROFILE_PATCH_PHASES,
    ),
    _definition(
        definition_id=PROFILE_PLANTILLA_MEDIA_OPERATION_DEFINITION_ID,
        request_type=ProfilePlantillaMediaOperationRequest,
        result_type=ProfilePlantillaMediaOperationResult,
        executor_type=ProfilePlantillaMediaOperationExecutor,
        phase_codes=PROFILE_PLANTILLA_MEDIA_PHASES,
    ),
    _definition(
        definition_id=PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
        request_type=ProfileDescendantsOperationRequest,
        result_type=ProfileDescendantsOperationResult,
        executor_type=ProfileDescendantsOperationExecutor,
        phase_codes=PROFILE_DESCENDANTS_PHASES,
    ),
    _definition(
        definition_id=PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
        request_type=ProfileRepeatableRowMutationOperationRequest,
        result_type=ProfileRepeatableRowMutationOperationResult,
        executor_type=ProfileRepeatableRowMutationOperationExecutor,
        phase_codes=PROFILE_REPEATABLE_ROW_MUTATION_PHASES,
    ),
    _definition(
        definition_id=PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID,
        request_type=ProfileRepeatableRowUpdateOperationRequest,
        result_type=ProfileRepeatableRowChangeOperationResult,
        executor_type=ProfileRepeatableRowUpdateOperationExecutor,
        phase_codes=PROFILE_REPEATABLE_ROW_UPDATE_PHASES,
    ),
    _definition(
        definition_id=PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID,
        request_type=ProfileRepeatableRowRemoveOperationRequest,
        result_type=ProfileRepeatableRowChangeOperationResult,
        executor_type=ProfileRepeatableRowRemoveOperationExecutor,
        phase_codes=PROFILE_REPEATABLE_ROW_REMOVE_PHASES,
    ),
    _definition(
        definition_id=PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
        request_type=ProfileCompleteSetupOperationRequest,
        result_type=ProfileCompleteSetupOperationResult,
        executor_type=ProfileCompleteSetupOperationExecutor,
        phase_codes=PROFILE_COMPLETE_SETUP_PHASES,
    ),
    _definition(
        definition_id=PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
        request_type=ProfileBundleExportOperationRequest,
        result_type=ProfileBundleExportResult,
        executor_type=ProfileBundleExportOperationExecutor,
        phase_codes=PROFILE_BUNDLE_EXPORT_PHASES,
        ephemeral_secret=OperationEphemeralSecretDeclaration(
            secret_kind=PROFILE_BUNDLE_EXPORT_INPUT_KIND,
            lifetime=timedelta(minutes=5),
        ),
    ),
    _definition(
        definition_id=PROFILE_LOGOUT_OPERATION_DEFINITION_ID,
        request_type=ProfileLogoutOperationRequest,
        result_type=ProfileLogoutOperationResult,
        executor_type=ProfileLogoutOperationExecutor,
        phase_codes=PROFILE_LOGOUT_PHASES,
    ),
)


def build_user_profile_operation_definitions() -> tuple[OperationDefinition, ...]:
    """Return the one canonical profile-maintenance operation population."""
    return USER_PROFILE_OPERATION_DEFINITIONS


_PROFILE_MUTATION_REGISTRATION_IDS = frozenset(
    {
        PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
        PROFILE_PATCH_OPERATION_DEFINITION_ID,
        PROFILE_PLANTILLA_MEDIA_OPERATION_DEFINITION_ID,
        PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
        PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
        PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID,
        PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID,
        PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID,
    }
)
_PROFILE_MUTATION_PROJECTION_TYPES: dict[str, type[BaseModel]] = {
    PROFILE_PATCH_OPERATION_DEFINITION_ID: ProfilePatchOperationProjection,
    PROFILE_PLANTILLA_MEDIA_OPERATION_DEFINITION_ID: ProfilePlantillaMediaOperationProjection,
    PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID: ProfileDescendantsOperationProjection,
    PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID: ProfileRepeatableRowMutationOperationProjection,
    PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID: ProfileRepeatableRowChangeOperationProjection,
    PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID: ProfileRepeatableRowChangeOperationProjection,
    PROFILE_COMPLETE_SETUP_OPERATION_DEFINITION_ID: ProfileCompleteSetupOperationProjection,
}


def _profile_schema_binding(
    definition: OperationDefinition,
    schema_kind: str,
    model_type: type[BaseModel],
) -> OperationSchemaBindingV1:
    return OperationSchemaBindingV1.bind(
        schema_id=f"{definition.definition_id}.{schema_kind}",
        schema_version=1,
        model_type=model_type,
    )


def _public_profile_registration(
    definition: OperationDefinition,
    *,
    result_type: type[BaseModel],
    result_projector: Callable[[BaseModel, OperationTerminalReceipt], BaseModel],
    access_resolver: Callable[[OperationRequest[BaseModel], OperationAccessContext], ResolvedOperationAccess],
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=_profile_schema_binding(definition, "request", definition.request_type),
        result_schema=_profile_schema_binding(definition, "result", result_type),
        result_projector=result_projector,
        access_resolver=access_resolver,
    )


def _profile_view_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    return _public_profile_registration(
        definition,
        result_type=ProfileViewOperationProjection,
        result_projector=project_profile_view_result,
        access_resolver=resolve_profile_view_access,
    )


def _profile_mutation_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    projection_type = _PROFILE_MUTATION_PROJECTION_TYPES.get(
        definition.definition_id, ProfileMutationOperationProjection
    )
    return _public_profile_registration(
        definition,
        result_type=projection_type,
        result_projector=project_profile_mutation_result,
        access_resolver=resolve_profile_mutation_access,
    )


def _profile_bundle_export_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    return _public_profile_registration(
        definition,
        result_type=ProfileBundleExportOperationProjection,
        result_projector=project_profile_bundle_export_result,
        access_resolver=resolve_profile_bundle_export_access,
    )


def _profile_operation_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    if definition.definition_id == PROFILE_VIEW_OPERATION_DEFINITION_ID:
        return _profile_view_registration(definition)
    if definition.definition_id in _PROFILE_MUTATION_REGISTRATION_IDS:
        return _profile_mutation_registration(definition)
    if definition.definition_id == PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID:
        return _profile_bundle_export_registration(definition)
    return OperationPublicDefinitionRegistrationV1.compose_request_only(
        definition=definition, request_schema_id=f"{definition.definition_id}.request"
    )


def build_user_profile_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind profile-maintenance definitions to their stable public schemas."""
    registrations = (_profile_operation_registration(definition) for definition in definitions)
    return tuple(sorted(registrations, key=lambda item: item.contract.definition_id))


__all__ = [
    "USER_PROFILE_OPERATION_DEFINITIONS",
    "build_user_profile_operation_definitions",
    "build_user_profile_operation_registrations",
]
