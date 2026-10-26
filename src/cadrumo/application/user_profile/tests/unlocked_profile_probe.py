"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from uuid import UUID

from ..aggregate import CommittedProfileView, UnlockedProfileFactSummary
from ..profile_repository import CommittedProfileRepository


def load_unlocked(self: CommittedProfileRepository, profile_id: str | UUID) -> CommittedProfileView:
    """Project fact state and provenance only through the current authenticated session."""
    aggregate = self.load(profile_id)
    from ....domain.calculations.registry.authority import bundled_indexed_authority
    from ..profile_record_repository import ProfileRecordRepository

    with bundled_indexed_authority().operation() as operation:
        record = ProfileRecordRepository.for_current_session(
            aggregate.profile_id, root=self._root, profile_decode_context=operation.profile_decode_context()
        ).load(aggregate.profile_id)
    return aggregate.model_copy(
        update={
            "fact_summary": UnlockedProfileFactSummary(
                setup_state=record.setup_state,
                fact_count=len(record.facts),
                record_revision=record.record_revision,
                content_digest=record.content_digest,
            )
        }
    )
