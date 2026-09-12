"""Application contract for a durable profile-login handover witness."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, model_validator

from ...core.bucket_pointer import BucketPointer
from ...core.hashing import bounded_canonical_json_bytes
from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.utc import validate_utc_aware

HANDOVER_JOURNAL_MAX_BYTES = 4 * 1024


class HandoverPhase(StrEnum):
    """Durable boundaries of one password-authenticated profile handover."""

    PREPARED = "prepared"
    POINTER_PUBLISHED = "pointer_published"
    B_BOUND = "b_bound"
    ACCELERATED = "accelerated"
    ACTIVATED = "activated"
    A_RETIRED = "a_retired"


_HANDOVER_PHASE_INDEX: dict[HandoverPhase, int] = {
    HandoverPhase.PREPARED: 0,
    HandoverPhase.POINTER_PUBLISHED: 1,
    HandoverPhase.B_BOUND: 2,
    HandoverPhase.ACCELERATED: 3,
    HandoverPhase.ACTIVATED: 4,
    HandoverPhase.A_RETIRED: 5,
}


class ProfileLoginHandoverJournal(BaseModel):
    """Non-secret recovery witness for the short A-to-B handover window."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[2] = 2
    phase: HandoverPhase
    profile_a: BucketId | None
    profile_b: BucketId
    pointer_before: BucketPointer
    pointer_after: BucketPointer
    activation_at: datetime

    @model_validator(mode="after")
    def _validate_journal(self) -> ProfileLoginHandoverJournal:
        validate_utc_aware(self.activation_at)
        if self.pointer_after.bucket_id != self.profile_b:
            raise ValueError("handover pointer-after selection must name profile B")
        if self.pointer_after != self.pointer_before and (
            self.pointer_after.transition_revision != self.pointer_before.transition_revision + 1
        ):
            raise ValueError("handover pointer transition revision must advance exactly once when selection changes")
        return self

    @classmethod
    def prepare(
        cls,
        *,
        profile_a: str | None,
        profile_b: str,
        pointer_before: BucketPointer,
        pointer_after: BucketPointer,
        activation_at: datetime,
    ) -> ProfileLoginHandoverJournal:
        """Capture the transition before pointer publication."""
        return cls(
            phase=HandoverPhase.PREPARED,
            profile_a=profile_a,
            profile_b=profile_b,
            pointer_before=pointer_before,
            pointer_after=pointer_after,
            activation_at=activation_at,
        )

    def at_phase(self, phase: HandoverPhase) -> ProfileLoginHandoverJournal:
        """Return this handover witnessed at its next durable phase."""
        return self.model_copy(update={"phase": phase})

    def at_least_phase(self, phase: HandoverPhase) -> ProfileLoginHandoverJournal:
        """Advance without regressing the durable phase."""
        if _HANDOVER_PHASE_INDEX[self.phase] >= _HANDOVER_PHASE_INDEX[phase]:
            return self
        return self.at_phase(phase)

    def canonical_json_bytes(self) -> bytes:
        """Return the journal's bounded, byte-exact persistence form."""
        return bounded_canonical_json_bytes(
            self.model_dump(mode="json"),
            maximum_bytes=HANDOVER_JOURNAL_MAX_BYTES,
            subject="profile login handover journal",
        )


__all__ = ["HANDOVER_JOURNAL_MAX_BYTES", "HandoverPhase", "ProfileLoginHandoverJournal"]
