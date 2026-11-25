"""Exact-profile encrypted capabilities for the suffered-withholding certificate operations."""

from __future__ import annotations

from uuid import UUID

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ..adapters.persistence.profile.retencion_soportada_certificado import (
    RetencionSoportadaCertificadoRepositoryAdapter,
)
from ..adapters.persistence.profile.retencion_soportada_evidence_custody import (
    RetencionSoportadaEvidenceCustodyAdapter,
)
from ..adapters.persistence.storage.attachment import AttachmentStore
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.aggregation.retencion_soportada_repository import PinnedRetencionSoportadaWriteAuthority
from ..application.retencion_soportada_certificado.ports import RetencionSoportadaCertificadoPorts
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..application.user_profile.profile_record_repository import ProfileRecordRepository
from ..application.user_profile.projections import record_to_path_values
from ..application.workbench_generation_calendar import declared_tax_id
from ..core.bucket_pointer import require_active_bucket_id
from ..core.identity.bucket import canonical_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def _profile_tax_id(profile_id: UUID, operation: PinnedAuthorityOperation) -> str | None:
    record = ProfileRecordRepository.for_current_session(
        profile_id, profile_decode_context=operation.profile_decode_context()
    ).load(profile_id)
    return declared_tax_id(record_to_path_values(record))


def build_retencion_soportada_certificado_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> RetencionSoportadaCertificadoPorts:
    """Compose the capabilities only inside the admitted profile worker."""
    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    objects = secure_object_repository_for_bucket(str(profile_id))
    return RetencionSoportadaCertificadoPorts(
        repository=RetencionSoportadaCertificadoRepositoryAdapter(objects=objects),
        authority=PinnedRetencionSoportadaWriteAuthority(operation),
        custody=RetencionSoportadaEvidenceCustodyAdapter(
            store=AttachmentStore(bucket_id=canonical_bucket_id(str(profile_id)), objects=objects),
            bucket_id=str(profile_id),
        ),
        taxpayer_tax_id=lambda: _profile_tax_id(profile_id, operation),
    )
