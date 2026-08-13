"""Revision-bound interaction requests and exact apply/reject responses."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG, Hex64Str, OperationInteractionKind
from ...core.identity import ContentDigest
from ...core.time import validate_utc_aware
from ._events import OperationEventCode
from ._models import OperationIdentity, OperationReference, OperationRevision

OperationInteractionId = Hex64Str
OperationResponseToken = Hex64Str
OperationActorReference = Annotated[
    str,
    Field(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9]*:[a-z0-9][a-z0-9._-]+$"),
]


class OperationInteractionRequest(BaseModel):
    """Immutable request for one exact operator continuation."""

    model_config = STRICT_FROZEN_CONFIG

    interaction_id: OperationInteractionId
    identity: OperationIdentity
    revision: OperationRevision
    kind: OperationInteractionKind
    presentation_code: OperationEventCode
    response_schema_ref: OperationReference
    continuation_digest: ContentDigest
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_expiry(self) -> OperationInteractionRequest:
        if self.expires_at is not None:
            validate_utc_aware(self.expires_at)
        return self


class OperationResponseIntent(StrEnum):
    """Closed operator decision for a review continuation."""

    APPLY = "apply"
    REJECT = "reject"


class _OperationInteractionResponseBase(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    interaction_id: OperationInteractionId
    operation_id: Hex64Str
    revision: OperationRevision
    response_token: OperationResponseToken
    continuation_digest: ContentDigest
    reviewed_proposal_digest: ContentDigest
    actor_ref: OperationActorReference
    responded_at: datetime

    @model_validator(mode="after")
    def _validate_response_time(self) -> _OperationInteractionResponseBase:
        validate_utc_aware(self.responded_at)
        return self


class OperationApplyResponse(_OperationInteractionResponseBase):
    """Apply the exact reviewed proposal bound by both digests."""

    intent: Literal[OperationResponseIntent.APPLY] = OperationResponseIntent.APPLY
    baseline_digest: ContentDigest
    proposed_effect_digest: ContentDigest


class OperationRejectResponse(_OperationInteractionResponseBase):
    """Reject the exact reviewed proposal without a governed effect."""

    intent: Literal[OperationResponseIntent.REJECT] = OperationResponseIntent.REJECT
    reason_code: OperationEventCode | None = None


OperationInteractionResponse = Annotated[
    OperationApplyResponse | OperationRejectResponse,
    Field(discriminator="intent"),
]

__all__ = [
    "OperationActorReference",
    "OperationApplyResponse",
    "OperationInteractionId",
    "OperationInteractionRequest",
    "OperationInteractionResponse",
    "OperationRejectResponse",
    "OperationResponseIntent",
    "OperationResponseToken",
]
