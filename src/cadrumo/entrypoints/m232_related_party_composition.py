"""Exact-profile encrypted capabilities for the Modelo 232 related-party statements."""

from __future__ import annotations

from uuid import UUID

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ..adapters.persistence.profile.m232_related_party_records import Modelo232RelatedPartyStoreAdapter
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.aggregation.m232_related_party_repository import (
    Modelo232PinnedWriteAuthority,
    Modelo232RelatedPartyWritePorts,
)
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = ["build_m232_related_party_ports"]


def build_m232_related_party_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> Modelo232RelatedPartyWritePorts:
    """Compose the capabilities only inside the admitted profile worker."""
    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return Modelo232RelatedPartyWritePorts(
        store=Modelo232RelatedPartyStoreAdapter(objects=secure_object_repository_for_bucket(str(profile_id))),
        authority=Modelo232PinnedWriteAuthority(operation),
    )
