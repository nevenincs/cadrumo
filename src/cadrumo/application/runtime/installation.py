"""Durable local installation identity; metadata alone grants no profile access."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class RuntimeInstallation(BaseModel):
    """Bind automation enrollment to one native owner and physical storage root."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    version: Literal[1] = 1
    installation_id: UUID
    os_owner_id: Annotated[str, Field(min_length=1, max_length=256)]
    storage_identity: ContentDigest
