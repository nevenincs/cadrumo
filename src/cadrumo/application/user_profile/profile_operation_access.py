"""Canonical public registered operations for active user-profile maintenance."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from ...core.operations import profile_operation_subject as _profile_subject
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    COMMITTING_LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_period_independent_admission,
)
from ..operations.models import OperationRequest
from .access_contracts import AccessDenialCode
from .access_errors import ProfileAccessRefusedError
from .profile_operation_contracts import (
    ProfileBundleExportOperationRequest,
    ProfileCompleteSetupOperationRequest,
    ProfileDescendantsOperationRequest,
    ProfileFieldMutationOperationRequest,
    ProfilePatchOperationRequest,
    ProfilePlantillaMediaOperationRequest,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowRemoveOperationRequest,
    ProfileRepeatableRowUpdateOperationRequest,
)
from .view_operation import (
    ProfileViewOperationRequest,
)


def resolve_profile_mutation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Authorize profile facts as profile-wide work, without tax-period impersonation."""
    payload = request.payload
    if not isinstance(
        payload,
        ProfileFieldMutationOperationRequest
        | ProfilePatchOperationRequest
        | ProfilePlantillaMediaOperationRequest
        | ProfileDescendantsOperationRequest
        | ProfileRepeatableRowMutationOperationRequest
        | ProfileRepeatableRowUpdateOperationRequest
        | ProfileRepeatableRowRemoveOperationRequest
        | ProfileCompleteSetupOperationRequest,
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _bind_exact_profile_access(request, context, payload.profile_id)


def resolve_profile_bundle_export_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require the exact active profile and explicit export-result disclosure."""
    payload = request.payload
    if not isinstance(payload, ProfileBundleExportOperationRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _bind_exact_profile_access(request, context, payload.profile_id)


def resolve_profile_view_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact active profile and explicit result disclosure for a view page."""
    payload = request.payload
    if not isinstance(payload, ProfileViewOperationRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _bind_exact_profile_access(request, context, payload.profile_id)


def _bind_exact_profile_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, profile_id: UUID
) -> ResolvedOperationAccess:
    """Bind the active profile's own period-independent maintenance, refusing any other subject.

    A replay must replay this profile's period-independent submission of the
    same operation. It need not come from the submitting destination or
    frontend: observing and reading an admitted operation are caller-independent,
    and the runtime still checks the current destination's own disclosure scope.
    """
    if profile_id != context.profile_id or request.subject_ref != _profile_subject(str(profile_id)):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    admitted = context.admitted_request
    if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
        require_period_independent_admission(admitted, profile_id=profile_id, definition_id=request.definition_id)
    return bind_operation_access_profile(
        context,
        COMMITTING_LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
        profile_id=profile_id,
        definition_id=request.definition_id,
        periods=frozenset(),
    )
