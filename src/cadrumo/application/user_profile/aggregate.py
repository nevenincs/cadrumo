"""Non-authoritative projection of one committed profile capsule.

Custody material is deliberately absent.  A profile view is visible only after
the storage owner has validated its immutable commit marker; the label is the
repository's presentation mapping, never a manifest or a key-selection hint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.identity import ContentDigest, PrefixedContentDigest, ProfileId, ProfileLabel
from ...core.time import validate_utc_aware
from ...domain.user_profile.values import ProfileSetupState


class LockedProfileFactSummary(BaseModel):
    """The only fact/status projection available without an unlocked session."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)

    availability: Literal["UNAVAILABLE_LOCKED"] = "UNAVAILABLE_LOCKED"
    setup_state: Literal["UNAVAILABLE_LOCKED"] = "UNAVAILABLE_LOCKED"
    fact_count: Literal[0] = 0


class UnlockedProfileFactSummary(BaseModel):
    """Session-authenticated current-record summary and provenance."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)

    availability: Literal["AVAILABLE_UNLOCKED"] = "AVAILABLE_UNLOCKED"
    setup_state: ProfileSetupState
    fact_count: int = Field(ge=0)
    record_revision: int = Field(ge=1)
    content_digest: ContentDigest


type ProfileFactSummary = Annotated[
    LockedProfileFactSummary | UnlockedProfileFactSummary,
    Field(discriminator="availability"),
]


type ProfileRestoreAuthority = Literal["password", "recovery_artifact"]
"""Which door proved the key a restore republishes a capsule under.

Declared beside ``publication_kind`` because it is the same class of axis and
answers the question that one leaves open: a view already says a capsule was
published by a restore, but not what authorised it. The two members are not
interchangeable. ``password`` means the profile's own credential unwrapped its
own envelope; ``recovery_artifact`` means a portable artifact was proved with
its recovery secret, which recovers the DATA path and deliberately does not
hand back password access -- a recovery-proved restore republishes the same
password envelope, and credential rotation remains a separate, unbuilt
capability.
"""


class CommittedProfileView(BaseModel):
    """A safe read model, assembled from a committed capsule and label owner."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)

    profile_id: ProfileId
    label: ProfileLabel
    committed_at: datetime
    publication_kind: Literal["enroll", "restore"]
    password_generation: int = Field(ge=1)
    custody_present: Literal[True] = True
    label_revision: int = Field(ge=1)
    label_content_digest: PrefixedContentDigest
    label_self_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    label_source_witness: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    fact_summary: ProfileFactSummary = Field(default_factory=LockedProfileFactSummary)

    @field_validator("committed_at")
    @classmethod
    def _validate_committed_at(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)


__all__ = [
    "CommittedProfileView",
    "LockedProfileFactSummary",
    "ProfileFactSummary",
    "ProfileRestoreAuthority",
    "UnlockedProfileFactSummary",
]
