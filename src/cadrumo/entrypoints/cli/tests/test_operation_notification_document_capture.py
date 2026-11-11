"""Registered document capture keeps its exact scope and receipt semantics."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import cast
from uuid import UUID

import pytest
import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.registered_operation_deadlines import provider_login_settlement_seconds
from cadrumo_client.contracts.contracts import RefusalCode

from ....application.live.notification_document_capture_operation import (
    NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID,
    NotificationDocumentCapturePublicResultV1,
    NotificationDocumentCaptureRequest,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import operation_notification_document_capture as bridge
from .operation_bridge_support import bind_profile_submission

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


_bind = partial(
    bind_profile_submission,
    bridge=bridge,
    operation_id=_OPERATION_ID,
)


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
                "settlement_timeout": provider_login_settlement_seconds(after_login=120),
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
    assert error.value.context["reason"] == RefusalCode.INVALID_FRAME.value


@pytest.mark.parametrize(
    ("already_in_custody", "effect", "condition", "refusal_code"),
    [
        (False, OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED, None),
        (True, OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, None),
        (False, OperationEffect.UNKNOWN, OperationTerminalCondition.SUCCEEDED, None),
        (False, OperationEffect.UPDATED, OperationTerminalCondition.REFUSED, None),
        (False, OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, RefusalCode.UNAVAILABLE.value),
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
    assert error.value.context["reason"] == RefusalCode.INVALID_FRAME.value
