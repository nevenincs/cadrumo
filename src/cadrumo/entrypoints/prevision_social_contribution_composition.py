"""Exact-profile encrypted capabilities for the pension contribution certificate operations."""

from __future__ import annotations

from uuid import UUID

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ..adapters.persistence.profile.prevision_social_contribution_evidence_custody import (
    PrevisionSocialContributionEvidenceCustodyAdapter,
)
from ..adapters.persistence.profile.prevision_social_contribution_records import (
    PrevisionSocialContributionRecordRepositoryAdapter,
)
from ..adapters.persistence.storage.attachment import AttachmentStore
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.aggregation.prevision_social_contribution_repository import (
    PinnedPrevisionSocialContributionWriteAuthority,
)
from ..application.prevision_social_contribution.ports import PrevisionSocialPorts
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..core.identity.bucket import canonical_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def build_prevision_social_contribution_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> PrevisionSocialPorts:
    """Compose the capabilities only inside the admitted profile worker."""
    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    objects = secure_object_repository_for_bucket(str(profile_id))
    return PrevisionSocialPorts(
        repository=PrevisionSocialContributionRecordRepositoryAdapter(objects=objects),
        authority=PinnedPrevisionSocialContributionWriteAuthority(operation),
        custody=PrevisionSocialContributionEvidenceCustodyAdapter(
            store=AttachmentStore(bucket_id=canonical_bucket_id(str(profile_id)), objects=objects),
            bucket_id=str(profile_id),
        ),
    )
