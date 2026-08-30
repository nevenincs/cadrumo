"""Durable idempotency binding for one exact operation request."""

from __future__ import annotations

from pydantic import BaseModel

from ....core.models import STRICT_FROZEN_CONFIG
from ....core.hashing import content_hash_hex
from ....core.identity import ContentDigest
from ..models import OperationDefinitionId, OperationId, OperationIdentity, OperationReference


class OperationIdempotencyClaim(BaseModel):
    """Durable binding from one caller key to one exact operation request."""

    model_config = STRICT_FROZEN_CONFIG

    definition_id: OperationDefinitionId
    subject_ref: OperationReference
    key_digest: ContentDigest
    operation_id: OperationId
    request_reference: ContentDigest

    @classmethod
    def bind(
        cls,
        *,
        identity: OperationIdentity,
        idempotency_key: str,
        request_reference: ContentDigest,
    ) -> OperationIdempotencyClaim:
        """Bind a caller key without retaining it in credential-free state."""
        return cls(
            definition_id=identity.definition_id,
            subject_ref=identity.subject_ref,
            key_digest=content_hash_hex(
                {
                    "schema_version": 1,
                    "definition_id": identity.definition_id,
                    "subject_ref": identity.subject_ref,
                    "idempotency_key": idempotency_key,
                }
            ),
            operation_id=identity.operation_id,
            request_reference=request_reference,
        )


__all__ = ["OperationIdempotencyClaim"]
