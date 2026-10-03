"""The CLI preview bridge binds worker reads to the prepared profile."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
import typer

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode
from cadrumo.application.user_profile.censal_operation import CensalProfileBaseline
from cadrumo.application.user_profile.censal_preview_operation import (
    CENSAL_PREVIEW_OPERATION_DEFINITION_ID,
    CensalPreviewOperationRequest,
    CensalPreviewOperationResult,
)
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.entrypoints.cli.config import runtime_censal_preview
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError
from cadrumo.entrypoints.cli.registered_operation_contracts import RegisteredOperationCompletion

_PROFILE_ID = UUID("aa000000-0000-4000-8000-0000000000aa")
_FOREIGN_PROFILE_ID = UUID("bb000000-0000-4000-8000-0000000000bb")
_SESSION_ID = UUID("cc000000-0000-4000-8000-0000000000cc")
_OPERATION_ID = "f" * 64

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _BoundClient:
    profile_id = _PROFILE_ID
    session_id = _SESSION_ID
    frontend = OperationFrontendProjection.CLI


def _install_bridge(
    monkeypatch: pytest.MonkeyPatch,
    *,
    projection_profile_id: UUID = _PROFILE_ID,
    effect: OperationEffect = OperationEffect.NONE,
) -> tuple[typer.Context, _BoundClient, CensalProfileBaseline, dict[str, Any], CensalPreviewOperationResult]:
    client = _BoundClient()
    ctx = cast(typer.Context, object())
    baseline = CensalProfileBaseline(profile_id=str(client.profile_id), record_revision=3, content_digest="a" * 64)
    prepared = cast(
        Any,
        SimpleNamespace(operation_request=SimpleNamespace(baseline=baseline)),
    )
    projection = CensalPreviewOperationResult(
        profile_id=projection_profile_id,
        source_url="https://example.invalid/censal",
    )
    captured: dict[str, Any] = {}

    def bound_profile_client(received_ctx: typer.Context) -> _BoundClient:
        assert received_ctx is ctx
        return client

    def prepare_censal_review(received_ctx: typer.Context) -> Any:
        assert received_ctx is ctx
        return prepared

    def run_registered_operation(received_client: object, payload: object, **options: object):
        captured.update(client=received_client, payload=payload, options=options)
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        )

    monkeypatch.setattr(runtime_censal_preview, "bound_profile_client", bound_profile_client)
    monkeypatch.setattr(runtime_censal_preview, "prepare_censal_review", prepare_censal_review)
    monkeypatch.setattr(runtime_censal_preview, "run_registered_operation", run_registered_operation)
    return ctx, client, baseline, captured, projection


@pytest.mark.parametrize("effect", [OperationEffect.NONE, OperationEffect.UPDATED])
def test_preview_bridge_submits_prepared_baseline_under_exact_profile_subject(
    monkeypatch: pytest.MonkeyPatch,
    effect: OperationEffect,
) -> None:
    ctx, client, baseline, captured, projection = _install_bridge(monkeypatch, effect=effect)

    preview = runtime_censal_preview.preview_censal_with_runtime(ctx)

    assert preview is projection
    assert captured["client"] is client
    request = captured["payload"]
    assert isinstance(request, CensalPreviewOperationRequest)
    assert request.baseline == baseline
    assert request.baseline.profile_id == str(client.profile_id)
    assert captured["options"] == {
        "definition_id": CENSAL_PREVIEW_OPERATION_DEFINITION_ID,
        "subject_ref": profile_operation_subject(str(client.profile_id)),
        "result_type": CensalPreviewOperationResult,
        "request_version": 1,
        "result_version": 1,
        "timeout": 120,
    }


@pytest.mark.parametrize(
    ("projection_profile_id", "effect"),
    [
        (_FOREIGN_PROFILE_ID, OperationEffect.NONE),
        (_PROFILE_ID, OperationEffect.UNKNOWN),
    ],
)
def test_preview_bridge_refuses_profile_or_effect_mismatch_with_operation_identity(
    monkeypatch: pytest.MonkeyPatch,
    projection_profile_id: UUID,
    effect: OperationEffect,
) -> None:
    ctx, _client, _baseline, _captured, _projection = _install_bridge(
        monkeypatch,
        projection_profile_id=projection_profile_id,
        effect=effect,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        runtime_censal_preview.preview_censal_with_runtime(ctx)

    assert refused.value.context == {
        "operation_id": _OPERATION_ID,
        "reason": RuntimeRefusalCode.INVALID_FRAME.value,
        "effect": effect.value,
        "terminal_condition": OperationTerminalCondition.SUCCEEDED.value,
    }
