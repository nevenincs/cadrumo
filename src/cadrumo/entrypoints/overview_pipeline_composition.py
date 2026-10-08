"""Compose pipeline inspection without the filing mutation capability bundle."""

from __future__ import annotations

from uuid import UUID

from ..application.overview.pipeline_read_ports import PipelineReadPorts
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..application.user_profile.profile_record_repository import ProfileRecordRepository
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from .adapter_composition import build_calculation_action_ports
from .ledger_action_composition import compose_ledger_action_ports


def build_pipeline_read_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> PipelineReadPorts:
    """Use explicit secure storage and the same authority for nested decoding."""
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    profile_id = str(UUID(bucket_id))
    if require_active_bucket_id() != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    record = ProfileRecordRepository.for_current_session(
        profile_id, profile_decode_context=operation.profile_decode_context()
    ).load(profile_id)
    if str(record.profile_id) != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    objects = secure_object_repository_for_bucket(profile_id)
    calculation_binding = bind_calculation_revision_persistence_from_profile(
        bucket_id=profile_id,
        objects=objects,
        operation=operation,
        profile_record=record,
    )
    return PipelineReadPorts(
        bucket_id=profile_id,
        ledger=compose_ledger_action_ports(bucket_id=profile_id, operation=operation),
        calculation=build_calculation_action_ports(
            bucket_id=profile_id, operation=operation, profile_record=record, objects=objects
        ),
        verification=calculation_binding.verification_repository(),
    )
