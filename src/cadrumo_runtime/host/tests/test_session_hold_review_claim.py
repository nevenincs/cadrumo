"""The canonical person holder relays an explicit exact-document claim."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import JsonValue

from cadrumo.application.operations.frontend_projection import (
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
)
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.core.hashing import content_hash_hex
from cadrumo_client.contracts.operation_access import (
    OperationClaimableReviews,
    OperationClaimableReviewsListed,
    OperationReply,
    OperationRequest,
    OperationReviewClaim,
    OperationReviewClaimed,
)
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_runtime.host.session_hold_operations import OperationRelay, RelayRefusedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _pending(revision: int) -> OperationReviewAvailableInteractionV1:
    schema = OperationSchemaIdentityV1(
        schema_id="user-profile.censo-review.projection", schema_version=1, schema_fingerprint="f" * 64
    )
    reference = OperationReviewProjectionReferenceV1(
        operation_id="a" * 64,
        interaction_id="b" * 64,
        revision=revision,
        review_projection_schema=schema,
        definition_contract_digest="c" * 64,
        expires_at=None,
    )
    return OperationReviewAvailableInteractionV1(
        operation_id=reference.operation_id,
        interaction_id=reference.interaction_id,
        revision=revision,
        presentation_code="user-profile.censo-review.projection",
        response_schema=schema,
        expires_at=None,
        review_reference=reference,
    )


class _Client:
    profile_id: UUID = uuid4()
    session_id: UUID = uuid4()


def test_holder_claims_displayed_digest_and_returns_only_verified_successor(monkeypatch: pytest.MonkeyPatch) -> None:
    relay = OperationRelay(cast(FrontendClient, _Client()))
    document: dict[str, JsonValue] = {"plan_digest": "exact-role-plan"}
    successor_document: dict[str, JsonValue] = {"plan_digest": "exact-role-plan", "revision": 4}
    pending = _pending(3)
    successor = _pending(4)
    reviews: Iterator[tuple[OperationReviewAvailableInteractionV1, dict[str, JsonValue]]] = iter(
        ((pending, document), (successor, successor_document))
    )
    sent: list[OperationRequest] = []

    def review(
        _operation_id: str, *, deadline: float
    ) -> tuple[OperationReviewAvailableInteractionV1, dict[str, JsonValue]]:
        return next(reviews)

    def exchange(request: OperationRequest, *, deadline: float) -> OperationReply:
        assert isinstance(request, OperationReviewClaim)
        sent.append(request)
        assert request.reference == pending.review_reference
        assert request.reviewed_document_digest == content_hash_hex(document)
        return OperationReviewClaimed(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            reference=successor.review_reference,
            reviewed_document_digest=content_hash_hex(document),
            allowed_intents=frozenset({"apply", "reject"}),
        )

    monkeypatch.setattr(relay, "_review", review)
    monkeypatch.setattr(relay, "_exchange", exchange)
    result = relay.handle(
        "operation_review_claim",
        {
            "operation_id": pending.operation_id,
            "interaction_id": pending.interaction_id,
            "revision": 3,
            "review_digest": content_hash_hex(document),
        },
    )
    assert len(sent) == 1
    assert result["kind"] == "operation_review_claimed"
    assert result["revision"] == 4
    assert result["document"] == successor_document
    assert result["review_digest"] == content_hash_hex(successor_document)


@pytest.mark.parametrize("revision,digest,code", [(2, None, "not_pending"), (3, "f" * 64, "review_changed")])
def test_changed_display_never_claims(
    monkeypatch: pytest.MonkeyPatch,
    revision: int,
    digest: str | None,
    code: str,
) -> None:
    relay = OperationRelay(cast(FrontendClient, _Client()))
    document: dict[str, JsonValue] = {"plan_digest": "exact-role-plan"}

    def review(
        _operation_id: str, *, deadline: float
    ) -> tuple[OperationReviewAvailableInteractionV1, dict[str, JsonValue]]:
        return _pending(3), document

    def exchange(request: OperationRequest, *, deadline: float) -> OperationReply:
        raise AssertionError("changed display must never request a claim")

    monkeypatch.setattr(relay, "_review", review)
    monkeypatch.setattr(relay, "_exchange", exchange)
    with pytest.raises(RelayRefusedError, match=code):
        relay.handle(
            "operation_review_claim",
            {
                "operation_id": "a" * 64,
                "interaction_id": "b" * 64,
                "revision": revision,
                "review_digest": digest or content_hash_hex(document),
            },
        )


def test_holder_lists_claimable_reviews_and_refuses_any_other_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    relay = OperationRelay(cast(FrontendClient, _Client()))
    replies: Iterator[OperationReply] = iter(
        (
            OperationClaimableReviewsListed(
                request_id=uuid4(), runtime_boot_id=uuid4(), connection_id=uuid4(), operation_ids=("a" * 64,)
            ),
            OperationReviewClaimed(
                request_id=uuid4(),
                runtime_boot_id=uuid4(),
                connection_id=uuid4(),
                reference=_pending(3).review_reference,
                reviewed_document_digest="d" * 64,
                allowed_intents=frozenset({"apply", "reject"}),
            ),
        )
    )
    sent: list[OperationRequest] = []

    def exchange(request: OperationRequest, *, deadline: float) -> OperationReply:
        sent.append(request)
        return next(replies)

    monkeypatch.setattr(relay, "_exchange", exchange)
    assert relay.handle("operation_review_claimable", {}) == {
        "kind": "operation_reviews_claimable",
        "operation_ids": ["a" * 64],
    }
    assert isinstance(sent[0], OperationClaimableReviews)
    assert (sent[0].profile_id, sent[0].session_id) == (_Client.profile_id, _Client.session_id)
    with pytest.raises(RelayRefusedError, match="unavailable"):
        relay.handle("operation_review_claimable", {})
