"""Exact-profile encrypted capabilities for the suffered-withholding absence attestations."""

from __future__ import annotations

from uuid import UUID

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ..adapters.persistence.profile.retencion_soportada_records import (
    RetencionSoportadaAbsenceRepositoryAdapter,
    RetencionSoportadaRecordRepositoryAdapter,
)
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.aggregation.retencion_soportada_absence_repository import RetencionSoportadaAbsenceWritePorts
from ..application.aggregation.retencion_soportada_repository import PinnedRetencionSoportadaWriteAuthority
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = ["build_retencion_soportada_absence_ports"]


def build_retencion_soportada_absence_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> RetencionSoportadaAbsenceWritePorts:
    """Compose the capabilities only inside the admitted profile worker."""
    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    objects = secure_object_repository_for_bucket(str(profile_id))
    return RetencionSoportadaAbsenceWritePorts(
        attestations=RetencionSoportadaAbsenceRepositoryAdapter(objects=objects),
        records=RetencionSoportadaRecordRepositoryAdapter(objects=objects),
        authority=PinnedRetencionSoportadaWriteAuthority(operation),
    )
