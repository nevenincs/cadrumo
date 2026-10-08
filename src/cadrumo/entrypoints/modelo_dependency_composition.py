"""Bind dependency inspection to the active immutable worker profile."""

from __future__ import annotations

from uuid import UUID

from ..application.calculations.m111_no_retenciones import m111_no_retenciones_periods_from_profile_values
from ..application.modelo.dependency_read_ports import DependencyReadPorts, DependencyReadRepositories
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..application.user_profile.profile_record_repository import ProfileRecordRepository
from ..application.user_profile.projections import record_to_path_values
from ..application.wizard.status import taxpayer_profile_from_record
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def build_dependency_read_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> DependencyReadPorts:
    """Capture taxpayer facts and bind every repository to the admitted profile."""
    from ..adapters.persistence.profile.calculation_observations import CalculationObservationRepository
    from ..adapters.persistence.profile.justificante import JustificanteRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    profile_id = str(UUID(bucket_id))
    if require_active_bucket_id() != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    record = ProfileRecordRepository.for_current_session(
        profile_id,
        profile_decode_context=operation.profile_decode_context(),
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
    return DependencyReadPorts(
        bucket_id=profile_id,
        profile=taxpayer_profile_from_record(record, schema=operation.profile_schema()),
        m111_no_retenciones_periods=m111_no_retenciones_periods_from_profile_values(record_to_path_values(record)),
        repositories=DependencyReadRepositories(
            work_unit=WorkUnitCatalogueRepository(bucket_id=profile_id, objects=objects),
            calculation=calculation_binding.calculation_repository(),
            filing=ModeloRecordCatalogueRepository(bucket_id=profile_id, objects=objects),
            verification=calculation_binding.verification_repository(),
            observation=CalculationObservationRepository(objects=objects),
            justificante=JustificanteRepository(objects=objects),
        ),
    )
