"""The client hashes the displayed envelope and accepts only its exact claim ACK."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field

from cadrumo.application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from cadrumo.application.operations.frontend_requests import OperationReviewProjectionSuccessV1
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.models import STRICT_FROZEN_CONFIG

from ...contracts.contracts import RefusalCode, RefusalError
from ...contracts.operation_access import (
    OperationProjected,
    OperationReview,
    OperationReviewClaim,
    OperationReviewClaimed,
)
from ..frontend_client import FrontendClient
from ..operation_controller import OperationController

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class Review(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    label: str = Field(min_length=1, max_length=128)


class ReviewClient:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.session_id = uuid4()
        self.profile_id = uuid4()
        self.requests: list[OperationReview | OperationReviewClaim] = []
        self.reference = OperationReviewProjectionReferenceV1(
            operation_id="a" * 64,
            interaction_id="d" * 64,
            revision=4,
            review_projection_schema=OperationSchemaIdentityV1.from_model(
                schema_id="test.review", schema_version=1, model_type=Review
            ),
            definition_contract_digest="b" * 64,
            expires_at=None,
        )
        self.document = OperationReviewProjectionSuccessV1[Review](
            projection_schema=self.reference.review_projection_schema,
            definition_contract_digest=self.reference.definition_contract_digest,
            projection=Review(label="RevisiÃƒÂ³n de instalaciÃƒÂ³n"),
        ).model_dump(mode="json")
        self.mutation: str | None = None

    def operation(
        self, request: OperationReview | OperationReviewClaim, *, deadline: float
    ) -> OperationProjected | OperationReviewClaimed:
        self.requests.append(request)
        if isinstance(request, OperationReview):
            return OperationProjected(
                request_id=request.request_id,
                runtime_boot_id=uuid4(),
                connection_id=uuid4(),
                operation_id=self.reference.operation_id,
                projection_kind="review",
                document=self.document,
            )
        reference = self.reference.model_copy(update={"revision": 5})
        digest = content_hash_hex(self.document)
        if self.mutation == "digest":
            digest = "c" * 64
        elif self.mutation == "interaction":
            reference = reference.model_copy(update={"interaction_id": "e" * 64})
        elif self.mutation == "revision":
            reference = reference.model_copy(update={"revision": 8})
        return OperationReviewClaimed(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            reference=reference,
            reviewed_document_digest=digest,
            allowed_intents=frozenset({"apply", "reject"}),
        )

    def controller(self) -> OperationController:
        return OperationController(cast(FrontendClient, self), self.reference.operation_id, self.session_id)


@pytest.mark.asyncio
async def test_exact_displayed_envelope_is_fingerprinted_without_a_second_read() -> None:
    client = ReviewClient()
    controller = client.controller()
    review, digest = await controller.resolve_review_document(client.reference, Review)
    assert isinstance(review, OperationReviewProjectionSuccessV1)
    assert review.projection.label == "RevisiÃƒÂ³n de instalaciÃƒÂ³n"
    assert digest == content_hash_hex(client.document)
    assert digest != content_hash_hex(review.projection.model_dump(mode="json"))
    claimed = await controller.claim_review(client.reference, digest)
    assert [type(request) for request in client.requests] == [OperationReview, OperationReviewClaim]
    assert isinstance(client.requests[-1], OperationReviewClaim)
    assert client.requests[-1].reviewed_document_digest == digest
    assert claimed.reference.revision == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["digest", "interaction", "revision"])
async def test_foreign_or_stale_ack_never_becomes_local_response_coordinates(mutation: str) -> None:
    client = ReviewClient()
    client.mutation = mutation
    controller = client.controller()
    with pytest.raises(RefusalError) as raised:
        await controller.claim_review(client.reference, content_hash_hex(client.document))
    assert raised.value.reason is RefusalCode.INVALID_FRAME


@pytest.mark.asyncio
async def test_observed_foreign_operation_cannot_be_claimed() -> None:
    client = ReviewClient()
    with pytest.raises(RefusalError):
        await client.controller().claim_review(
            client.reference.model_copy(update={"operation_id": "f" * 64}), content_hash_hex(client.document)
        )
    assert client.requests == []
