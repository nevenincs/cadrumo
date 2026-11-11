"""Registered runtime bridges retain the full review request and result."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.contracts.contracts import RefusalCode

from ....application.review.enums import ReviewSeverity, ReviewState
from ....application.review.read_contracts import (
    REVIEW_QUEUE_OPERATION_DEFINITION_ID,
    REVIEW_VIEW_OPERATION_DEFINITION_ID,
    ReviewQueueReadRequest,
    ReviewViewReadRequest,
)
from ....application.review.read_projections import (
    ReviewQueueReadProjection,
    ReviewQueueRowProjection,
    ReviewViewReadProjection,
)
from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect, OperationTerminalCondition
from .. import operation_review as bridge
from .operation_bridge_support import bind_exact_profile_read

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
    bind_exact_profile_read(
        monkeypatch,
        bridge=bridge,
        definition_id=definition_id,
        profile_id=profile_id,
        projection=projection,
        submitted=submitted,
        result_version=1,
        operation_id=_OPERATION_ID,
    )


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
        assert isinstance(foreign, ReviewViewReadProjection)
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
    refusal_context = exc_info.value.context
    assert refusal_context is not None
    assert refusal_context["operation_id"] == _OPERATION_ID
    assert refusal_context["reason"] == RefusalCode.INVALID_FRAME.value
    assert refusal_context["terminal_condition"] == OperationTerminalCondition.SUCCEEDED.value
    assert refusal_context["effect"] == OperationEffect.NONE.value
