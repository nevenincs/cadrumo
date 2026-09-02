"""Revision-bound interaction requests and exact apply/reject responses."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from ...core.hashing import content_hash_hex
from ...core.hex import Hex64Str
from ...core.identity import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import OperationInteractionKind
from ...core.time.utc import validate_utc_aware
from .events import OperationEventCode
from .models import OperationIdentity, OperationReference, OperationRevision

type OperationInteractionId = Hex64Str
type OperationResponseToken = Hex64Str
type OperationActorReference = Annotated[
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


OperationResponseIntentValue = Literal[
    OperationResponseIntent.APPLY,
    OperationResponseIntent.REJECT,
]
"""Both members of the operator decision, for a surface that admits either.

An operation model graph must not customise its Pydantic core schema and a bare enum
under strict validation refuses the plain token a serialised response carries, so the
contracts, the TUI and the censal review all take this literal. Rooted in the enum
above; the single-member narrowings on the concrete response models are rooted the same
way and stay narrow.
"""


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


type OperationInteractionResponse = Annotated[
    OperationApplyResponse | OperationRejectResponse,
    Field(discriminator="intent"),
]


class OperationPendingInteraction(BaseModel):
    """Credential-free durable checkpoint for one exact single-use response."""

    model_config = STRICT_FROZEN_CONFIG

    request: OperationInteractionRequest
    response_token_digest: ContentDigest
    reviewed_proposal_digest: ContentDigest
    baseline_digest: ContentDigest | None = None
    proposed_effect_digest: ContentDigest | None = None

    @property
    def consumed(self) -> bool:
        """Report that this checkpoint still awaits a response."""
        return False

    @property
    def response_action(self) -> None:
        """Expose no decision before the checkpoint is consumed."""
        return None

    @classmethod
    def bind(
        cls,
        *,
        request: OperationInteractionRequest,
        response_token: OperationResponseToken,
        reviewed_proposal_digest: ContentDigest,
        baseline_digest: ContentDigest | None = None,
        proposed_effect_digest: ContentDigest | None = None,
    ) -> OperationPendingInteraction:
        """Digest the secret bearer token before it reaches journal state."""
        return cls(
            request=request,
            response_token_digest=content_hash_hex(response_token),
            reviewed_proposal_digest=reviewed_proposal_digest,
            baseline_digest=baseline_digest,
            proposed_effect_digest=proposed_effect_digest,
        )

    def consume(self, response: OperationApplyResponse | OperationRejectResponse) -> OperationConsumedInteraction:
        """Refuse every response that does not match this exact checkpoint."""
        _validate_response_identity(self.request, response)
        _validate_response_content(self, response)
        _validate_response_expiry(self.request, response)
        _validate_apply_response(self, response)
        response_digest = content_hash_hex(response.model_dump(mode="json"))
        return OperationConsumedInteraction(
            interaction_id=self.request.interaction_id,
            intent=response.intent,
            response_digest=response_digest,
            consumed_at=response.responded_at,
            checkpoint=self,
            continuation_proof_digest=_continuation_proof_digest(
                interaction_id=self.request.interaction_id,
                intent=response.intent,
                response_digest=response_digest,
                consumed_at=response.responded_at,
                checkpoint=self,
            ),
        )


def _validate_response_identity(
    request: OperationInteractionRequest,
    response: OperationApplyResponse | OperationRejectResponse,
) -> None:
    if response.interaction_id != request.interaction_id:
        raise ValueError("interaction response does not match the pending interaction identity")
    if response.operation_id != request.identity.operation_id or response.revision != request.revision:
        raise ValueError("interaction response does not match the pending operation revision")
    if response.continuation_digest != request.continuation_digest:
        raise ValueError("interaction response does not match the pending continuation")


def _validate_response_content(
    pending: OperationPendingInteraction,
    response: OperationApplyResponse | OperationRejectResponse,
) -> None:
    if response.reviewed_proposal_digest != pending.reviewed_proposal_digest:
        raise ValueError("interaction response does not match the reviewed proposal")
    if content_hash_hex(response.response_token) != pending.response_token_digest:
        raise ValueError("interaction response token does not match the pending token digest")


def _validate_response_expiry(
    request: OperationInteractionRequest,
    response: OperationApplyResponse | OperationRejectResponse,
) -> None:
    if request.expires_at is not None and response.responded_at > request.expires_at:
        raise ValueError("interaction response is expired")


def _validate_apply_response(
    pending: OperationPendingInteraction,
    response: OperationApplyResponse | OperationRejectResponse,
) -> None:
    if not isinstance(response, OperationApplyResponse):
        return
    if response.baseline_digest != pending.baseline_digest:
        raise ValueError("apply response does not match the pending baseline")
    if response.proposed_effect_digest != pending.proposed_effect_digest:
        raise ValueError("apply response does not match the pending proposed effect")


class OperationConsumedInteraction(BaseModel):
    """Safe durable continuation intent bound to its exact consumed checkpoint."""

    model_config = STRICT_FROZEN_CONFIG

    interaction_id: OperationInteractionId
    intent: OperationResponseIntent
    response_digest: ContentDigest
    consumed_at: datetime
    checkpoint: OperationPendingInteraction
    continuation_proof_digest: ContentDigest

    @property
    def consumed(self) -> bool:
        """Report that this checkpoint carries a durable response."""
        return True

    @property
    def reviewed_proposal_digest(self) -> ContentDigest:
        """Expose only the digest required by the resumed executor."""
        return self.checkpoint.reviewed_proposal_digest

    @property
    def response_action(self) -> OperationResponseIntentValue:
        """Project the private intent enum as a safe closed action member."""
        return self.intent

    @model_validator(mode="after")
    def _validate_consumed_at(self) -> OperationConsumedInteraction:
        validate_utc_aware(self.consumed_at)
        if self.interaction_id != self.checkpoint.request.interaction_id:
            raise ValueError("consumed interaction does not match its checkpoint identity")
        expected_proof = _continuation_proof_digest(
            interaction_id=self.interaction_id,
            intent=self.intent,
            response_digest=self.response_digest,
            consumed_at=self.consumed_at,
            checkpoint=self.checkpoint,
        )
        if self.continuation_proof_digest != expected_proof:
            raise ValueError("consumed interaction continuation proof does not match its durable intent")
        return self


def _continuation_proof_digest(
    *,
    interaction_id: OperationInteractionId,
    intent: OperationResponseIntent,
    response_digest: ContentDigest,
    consumed_at: datetime,
    checkpoint: OperationPendingInteraction,
) -> ContentDigest:
    """Bind every dispatch-relevant continuation fact into one hydration proof."""
    return content_hash_hex(
        {
            "schema_version": 1,
            "interaction_id": interaction_id,
            "intent": intent,
            "response_digest": response_digest,
            "consumed_at": consumed_at.isoformat(),
            "checkpoint": checkpoint.model_dump(mode="json"),
        }
    )


__all__ = [
    "OperationActorReference",
    "OperationApplyResponse",
    "OperationConsumedInteraction",
    "OperationInteractionId",
    "OperationInteractionRequest",
    "OperationInteractionResponse",
    "OperationPendingInteraction",
    "OperationRejectResponse",
    "OperationResponseIntent",
    "OperationResponseToken",
]
