"""Single-holder review custody and compatibility of durable continuation proofs."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ....core.hashing import canonical_json_bytes, content_hash_hex
from ....core.operations import OperationInteractionKind
from ..frontend_requests import OperationResponseControlRequestV1
from ..interactions import (
    OperationConsumedInteraction,
    OperationInteractionRequest,
    OperationPendingInteraction,
    OperationRejectResponse,
    OperationReviewClaimAttribution,
)
from ..models import OperationIdentity
from ..projection_services import OperationResponseAuthorityBroker

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)


def _pending() -> OperationPendingInteraction:
    return OperationPendingInteraction.bind(
        request=OperationInteractionRequest(
            interaction_id="b" * 64,
            identity=OperationIdentity(
                operation_id="a" * 64, definition_id="config.provision.setup", subject_ref="config:provision"
            ),
            revision=4,
            kind=OperationInteractionKind.REVIEW,
            presentation_code="config.provision.review",
            response_schema_ref="schema:config.provision.review",
            continuation_digest="c" * 64,
        ),
        response_token="d" * 64,
        reviewed_proposal_digest="e" * 64,
    )


def _claim(pending: OperationPendingInteraction) -> OperationPendingInteraction:
    session = uuid4()
    claim = OperationReviewClaimAttribution(
        actor_ref=f"session:{session}",
        connection_id=uuid4(),
        session_id=session,
        profile_id=uuid4(),
        runtime_boot_id=uuid4(),
        authority_generation="f" * 64,
        frontend="cli",
        source_ref="synthetic-login",
        claimed_at=_NOW,
        displayed_revision=pending.request.revision,
        reviewed_document_digest="1" * 64,
    )
    return pending.model_copy(
        update={
            "request": pending.request.model_copy(update={"revision": pending.request.revision + 1}),
            "review_claim": claim,
        }
    )


def _response(pending: OperationPendingInteraction, actor: str) -> OperationRejectResponse:
    return OperationRejectResponse(
        interaction_id=pending.request.interaction_id,
        operation_id=pending.request.identity.operation_id,
        revision=pending.request.revision,
        response_token="d" * 64,
        continuation_digest=pending.request.continuation_digest,
        reviewed_proposal_digest=pending.reviewed_proposal_digest,
        actor_ref=actor,
        responded_at=_NOW,
    )


def test_broker_rotates_only_the_retained_exact_checkpoint_and_invalidates_old_actor() -> None:
    pending, broker = _pending(), OperationResponseAuthorityBroker()
    old = broker.reserve(pending.request.identity.operation_id, "operator:original")
    broker.issue(pending, "d" * 64)
    successor = _claim(pending)
    assert successor.review_claim is not None
    holder = broker.assign_actor(pending, successor, clock=lambda: _NOW)
    request = OperationResponseControlRequestV1(
        operation_id=pending.request.identity.operation_id,
        interaction_id=pending.request.interaction_id,
        revision=successor.request.revision,
        actor_ref=successor.review_claim.actor_ref,
    )
    try:
        assert broker.inspect(request, successor, holder, clock=lambda: _NOW)
        with pytest.raises(ValueError, match="unavailable"):
            broker.inspect(request, successor, old, clock=lambda: _NOW)
        with pytest.raises(ValueError, match="successor"):
            broker.assign_actor(successor, _claim(successor), clock=lambda: _NOW)
        broker.bind(request, successor, holder, clock=lambda: _NOW).close()
        with pytest.raises(ValueError, match="unavailable"):
            broker.require_claimable(successor, clock=lambda: _NOW)
    finally:
        old.close()
        holder.close()
        broker.close()


def test_an_observed_checkpoint_cannot_reconstruct_a_broker_bearer() -> None:
    broker = OperationResponseAuthorityBroker()
    with pytest.raises(ValueError, match="unavailable"):
        broker.assign_actor(_pending(), _claim(_pending()), clock=lambda: _NOW)


def test_claim_attribution_rejects_foreign_actor_and_survives_consumption() -> None:
    claimed = _claim(_pending())
    assert claimed.review_claim is not None
    with pytest.raises(ValueError, match="claimant"):
        claimed.consume(_response(claimed, "operator:foreign"))
    consumed = claimed.consume(_response(claimed, claimed.review_claim.actor_ref))
    assert OperationConsumedInteraction.model_validate_json(consumed.model_dump_json()) == consumed
    assert consumed.checkpoint.review_claim == claimed.review_claim


def test_legacy_consumed_checkpoint_retains_its_original_proof_without_claim_field() -> None:
    pending = _pending()
    consumed = pending.consume(_response(pending, "operator:original"))
    old_checkpoint = pending.model_dump(mode="json", exclude={"review_claim"})
    proof = content_hash_hex(
        {
            "schema_version": 1,
            "interaction_id": consumed.interaction_id,
            "intent": consumed.intent,
            "response_digest": consumed.response_digest,
            "consumed_at": consumed.consumed_at.isoformat(),
            "checkpoint": old_checkpoint,
        }
    )
    assert consumed.continuation_proof_digest == proof
    stored = consumed.model_dump(mode="json")
    stored["checkpoint"] = old_checkpoint
    assert (
        OperationConsumedInteraction.model_validate_json(canonical_json_bytes(stored)).continuation_proof_digest
        == proof
    )
