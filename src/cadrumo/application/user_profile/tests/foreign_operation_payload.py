"""A profile-bearing payload outside every supported operation schema."""

from uuid import UUID

from pydantic import BaseModel

from ....core.models import STRICT_FROZEN_CONFIG


class ForeignProfilePayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
