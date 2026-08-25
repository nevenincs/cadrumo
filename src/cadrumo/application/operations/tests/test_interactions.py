"""Real binding proofs for operation interactions and responses."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, TypedDict

import pytest
from pydantic import TypeAdapter, ValidationError

from ....core import OperationInteractionKind
from ..interactions import (
    OperationApplyResponse,
    OperationInteractionRequest,
    OperationInteractionResponse,
    OperationRejectResponse,
)
from ..models import OperationIdentity

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 13, 19, 0, tzinfo=UTC)
_OPERATION_ID = "a" * 64
_INTERACTION_ID = "b" * 64
_TOKEN = "c" * 64
_CONTINUATION = "d" * 64
_PROPOSAL = "e" * 64
_BASELINE = "f" * 64
_EFFECT = "1" * 64
_ACTOR = "operator:local"
_IDENTITY = OperationIdentity(
    operation_id=_OPERATION_ID,
    definition_id="profile.sync",
    subject_ref="profile:active",
)


class _RequestValues(TypedDict):
    interaction_id: str
    identity: OperationIdentity
    revision: int
    kind: OperationInteractionKind
    presentation_code: str
    response_schema_ref: str
    continuation_digest: str


class _ResponseValues(TypedDict):
    interaction_id: str
    operation_id: str
    revision: int
    response_token: str
    continuation_digest: str
    reviewed_proposal_digest: str
    actor_ref: str
    responded_at: datetime


def test_interaction_request_requires_exact_revision_and_continuation_digest() -> None:
    request = OperationInteractionRequest(
        interaction_id=_INTERACTION_ID,
        identity=_IDENTITY,
        revision=4,
        kind=OperationInteractionKind.REVIEW,
        presentation_code="profile.sync.review",
        response_schema_ref="schema:profile-sync-review-v1",
        continuation_digest=_CONTINUATION,
        expires_at=_NOW,
    )
    assert request.revision == 4
    with pytest.raises(ValidationError):
        OperationInteractionRequest.model_validate({**request.model_dump(), "continuation_digest": "short"})


def test_interaction_request_refuses_naive_expiry_and_extra_frontend_state() -> None:
    values: _RequestValues = {
        "interaction_id": _INTERACTION_ID,
        "identity": _IDENTITY,
        "revision": 4,
        "kind": OperationInteractionKind.INPUT,
        "presentation_code": "profile.secret.input",
        "response_schema_ref": "schema:secret-v1",
        "continuation_digest": _CONTINUATION,
    }
    with pytest.raises(ValidationError):
        TypeAdapter(OperationInteractionRequest).validate_python(
            {**values, "expires_at": datetime(2026, 8, 13, 19, 0)},
        )
    with pytest.raises(ValidationError):
        TypeAdapter(OperationInteractionRequest).validate_python(
            {**values, "localized_prompt": "Enter your secret"},
        )


def _response_values() -> _ResponseValues:
    return {
        "interaction_id": _INTERACTION_ID,
        "operation_id": _OPERATION_ID,
        "revision": 4,
        "response_token": _TOKEN,
        "continuation_digest": _CONTINUATION,
        "reviewed_proposal_digest": _PROPOSAL,
        "actor_ref": _ACTOR,
        "responded_at": _NOW,
    }


def test_apply_and_reject_are_discriminated_exact_responses() -> None:
    adapter = TypeAdapter(OperationInteractionResponse)
    apply = adapter.validate_python(
        {**_response_values(), "intent": "apply", "baseline_digest": _BASELINE, "proposed_effect_digest": _EFFECT}
    )
    reject = adapter.validate_python({**_response_values(), "intent": "reject", "reason_code": "operator.reject"})
    assert isinstance(apply, OperationApplyResponse)
    assert isinstance(reject, OperationRejectResponse)


@pytest.mark.parametrize(
    "field", ("interaction_id", "operation_id", "response_token", "continuation_digest", "reviewed_proposal_digest")
)
def test_response_refuses_missing_or_malformed_binding_identity(
    field: Literal[
        "interaction_id", "operation_id", "response_token", "continuation_digest", "reviewed_proposal_digest"
    ],
) -> None:
    values = _response_values()
    malformed = {**values, field: "not-an-opaque-binding"}
    with pytest.raises(ValidationError):
        TypeAdapter(OperationApplyResponse).validate_python(malformed)


def test_response_is_frozen_and_refuses_payload_or_frontend_prose() -> None:
    response = OperationApplyResponse(**_response_values(), baseline_digest=_BASELINE, proposed_effect_digest=_EFFECT)
    with pytest.raises(ValidationError):
        response.revision = 5
    with pytest.raises(ValidationError):
        TypeAdapter(OperationApplyResponse).validate_python(
            {
                **_response_values(),
                "baseline_digest": _BASELINE,
                "proposed_effect_digest": _EFFECT,
                "payload": {"field": "secret"},
            },
        )


@pytest.mark.parametrize(
    "field", ("baseline_digest", "reviewed_proposal_digest", "proposed_effect_digest", "actor_ref")
)
def test_apply_refuses_mutated_approval_evidence(field: str) -> None:
    values = {
        **_response_values(),
        "baseline_digest": _BASELINE,
        "proposed_effect_digest": _EFFECT,
        field: "raw or malformed evidence",
    }
    with pytest.raises(ValidationError):
        TypeAdapter(OperationApplyResponse).validate_python(values)


def test_apply_round_trip_retains_every_exact_approval_correlation() -> None:
    adapter = TypeAdapter(OperationInteractionResponse)
    response = adapter.validate_python(
        {
            **_response_values(),
            "intent": "apply",
            "baseline_digest": _BASELINE,
            "proposed_effect_digest": _EFFECT,
        }
    )
    assert adapter.validate_json(adapter.dump_json(response)) == response
    assert isinstance(response, OperationApplyResponse)
    assert (
        response.operation_id,
        response.interaction_id,
        response.revision,
        response.response_token,
        response.continuation_digest,
        response.baseline_digest,
        response.reviewed_proposal_digest,
        response.proposed_effect_digest,
        response.actor_ref,
        response.responded_at,
    ) == (
        _OPERATION_ID,
        _INTERACTION_ID,
        4,
        _TOKEN,
        _CONTINUATION,
        _BASELINE,
        _PROPOSAL,
        _EFFECT,
        _ACTOR,
        _NOW,
    )


def test_reject_binds_actor_time_and_reviewed_proposal_without_apply_only_evidence() -> None:
    reject = OperationRejectResponse(**_response_values(), reason_code="operator.reject")
    assert reject.actor_ref == _ACTOR
    assert reject.reviewed_proposal_digest == _PROPOSAL
    assert "baseline_digest" not in type(reject).model_fields
    assert "proposed_effect_digest" not in type(reject).model_fields
