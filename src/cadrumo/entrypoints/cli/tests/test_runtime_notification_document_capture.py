"""Registered document capture keeps its exact scope and receipt semantics."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....application.live.notification_document_capture_operation import (
    NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID,
    NotificationDocumentCapturePublicResultV1,
    NotificationDocumentCaptureRequest,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import runtime_notification_document_capture as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_CERT = "2699101808461"
_CERT2 = "2699101808462"
_FETCHED_AT = datetime(2025, 3, 6, 7, 8, tzinfo=UTC)
_DETAIL_URL = f"https://sede.example/notification?ncc={_CERT}"
_DIGEST = "d" * 64


def _projection(*, already_in_custody: bool = False) -> NotificationDocumentCapturePublicResultV1:
    return NotificationDocumentCapturePublicResultV1(
        bucket_id=str(_PROFILE),
        certificado_id=_CERT,
        attachment_id=_DIGEST,
        document_sha256=_DIGEST,
        byte_size=123,
        source_url=_DETAIL_URL,
        fetched_at=_FETCHED_AT,
        sancion_parsed=False,
        sancion=None,
        parse_refusal="No extractable text layer",
        mode="read",
        already_in_custody=already_in_custody,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: NotificationDocumentCapturePublicResultV1,
    *,
    effect: OperationEffect,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[BaseModel, dict[str, object]]], list[UUID]]:
    bound_profiles: list[UUID] = []
    client = object()

    def require_client(_ctx: object, *, expected_profile_id: UUID) -> object:
        bound_profiles.append(expected_profile_id)
        return client

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    submitted: list[tuple[BaseModel, dict[str, object]]] = []

    def submit(submitted_client: object, request: BaseModel, **kwargs: object):
        assert submitted_client is client
        submitted.append((request, kwargs))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted, bound_profiles


def _capture() -> bridge.NotificationDocumentCapture:
    return bridge.capture_notification_document_for_cli(
        cast(typer.Context, cast(object, None)),
        profile_id=_PROFILE,
        certificado_id=_CERT,
    )


@pytest.mark.parametrize(
    ("already_in_custody", "effect"),
    [(False, OperationEffect.UPDATED), (True, OperationEffect.NONE)],
)
def test_capture_submits_exact_profile_and_certificado_and_accepts_matching_receipt(
    monkeypatch: pytest.MonkeyPatch,
    already_in_custody: bool,
    effect: OperationEffect,
) -> None:
    projection = _projection(already_in_custody=already_in_custody)
    submitted, bound_profiles = _bind(monkeypatch, projection, effect=effect)

    captured = _capture()

    assert bound_profiles == [_PROFILE]
    assert captured.completion.operation_id == _OPERATION_ID
    assert captured.projection == projection
    assert submitted == [
        (
            NotificationDocumentCaptureRequest(profile_id=_PROFILE, certificado_id=_CERT),
            {
                "definition_id": NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID,
                "subject_ref": profile_operation_subject(str(_PROFILE)),
                "result_type": NotificationDocumentCapturePublicResultV1,
                "request_version": 1,
                "result_version": 1,
                "timeout": 120,
            },
        ),
    ]


@pytest.mark.parametrize("projection_update", [{"bucket_id": "foreign"}, {"certificado_id": _CERT2}])
def test_foreign_profile_or_certificado_refuses_with_correlated_operation(
    monkeypatch: pytest.MonkeyPatch,
    projection_update: dict[str, object],
) -> None:
    projection = _projection().model_copy(update=projection_update)
    _bind(monkeypatch, projection, effect=OperationEffect.UPDATED)

    with pytest.raises(CliRefusedBoundaryError) as error:
        _capture()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


@pytest.mark.parametrize(
    ("already_in_custody", "effect", "condition", "refusal_code"),
    [
        (False, OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED, None),
        (True, OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, None),
        (False, OperationEffect.UNKNOWN, OperationTerminalCondition.SUCCEEDED, None),
        (False, OperationEffect.UPDATED, OperationTerminalCondition.REFUSED, None),
        (False, OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, RuntimeRefusalCode.UNAVAILABLE.value),
    ],
)
def test_receipt_that_disagrees_with_capture_result_refuses_with_correlated_operation(
    monkeypatch: pytest.MonkeyPatch,
    already_in_custody: bool,
    effect: OperationEffect,
    condition: OperationTerminalCondition,
    refusal_code: str | None,
) -> None:
    _bind(
        monkeypatch,
        _projection(already_in_custody=already_in_custody),
        effect=effect,
        condition=condition,
        refusal_code=refusal_code,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        _capture()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
