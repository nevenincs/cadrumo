"""The versioned public claim exchanges safe coordinates and never actor credentials."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from cadrumo.application.operations.interactions import OperationResponseIntent
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1

from ..operation_access import OperationReviewClaim, OperationReviewClaimed
from ..profile_access import Reply, Request

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _reference() -> OperationReviewProjectionReferenceV1:
    return OperationReviewProjectionReferenceV1(
        operation_id="a" * 64,
        interaction_id="b" * 64,
        revision=5,
        review_projection_schema=OperationSchemaIdentityV1(
            schema_id="user-profile.censo-review.projection",
            schema_version=1,
            schema_fingerprint="c" * 64,
        ),
        definition_contract_digest="d" * 64,
        expires_at=None,
    )


def test_public_claim_request_and_successor_reply_round_trip_through_wire_unions() -> None:
    request = OperationReviewClaim(
        request_id=uuid4(),
        profile_id=uuid4(),
        session_id=uuid4(),
        reference=_reference(),
        reviewed_document_digest="e" * 64,
    )
    assert Request.model_validate_json(request.model_dump_json()).root == request
    reply = OperationReviewClaimed(
        request_id=request.request_id,
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        reference=request.reference.model_copy(update={"revision": 6}),
        reviewed_document_digest=request.reviewed_document_digest,
        allowed_intents=frozenset({OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}),
    )
    assert Reply.model_validate_json(reply.model_dump_json()).root == reply
    assert set(reply.model_dump()) == {
        "kind",
        "review_claim_version",
        "request_id",
        "runtime_boot_id",
        "connection_id",
        "reference",
        "reviewed_document_digest",
        "allowed_intents",
    }


@pytest.mark.parametrize("forged", ["actor_ref", "attestation", "response_token", "frontend"])
def test_client_claim_cannot_declare_claimant_provenance_or_bearer(forged: str) -> None:
    request = OperationReviewClaim(
        request_id=uuid4(),
        profile_id=uuid4(),
        session_id=uuid4(),
        reference=_reference(),
        reviewed_document_digest="e" * 64,
    )
    with pytest.raises(ValidationError):
        OperationReviewClaim.model_validate({**request.model_dump(), forged: "forged"})
