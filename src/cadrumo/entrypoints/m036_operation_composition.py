"""Bind Modelo 036 declaration recording to the admitted profile worker."""

from __future__ import annotations

from uuid import UUID

from ..adapters.persistence.profile.m036_lifecycle import build_m036_lifecycle_ports
from ..application.modelo.m036_operation_ports import M036OperationPorts
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def build_m036_operation_ports(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> M036OperationPorts:
    """Compose the canonical encrypted repositories only for the exact worker."""
    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return M036OperationPorts(
        profile_id=profile_id,
        operation=operation,
        lifecycle_ports=build_m036_lifecycle_ports(bucket_id=str(profile_id)),
    )
