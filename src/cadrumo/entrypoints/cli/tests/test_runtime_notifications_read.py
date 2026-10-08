"""Registered local notification reads preserve exact scope and CLI output."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....application.live.notification_ports import NotificationType
from ....application.live.notifications_read_operation import (
    NOTIFICATIONS_LATEST_DEFINITION_ID,
    NOTIFICATIONS_LIST_DEFINITION_ID,
    NOTIFICATIONS_SHOW_DEFINITION_ID,
    NotificationRowPublicV1,
    NotificationsLatestPublicResultV1,
    NotificationsLatestRequest,
    NotificationsListPublicResultV1,
    NotificationsListRequest,
    NotificationsShowPublicResultV1,
    NotificationsShowRequest,
    NotificationsSnapshotSummaryPublicV1,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import runtime_notifications_read as bridge
from .. import runtime_profile_operation as profile_operation
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_CAPTURED_AT = datetime(2025, 3, 6, 7, 8, tzinfo=UTC)
_SOURCE_URL = "https://sede.example/notifications"


def _list_projection() -> NotificationsListPublicResultV1:
    return NotificationsListPublicResultV1(
        bucket_id=str(_PROFILE),
        count=1,
        rows=(
            NotificationsSnapshotSummaryPublicV1(
                snapshot_id="2" * 64,
                captured_at=_CAPTURED_AT,
                row_count=1,
            ),
        ),
    )


def _show_projection() -> NotificationsShowPublicResultV1:
    return NotificationsShowPublicResultV1(
        bucket_id=str(_PROFILE),
        snapshot_id="2" * 64,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE_URL,
        row_count=1,
        rows=(
            NotificationRowPublicV1(
                certificado_id="1234567890",
                tipo=NotificationType.NOTIFICACION,
                concepto="Synthetic notification",
                titular_nif="X1234567L",
                titular_nombre="Synthetic taxpayer",
                destinatario_nif="X1234567L",
                destinatario_nombre="Synthetic taxpayer",
                fecha_emision=date(2025, 3, 6),
                fecha_notificacion=None,
                modo_notificacion=None,
                leida=False,
                source_url="https://sede.example/notification/1234567890",
                mode="read",
            ),
        ),
    )


def _latest_projection() -> NotificationsLatestPublicResultV1:
    return NotificationsLatestPublicResultV1(
        bucket_id=str(_PROFILE),
        snapshot_id="2" * 64,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE_URL,
        row_count=1,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projections: Mapping[str, BaseModel],
    *,
    effect: OperationEffect = OperationEffect.NONE,
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[object, dict[str, object]]], list[UUID]]:
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    bound_profiles: list[UUID] = []
    client = object()

    def require_client(_ctx: object, *, expected_profile_id: UUID) -> object:
        bound_profiles.append(expected_profile_id)
        return client

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    submitted: list[tuple[object, dict[str, object]]] = []

    def submit(submitted_client: object, request: object, **kwargs: object):
        assert submitted_client is client
        options = kwargs
        submitted.append((request, options))
        definition_id = cast(str, options["definition_id"])
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projections[definition_id],
            effect=effect,
            terminal_condition=terminal_condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(profile_operation, "run_registered_operation", submit)
    return submitted, bound_profiles


def _context() -> typer.Context:
    return cast(typer.Context, cast(object, None))


def test_list_show_latest_submit_exact_profile_and_validate_public_results(monkeypatch: pytest.MonkeyPatch) -> None:
    projections = {
        NOTIFICATIONS_LIST_DEFINITION_ID: _list_projection(),
        NOTIFICATIONS_SHOW_DEFINITION_ID: _show_projection(),
        NOTIFICATIONS_LATEST_DEFINITION_ID: _latest_projection(),
    }
    submitted, bound_profiles = _bind(monkeypatch, projections)

    listed = bridge.read_notifications_list_for_cli(_context())
    shown = bridge.read_notifications_show_for_cli(_context(), snapshot_id="22")
    latest = bridge.read_notifications_latest_for_cli(_context())

    assert bound_profiles == [_PROFILE, _PROFILE, _PROFILE]
    assert (
        listed.completion.operation_id
        == shown.completion.operation_id
        == latest.completion.operation_id
        == _OPERATION_ID
    )
    assert [request for request, _ in submitted] == [
        NotificationsListRequest(profile_id=_PROFILE),
        NotificationsShowRequest(profile_id=_PROFILE, snapshot_id="22"),
        NotificationsLatestRequest(profile_id=_PROFILE),
    ]
    for (_request, options), definition_id, result_type in zip(
        submitted,
        (
            NOTIFICATIONS_LIST_DEFINITION_ID,
            NOTIFICATIONS_SHOW_DEFINITION_ID,
            NOTIFICATIONS_LATEST_DEFINITION_ID,
        ),
        (
            NotificationsListPublicResultV1,
            NotificationsShowPublicResultV1,
            NotificationsLatestPublicResultV1,
        ),
        strict=True,
    ):
        assert options["definition_id"] == definition_id
        assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert options["result_type"] is result_type
        assert options["request_version"] == options["result_version"] == 1

    assert listed.projection == _list_projection()
    assert shown.projection == _show_projection()
    assert latest.projection == _latest_projection()


@pytest.mark.parametrize(
    ("definition_id", "projection_name", "update", "snapshot_prefix", "effect", "condition", "refusal"),
    [
        (
            NOTIFICATIONS_LIST_DEFINITION_ID,
            "list",
            {"bucket_id": "foreign"},
            None,
            OperationEffect.NONE,
            OperationTerminalCondition.SUCCEEDED,
            None,
        ),
        (
            NOTIFICATIONS_LIST_DEFINITION_ID,
            "list",
            {"count": 0},
            None,
            OperationEffect.NONE,
            OperationTerminalCondition.SUCCEEDED,
            None,
        ),
        (
            NOTIFICATIONS_SHOW_DEFINITION_ID,
            "show",
            {"bucket_id": "foreign"},
            "22",
            OperationEffect.NONE,
            OperationTerminalCondition.SUCCEEDED,
            None,
        ),
        (
            NOTIFICATIONS_SHOW_DEFINITION_ID,
            "show",
            {"snapshot_id": "3" * 64},
            "22",
            OperationEffect.NONE,
            OperationTerminalCondition.SUCCEEDED,
            None,
        ),
        (
            NOTIFICATIONS_SHOW_DEFINITION_ID,
            "show",
            {"row_count": 0},
            "22",
            OperationEffect.NONE,
            OperationTerminalCondition.SUCCEEDED,
            None,
        ),
        (
            NOTIFICATIONS_LATEST_DEFINITION_ID,
            "latest",
            {"bucket_id": "foreign"},
            None,
            OperationEffect.NONE,
            OperationTerminalCondition.SUCCEEDED,
            None,
        ),
        (
            NOTIFICATIONS_LIST_DEFINITION_ID,
            "list",
            {},
            None,
            OperationEffect.UPDATED,
            OperationTerminalCondition.SUCCEEDED,
            None,
        ),
        (
            NOTIFICATIONS_LIST_DEFINITION_ID,
            "list",
            {},
            None,
            OperationEffect.NONE,
            OperationTerminalCondition.REFUSED,
            None,
        ),
        (
            NOTIFICATIONS_LIST_DEFINITION_ID,
            "list",
            {},
            None,
            OperationEffect.NONE,
            OperationTerminalCondition.SUCCEEDED,
            RuntimeRefusalCode.UNAVAILABLE.value,
        ),
    ],
)
def test_scope_or_receipt_mismatch_is_a_correlated_invalid_frame(
    monkeypatch: pytest.MonkeyPatch,
    definition_id: str,
    projection_name: str,
    update: dict[str, object],
    snapshot_prefix: str | None,
    effect: OperationEffect,
    condition: OperationTerminalCondition,
    refusal: str | None,
) -> None:
    projections: dict[str, BaseModel] = {
        NOTIFICATIONS_LIST_DEFINITION_ID: _list_projection(),
        NOTIFICATIONS_SHOW_DEFINITION_ID: _show_projection(),
        NOTIFICATIONS_LATEST_DEFINITION_ID: _latest_projection(),
    }
    if update:
        projection = projections[definition_id]
        projections[definition_id] = projection.model_copy(update=update)
    _bind(
        monkeypatch,
        projections,
        effect=effect,
        terminal_condition=condition,
        refusal_code=refusal,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        if projection_name == "list":
            bridge.read_notifications_list_for_cli(_context())
        elif projection_name == "show":
            bridge.read_notifications_show_for_cli(_context(), snapshot_id=cast(str, snapshot_prefix))
        else:
            bridge.read_notifications_latest_for_cli(_context())

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
