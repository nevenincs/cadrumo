"""Registered runtime bridges retain the full review request and result."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.operations.models import OperationId
from ....application.review.enums import ReviewSeverity, ReviewState
from ....application.review.read_operation import (
    REVIEW_QUEUE_OPERATION_DEFINITION_ID,
    REVIEW_VIEW_OPERATION_DEFINITION_ID,
    ReviewQueueReadProjection,
    ReviewQueueReadRequest,
    ReviewQueueRowProjection,
    ReviewViewReadProjection,
    ReviewViewReadRequest,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import runtime_review as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "f" * 64
_SINCE = datetime(2026, 9, 30, 11, 30, tzinfo=UTC)


def _queue_request(profile_id: UUID = _PROFILE) -> ReviewQueueReadRequest:
    return ReviewQueueReadRequest(
        profile_id=profile_id,
        kinds=("modelo_finding", "ledger_transaction"),
        source_kinds=("ledger_transaction", "modelo_finding"),
        state=ReviewState.ALL,
        modelo="303",
        output_language=OutputLanguage.EN,
    )


def _row(profile_id: UUID = _PROFILE) -> ReviewQueueRowProjection:
    return ReviewQueueRowProjection(
        item_id="review-001",
        kind="modelo_finding",
        source_kind="modelo_finding",
        affected_object_id="draft-abc",
        bucket_id=str(profile_id),
        modelo="303",
        period=None,
        severity=ReviewSeverity.HIGH,
        state=ReviewState.ALL,
        blocking=True,
        reason="stale approval: taxpayer changed",
        current_owner_surface="app modelo",
        canonical_next_command="aeat app modelo work verify draft-abc",
        since=_SINCE,
        summary="modelo 303 draft needs review",
        legal_refs=("ley-37-1992:art-94",),
    )


def _request(definition_id: str, profile_id: UUID = _PROFILE) -> BaseModel:
    if definition_id == REVIEW_QUEUE_OPERATION_DEFINITION_ID:
        return _queue_request(profile_id)
    return ReviewViewReadRequest(
        profile_id=profile_id,
        item_id="review-001",
        output_language=OutputLanguage.EN,
    )


def _projection(definition_id: str, profile_id: UUID = _PROFILE) -> BaseModel:
    request = _request(definition_id, profile_id)
    if isinstance(request, ReviewQueueReadRequest):
        row = _row(profile_id)
        queue_request = request.model_copy(update={"kinds": ("modelo_finding",), "source_kinds": ("modelo_finding",)})
        return ReviewQueueReadProjection(profile_id=profile_id, request=queue_request, rows=(row,))
    return ReviewViewReadProjection(profile_id=profile_id, request=request, row=_row(profile_id))


def _invoke(ctx: typer.Context, definition_id: str) -> BaseModel:
    if definition_id == REVIEW_QUEUE_OPERATION_DEFINITION_ID:
        return bridge.run_review_queue(ctx, cast(ReviewQueueReadRequest, _request(definition_id)))
    return bridge.run_review_view(ctx, cast(ReviewViewReadRequest, _request(definition_id)))


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    *,
    definition_id: str,
    profile_id: UUID,
    projection: BaseModel,
    submitted: list[BaseModel],
) -> None:
    client = cast(RuntimeFrontendClient, SimpleNamespace(profile_id=profile_id))
    monkeypatch.setattr(bridge, "active_bucket_id_or_refuse", lambda: str(profile_id))

    def bound_client(_ctx: typer.Context, *, expected_profile_id: UUID) -> RuntimeFrontendClient:
        assert expected_profile_id == profile_id
        return client

    monkeypatch.setattr(bridge, "require_profile_client", bound_client)

    def submit(
        actual_client: RuntimeFrontendClient,
        request: BaseModel,
        **kwargs: object,
    ) -> RegisteredOperationCompletion[BaseModel]:
        submitted.append(request)
        assert actual_client is client
        assert kwargs["definition_id"] == definition_id
        assert kwargs["subject_ref"] == profile_operation_subject(str(profile_id))
        assert kwargs["result_type"] is type(projection)
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        assert kwargs["timeout"] == 120
        return RegisteredOperationCompletion(
            operation_id=cast("OperationId", _OPERATION_ID),
            projection=projection,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


@pytest.mark.parametrize(
    ("definition_id", "result_type"),
    [
        (REVIEW_QUEUE_OPERATION_DEFINITION_ID, ReviewQueueReadProjection),
        (REVIEW_VIEW_OPERATION_DEFINITION_ID, ReviewViewReadProjection),
    ],
)
def test_bridge_submits_exact_profile_request_and_returns_complete_projection(
    monkeypatch: pytest.MonkeyPatch,
    definition_id: str,
    result_type: type[BaseModel],
) -> None:
    request = _request(definition_id)
    projection = _projection(definition_id)
    if isinstance(projection, ReviewQueueReadProjection):
        request = projection.request
    submitted: list[BaseModel] = []
    _bind(
        monkeypatch,
        definition_id=definition_id,
        profile_id=_PROFILE,
        projection=projection,
        submitted=submitted,
    )

    if definition_id == REVIEW_QUEUE_OPERATION_DEFINITION_ID:
        result = bridge.run_review_queue(cast(typer.Context, cast(object, None)), cast(ReviewQueueReadRequest, request))
    else:
        result = bridge.run_review_view(cast(typer.Context, cast(object, None)), cast(ReviewViewReadRequest, request))

    assert submitted == [request]
    assert isinstance(result, result_type)
    if isinstance(result, ReviewQueueReadProjection):
        assert result.request == request
        assert result.rows[0].legal_refs == ("ley-37-1992:art-94",)
        assert result.rows[0].reason == "stale approval: taxpayer changed"
    else:
        assert result.request == request
        assert result.row.legal_refs == ("ley-37-1992:art-94",)
        assert result.row.reason == "stale approval: taxpayer changed"


@pytest.mark.parametrize("definition_id", [REVIEW_QUEUE_OPERATION_DEFINITION_ID, REVIEW_VIEW_OPERATION_DEFINITION_ID])
def test_bridge_refuses_a_foreign_profile_projection_with_its_submitted_receipt(
    monkeypatch: pytest.MonkeyPatch,
    definition_id: str,
) -> None:
    request = _request(definition_id)
    foreign = _projection(definition_id, _OTHER_PROFILE)
    if isinstance(foreign, ReviewQueueReadProjection):
        projection = ReviewQueueReadProjection.model_construct(
            profile_id=_OTHER_PROFILE,
            request=request,
            rows=foreign.rows,
        )
    else:
        projection = ReviewViewReadProjection.model_construct(
            profile_id=_OTHER_PROFILE,
            request=request,
            row=foreign.row,
        )
    submitted: list[BaseModel] = []
    _bind(
        monkeypatch,
        definition_id=definition_id,
        profile_id=_PROFILE,
        projection=projection,
        submitted=submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as exc_info:
        if definition_id == REVIEW_QUEUE_OPERATION_DEFINITION_ID:
            bridge.run_review_queue(cast(typer.Context, cast(object, None)), cast(ReviewQueueReadRequest, request))
        else:
            bridge.run_review_view(cast(typer.Context, cast(object, None)), cast(ReviewViewReadRequest, request))

    assert submitted == [request]
    assert exc_info.value.context["operation_id"] == _OPERATION_ID
    assert exc_info.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
    assert exc_info.value.context["terminal_condition"] == OperationTerminalCondition.SUCCEEDED.value
    assert exc_info.value.context["effect"] == OperationEffect.NONE.value
