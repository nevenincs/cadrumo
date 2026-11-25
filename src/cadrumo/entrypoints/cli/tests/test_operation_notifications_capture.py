"""Registered notification capture keeps its exact profile and CLI presentation."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import cast
from uuid import UUID

import pytest
import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_deadlines import provider_login_settlement_seconds
from cadrumo_client.contracts.contracts import RefusalCode

from ....application.live.notifications_capture_operation import (
    NOTIFICATIONS_CAPTURE_DEFINITION_ID,
    NotificationsCapturePublicResultV1,
    NotificationsCaptureRequest,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import app_live_notifications_commands as handler
from .. import operation_notifications_capture as bridge
from ..app_live_notifications_results import NotificationsCaptureResult
from .operation_bridge_support import bind_profile_submission

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_CAPTURED_AT = datetime(2025, 3, 6, 7, 8, tzinfo=UTC)
_PERSISTED_AT = datetime(2025, 3, 6, 7, 9, tzinfo=UTC)
_SOURCE_URL = "https://sede.example/notifications"


def _projection() -> NotificationsCapturePublicResultV1:
    return NotificationsCapturePublicResultV1(
        bucket_id=str(_PROFILE),
        snapshot_id="2" * 64,
        captured_at=_CAPTURED_AT,
        persisted_at=_PERSISTED_AT,
        row_count=3,
        source_url=_SOURCE_URL,
    )


_bind = partial(
    bind_profile_submission,
    bridge=bridge,
    operation_id=_OPERATION_ID,
    effect=OperationEffect.UPDATED,
)


def _read() -> bridge.NotificationsCaptureRead:
    return bridge.read_notifications_capture_for_cli(
        cast(typer.Context, cast(object, None)),
        profile_id=_PROFILE,
    )


def test_capture_submits_the_bound_profile_and_accepts_save_or_dedup_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for effect in (OperationEffect.UPDATED, OperationEffect.NONE):
        submitted, bound_profiles = _bind(monkeypatch, _projection(), effect=effect)

        read = _read()

        assert read.completion.operation_id == _OPERATION_ID
        assert read.projection == _projection()
        assert bound_profiles == [_PROFILE]
        assert submitted == [
            (
                NotificationsCaptureRequest(profile_id=_PROFILE),
                {
                    "definition_id": NOTIFICATIONS_CAPTURE_DEFINITION_ID,
                    "subject_ref": profile_operation_subject(str(_PROFILE)),
                    "result_type": NotificationsCapturePublicResultV1,
                    "request_version": 1,
                    "result_version": 1,
                    "timeout": 120,
                    "settlement_timeout": provider_login_settlement_seconds(after_login=120),
                },
            ),
        ]


@pytest.mark.parametrize(
    ("projection_update", "effect", "condition", "refusal_code"),
    [
        ({"bucket_id": "foreign"}, OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, None),
        ({}, OperationEffect.UNKNOWN, OperationTerminalCondition.SUCCEEDED, None),
        ({}, OperationEffect.UPDATED, OperationTerminalCondition.REFUSED, None),
        ({}, OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, RefusalCode.UNAVAILABLE.value),
    ],
)
def test_profile_or_receipt_mismatch_refuses_with_correlated_operation(
    monkeypatch: pytest.MonkeyPatch,
    projection_update: dict[str, object],
    effect: OperationEffect,
    condition: OperationTerminalCondition,
    refusal_code: str | None,
) -> None:
    _bind(
        monkeypatch,
        _projection().model_copy(update=projection_update),
        effect=effect,
        condition=condition,
        refusal_code=refusal_code,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        _read()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RefusalCode.INVALID_FRAME.value


def test_pull_preserves_the_existing_payload_and_text_presentation(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection()
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.UPDATED,
    )
    read = bridge.NotificationsCaptureRead(completion=completion, projection=projection)
    monkeypatch.setattr(handler, "active_bucket_id_or_refuse", lambda: str(_PROFILE))
    monkeypatch.setattr(handler, "emit_live_auth_preflight", lambda *_args, **_kwargs: None)
    calls: list[tuple[typer.Context, UUID]] = []

    def capture(ctx: typer.Context, *, profile_id: UUID) -> bridge.NotificationsCaptureRead:
        calls.append((ctx, profile_id))
        return read

    monkeypatch.setattr(handler, "read_notifications_capture_for_cli", capture)
    envelopes: list[dict[str, object]] = []
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))
    ctx = cast(typer.Context, cast(object, None))

    handler.notifications_pull(ctx)

    assert calls == [(ctx, _PROFILE)]
    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "app.live.notifications.pull"
    result = cast(NotificationsCaptureResult, envelope["result"])
    assert result == NotificationsCaptureResult(
        bucket_id=str(_PROFILE),
        snapshot_id="2" * 64,
        captured_at=_CAPTURED_AT,
        persisted_at=_PERSISTED_AT,
        row_count=3,
        source_url=_SOURCE_URL,
    )
    assert envelope["lines"] == [
        f"bucket\t{_PROFILE}",
        f"snapshot_id\t{'2' * 64}",
        f"captured_at\t{_CAPTURED_AT.isoformat()}",
        "row_count\t3",
        f"source_url\t{_SOURCE_URL}",
    ]
