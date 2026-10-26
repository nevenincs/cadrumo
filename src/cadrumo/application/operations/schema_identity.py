"""Stable value identity shared by declared operation and in-memory model schemas."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from ...core.hashing import content_hash_hex
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from .registry_schema_validation import strict_model_json_schema

type OperationPublicSchemaId = Annotated[
    str,
    Field(min_length=3, max_length=160, pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$"),
]


class OperationSchemaIdentityV1(BaseModel):
    """Stable public identity of one exact strict Pydantic JSON schema."""

    model_config = STRICT_FROZEN_CONFIG

    schema_id: OperationPublicSchemaId
    schema_version: Annotated[int, Field(ge=1)]
    schema_fingerprint: ContentDigest

    @classmethod
    def from_model(
        cls,
        *,
        schema_id: OperationPublicSchemaId,
        schema_version: int,
        model_type: type[BaseModel],
    ) -> OperationSchemaIdentityV1:
        """Derive the identity from the canonical closed schema of ``model_type``."""
        schema = strict_model_json_schema(model_type)
        return cls(
            schema_id=schema_id,
            schema_version=schema_version,
            schema_fingerprint=content_hash_hex(schema),
        )
