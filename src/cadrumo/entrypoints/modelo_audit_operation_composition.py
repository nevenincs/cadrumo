"""Bind existing audit repositories to the immutable authenticated profile worker."""

from __future__ import annotations

from uuid import UUID

from ..adapters.persistence.profile.evidence_bundles import EvidenceBundleRepository, EvidenceBundleWorkUnitRepository
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.evidence.ports import EvidenceBundlePorts
from ..application.modelo.audit_operation_ports import ModeloAuditOperationPorts
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def build_modelo_audit_operation_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> ModeloAuditOperationPorts:
    """Use canonical encrypted repositories without a second authority or provider."""
    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    objects = secure_object_repository_for_bucket(str(profile_id))
    return ModeloAuditOperationPorts(
        profile_id=profile_id,
        operation=operation,
        evidence=EvidenceBundlePorts(
            repository=EvidenceBundleRepository(objects=objects),
            work_units=EvidenceBundleWorkUnitRepository(bucket_id=str(profile_id), objects=objects),
        ),
    )
