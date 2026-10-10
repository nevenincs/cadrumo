"""Canonical public registered operations for active user-profile maintenance."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from ...core.capabilities import ServiceCapability
from ...core.operations import profile_operation_subject as _profile_subject
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    COMMITTING_LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    OperationAccessProfile,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_period_independent_admission,
)
from ..operations.models import OperationRequest
from ..operations.registry import OperationFrontendProjection
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

_CAPABILITY_SECTIONS = frozenset(capability.schema_path.partition(".")[0] for capability in ServiceCapability)
"""The profile sections whose facts opt a service capability in or out."""


def _addresses_service_capability(path: str) -> bool:
    """Tell whether a fact path lies in a capability section, read as the fact writer reads it.

    The writer trims the path before it stores the fact, so the same trimmed
    text decides here. The whole section is matched, not the members known
    today, so a capability added later is covered without a second list.
    """
    return path.strip().partition(".")[0] in _CAPABILITY_SECTIONS


def _capability_question_ids(context: OperationAccessContext) -> frozenset[str]:
    """Name the wizard questions whose answer is stored in a capability section.

    The set is read from the setup catalogue under the host's pinned authority,
    so a capability question added later is covered without a list here.
    Without that authority the catalogue cannot be read, no answer can be shown
    to leave the capabilities alone, and the access is refused.
    """
    operation = context.authority_operation
    if operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    # Deferred because the wizard package imports this package.
    from ..wizard.catalogue import build_setup_flow

    return frozenset(
        question.id
        for section in build_setup_flow(operation).sections
        for question in section.questions
        if question.profile_key is not None and _addresses_service_capability(question.profile_key)
    )


def _changes_service_capability(payload: BaseModel, context: OperationAccessContext) -> bool:
    """Tell whether a profile change sets or clears a service capability.

    A field change names its path. A wizard patch names questions, and a blank
    answer clears the fact its question owns, so naming the question is enough.
    """
    if isinstance(payload, ProfileFieldMutationOperationRequest):
        return _addresses_service_capability(payload.path)
    if isinstance(payload, ProfilePatchOperationRequest) and payload.values:
        answered = {item.question_id for item in payload.values}
        return not answered.isdisjoint(_capability_question_ids(context))
    return False


def resolve_profile_mutation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Authorize profile facts as profile-wide work, without tax-period impersonation.

    Setting or clearing a service capability is the person's consent to a
    service, whichever operation writes it. A field change or a wizard patch
    that does so is refused to an MCP client; every other change stays open
    to it.
    """
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
    if context.frontend is OperationFrontendProjection.MCP and _changes_service_capability(payload, context):
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    return _bind_exact_profile_access(
        request,
        context,
        payload.profile_id,
        COMMITTING_LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    )


def resolve_profile_bundle_export_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require the exact active profile and explicit export-result disclosure."""
    payload = request.payload
    if not isinstance(payload, ProfileBundleExportOperationRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _bind_exact_profile_access(
        request,
        context,
        payload.profile_id,
        COMMITTING_LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    )


def resolve_profile_view_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact active profile and explicit result disclosure for a view page.

    A view page opens no irreversible section, so its policy grants no COMMIT
    door and a session without one can still read the profile.
    """
    payload = request.payload
    if not isinstance(payload, ProfileViewOperationRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _bind_exact_profile_access(
        request,
        context,
        payload.profile_id,
        LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    )


def _bind_exact_profile_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    profile_id: UUID,
    access_profile: OperationAccessProfile,
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
        access_profile,
        profile_id=profile_id,
        definition_id=request.definition_id,
        periods=frozenset(),
    )
