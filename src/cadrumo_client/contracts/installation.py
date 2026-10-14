"""Durable local installation identity; metadata alone grants no profile access."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from cadrumo.core.exact_integer import EXACT_INTEGER
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class Installation(BaseModel):
    """Bind automation enrollment to one native owner and physical storage root."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    version: Annotated[Literal[1], EXACT_INTEGER] = 1
    installation_id: UUID
    os_owner_id: Annotated[str, Field(min_length=1, max_length=256)]
    storage_identity: ContentDigest
