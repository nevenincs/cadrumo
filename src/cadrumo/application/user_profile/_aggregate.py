"""Non-authoritative projection of one committed profile capsule.

Custody material is deliberately absent.  A profile view is visible only after
the storage owner has validated its immutable commit marker; the label is the
repository's presentation mapping, never a manifest or a key-selection hint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.identity import ProfileId, ProfileLabel
from ...core.time import validate_utc_aware


class CommittedProfileView(BaseModel):
    """A safe read model, assembled from a committed capsule and label owner."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", hide_input_in_errors=True)

    profile_id: ProfileId
    label: ProfileLabel
    committed_at: datetime
    publication_kind: Literal["enroll", "restore"]
    password_generation: int = Field(ge=1)
    custody_present: Literal[True] = True

    @field_validator("committed_at")
    @classmethod
    def _validate_committed_at(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)


__all__ = ["CommittedProfileView"]
