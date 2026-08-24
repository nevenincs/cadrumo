"""Conformance tests for the renderer-neutral public operation DTO family."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

import pytest
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

import cadrumo.application.operations as public_operations
from cadrumo.application.operations import (
    OperationCancellationRefusalCode,
    OperationCancellationRefusalV1,
    OperationDetachRefusalCode,
    OperationDetachRefusalV1,
    OperationNoPendingInteractionV1,
    OperationObservationRefusalCode,
    OperationObservationRefusalV1,
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationObservationSuccessV1,
    OperationPublicDefinitionContractV1,
    OperationPublicEventPageV1,
    OperationPublicPhaseEventV1,
    OperationPublicProjectionV1,
    OperationResponseControlRefusalCode,
    OperationResponseControlRefusalV1,
    OperationReviewProjectionReferenceV1,
    OperationReviewProjectionRefusalCode,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionResultV1,
    OperationReviewProjectionSuccessV1,
    OperationSchemaIdentityV1,
    OperationWorkspaceRefreshTargetRefusalCode,
    OperationWorkspaceRefreshTargetRefusalV1,
    OperationWorkspaceRefreshTargetRequestV1,
    OperationWorkspaceRefreshTargetResultV1,
    OperationWorkspaceRefreshTargetSuccessV1,
)
from cadrumo.application.operations._model_contract import require_strict_frozen_operation_model_graph
from cadrumo.core import (
    OperationCancellation,
    OperationClosePolicy,
    OperationEffect,
    OperationEventKind,
    OperationLifecycle,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 24, 12, tzinfo=UTC)
_OPERATION_ID = "1" * 64
_INTERACTION_ID = "2" * 64
_DIGEST = "3" * 64
_SCHEMA = OperationSchemaIdentityV1(
    schema_id="profile.sync.review",
    schema_version=1,
    schema_fingerprint=_DIGEST,
)


class SafeProjection(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)
    code: Annotated[str, Field(min_length=1)]


def _projection(*, anchor_cursor: int = 0) -> OperationPublicProjectionV1:
    contract = OperationPublicDefinitionContractV1.model_construct(definition_id="profile.sync")
    return OperationPublicProjectionV1.model_construct(
        observation_version=1,
        operation_id=_OPERATION_ID,
        definition_id="profile.sync",
        subject_ref="profile:active",
        revision=4,
        anchor_cursor=anchor_cursor,
        definition_contract=contract,
        contract_set_digest=_DIGEST,
        lifecycle=OperationLifecycle.RUNNING,
        terminal_condition=None,
        effect=OperationEffect.NONE,
        phase_code="profile.sync",
        started_at=_NOW,
        updated_at=_NOW,
        progress=None,
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
        cancellation=OperationCancellation.COOPERATIVE,
        cancellable_now=True,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref=None,
        refusal_ref=None,
        diagnostic_ref=None,
    )


def test_public_endpoint_versions_are_independent_strict_axes() -> None:
    observation = OperationObservationRequestV1(
        operation_id=_OPERATION_ID,
        after_cursor=0,
        page_limit=20,
    )
    refresh = OperationWorkspaceRefreshTargetRequestV1(
        operation_id=_OPERATION_ID,
        terminal_revision=4,
        definition_contract_digest=_DIGEST,
        target_schema=_SCHEMA,
    )

    assert observation.observation_version == 1
    assert refresh.refresh_target_version == 1
    assert "version" not in observation.__class__.model_fields
    assert "version" not in refresh.__class__.model_fields
    assert "result_ref" not in refresh.__class__.model_fields
    with pytest.raises(ValidationError):
        OperationObservationRequestV1.model_validate(
            {
                "observation_version": "1",
                "operation_id": _OPERATION_ID,
                "after_cursor": 0,
                "page_limit": 20,
            }
        )
    with pytest.raises(ValidationError):
        OperationObservationRequestV1(
            operation_id=_OPERATION_ID,
            after_cursor=0,
            page_limit=20,
            unknown=True,
        )


def test_observation_result_is_closed_and_anchor_consistent() -> None:
    page = OperationPublicEventPageV1(
        operation_id=_OPERATION_ID,
        anchor_cursor=0,
        requested_cursor=0,
        status="caught_up",
        events=(),
        next_cursor=0,
        restart_cursor=None,
    )
    success = OperationObservationSuccessV1(projection=_projection(), event_page=page)
    adapter = TypeAdapter(OperationObservationResultV1)

    assert adapter.validate_python(success) == success
    assert isinstance(
        adapter.validate_python(
            OperationObservationRefusalV1(
                code=OperationObservationRefusalCode.UNKNOWN_OPERATION,
                requested_version=1,
                diagnostic_ref=None,
            )
        ),
        OperationObservationRefusalV1,
    )
    with pytest.raises(ValidationError, match="share one anchor"):
        OperationObservationSuccessV1(
            projection=_projection(anchor_cursor=1),
            event_page=page,
        )


def test_public_event_page_enforces_contiguous_bounded_rows_and_resynchronization() -> None:
    first = OperationPublicPhaseEventV1(
        revision=2,
        sequence=1,
        timestamp=_NOW,
        code="phase.changed",
        kind=OperationEventKind.PHASE,
        phase_code="profile.sync",
    )
    page = OperationPublicEventPageV1(
        operation_id=_OPERATION_ID,
        anchor_cursor=1,
        requested_cursor=0,
        status="page",
        events=(first,),
        next_cursor=1,
        restart_cursor=None,
    )
    assert page.events == (first,)

    with pytest.raises(ValidationError, match="contiguous"):
        OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=2,
            requested_cursor=0,
            status="page",
            events=(first.model_copy(update={"sequence": 2}),),
            next_cursor=2,
            restart_cursor=None,
        )
    with pytest.raises(ValidationError, match="restart cursor"):
        OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=4,
            requested_cursor=1,
            status="compacted",
            events=(),
            next_cursor=1,
            restart_cursor=None,
        )


def test_review_reference_and_success_never_carry_response_authority() -> None:
    reference = OperationReviewProjectionReferenceV1(
        operation_id=_OPERATION_ID,
        interaction_id=_INTERACTION_ID,
        revision=4,
        review_projection_schema=_SCHEMA,
        definition_contract_digest=_DIGEST,
        expires_at=_NOW,
    )
    success = OperationReviewProjectionSuccessV1[SafeProjection](
        projection_schema=_SCHEMA,
        definition_contract_digest=_DIGEST,
        projection=SafeProjection(code="review.ready"),
    )
    adapter = TypeAdapter(OperationReviewProjectionResultV1[SafeProjection])

    assert adapter.validate_python(success) == success
    forbidden = {"token", "bearer", "payload", "operand", "continuation", "baseline", "capability"}
    reference_fields = set(reference.__class__.model_fields)
    success_fields = set(success.__class__.model_fields)
    assert not any(part in field for field in reference_fields | success_fields for part in forbidden)
    with pytest.raises(ValidationError):
        OperationReviewProjectionSuccessV1[SafeProjection](
            projection_schema=_SCHEMA,
            definition_contract_digest=_DIGEST,
            projection={"code": 1},
        )


@pytest.mark.parametrize(
    ("model", "code"),
    [
        (OperationObservationRefusalV1, OperationObservationRefusalCode.OBSERVATION_UNAVAILABLE),
        (OperationReviewProjectionRefusalV1, OperationReviewProjectionRefusalCode.REVIEW_PROJECTION_UNAVAILABLE),
        (OperationResponseControlRefusalV1, OperationResponseControlRefusalCode.RESPONSE_AUTHORITY_UNAVAILABLE),
        (OperationCancellationRefusalV1, OperationCancellationRefusalCode.CANCELLATION_UNAVAILABLE),
        (OperationDetachRefusalV1, OperationDetachRefusalCode.DETACH_NOT_ALLOWED),
        (
            OperationWorkspaceRefreshTargetRefusalV1,
            OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET,
        ),
    ],
)
def test_public_refusals_are_closed_renderer_neutral_records(
    model: type[BaseModel],
    code: StrEnum,
) -> None:
    refusal = model(code=code, requested_version=1, diagnostic_ref=None)
    assert refusal.outcome == "refused"
    assert set(refusal.model_dump()) <= {
        "outcome",
        "observation_version",
        "review_projection_version",
        "response_control_version",
        "cancellation_version",
        "detach_version",
        "refresh_target_version",
        "code",
        "requested_version",
        "supported_version",
        "diagnostic_ref",
    }


def test_refresh_result_is_exactly_specialized_and_exported_from_the_facade() -> None:
    success = OperationWorkspaceRefreshTargetSuccessV1[SafeProjection](
        target_schema=_SCHEMA,
        definition_contract_digest=_DIGEST,
        target=SafeProjection(code="workspace.refresh"),
    )
    adapter = TypeAdapter(OperationWorkspaceRefreshTargetResultV1[SafeProjection])

    assert adapter.validate_python(success) == success
    assert public_operations.OperationWorkspaceRefreshTargetRequestV1 is (OperationWorkspaceRefreshTargetRequestV1)
    assert public_operations.OperationPublicProjectionV1 is OperationPublicProjectionV1


@pytest.mark.parametrize(
    "model_type",
    [
        OperationObservationRequestV1,
        OperationObservationRefusalV1,
        OperationPublicEventPageV1,
        OperationReviewProjectionReferenceV1,
        OperationResponseControlRefusalV1,
        OperationCancellationRefusalV1,
        OperationDetachRefusalV1,
        OperationWorkspaceRefreshTargetRequestV1,
        OperationWorkspaceRefreshTargetRefusalV1,
        OperationReviewProjectionSuccessV1[SafeProjection],
        OperationWorkspaceRefreshTargetSuccessV1[SafeProjection],
    ],
)
def test_every_public_model_graph_is_strict_frozen_and_closed(model_type: type[BaseModel]) -> None:
    require_strict_frozen_operation_model_graph(model_type, path="public DTO")
    OperationSchemaIdentityV1.from_model(
        schema_id="operations.public.contract",
        schema_version=1,
        model_type=model_type,
    )
