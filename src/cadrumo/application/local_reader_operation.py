"""Access for the operations that read what the machine holds for local reading.

The local AI belongs to the machine, so the ``local-reader`` reads name no
profile and their subject is the fixed one each declares.
"""

from __future__ import annotations

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from .operations.access_resolution import (
    LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_replayed_period_independent_access,
)
from .operations.models import OperationRequest
from .operations.profile_guard import require_access_request_payload
from .user_profile.access_errors import ProfileAccessRefusedError

__all__ = ["bind_machine_reader_access"]


def bind_machine_reader_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    payload_type: type[BaseModel],
    subject_ref: str,
) -> ResolvedOperationAccess:
    """Bind period-independent access, without COMMIT, to a read of one thing the machine holds.

    What is read belongs to the machine, so the request names no profile and
    its subject is the fixed one the operation declares. A read changes
    nothing, so it carries no COMMIT and a session whose scope holds none may
    submit it.
    """
    require_access_request_payload(request, definition_id=definition_id, payload_type=payload_type)
    if context.contract.definition_id != definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.subject_ref != subject_ref:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return bind_replayed_period_independent_access(
        context,
        LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
        definition_id=definition_id,
    )
