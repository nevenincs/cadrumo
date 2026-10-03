"""Registered justificante capture keeps the submitted profile and filing pair."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....application.calculations.observations_repository import ObservationSourceKind
from ....application.live.justificante_capture_operation import (
    JUSTIFICANTE_CAPTURE_DEFINITION_ID,
    JustificanteCapturePublicResultV1,
    JustificanteCaptureRequest,
)
from ....application.live.snapshot_base import SnapshotLifecycleState
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from .. import runtime_justificante_capture as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_CAPTURED_AT = datetime(2025, 3, 6, 7, 8, tzinfo=UTC)
_SNAPSHOT_ID = "b4e2" * 16
_PDF_SHA256 = "a3f1" * 16
_FILING_RECORD_ID = "c" * 64


def _projection(**updates: object) -> JustificanteCapturePublicResultV1:
    projection = JustificanteCapturePublicResultV1(
        bucket_id=str(_PROFILE),
        snapshot_id=_SNAPSHOT_ID,
        modelo="130",
        filing_year=2025,
        period="1T",
        expediente_id="202513000000001Z",
        csv="ABCD1234EFGH",
        pdf_sha256=_PDF_SHA256,
        source_kind=ObservationSourceKind.AEAT_SEDE_LIVE_CAPTURE,
        state=SnapshotLifecycleState.ACTIVE,
        captured_at=_CAPTURED_AT,
        justificante_metadata_registered=True,
        calendar_evidence_available=True,
        modelo_filing_record_required=False,
        filing_evidence_stamped=True,
        filing_record_id=_FILING_RECORD_ID,
    )
    return projection.model_copy(update=updates)


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: JustificanteCapturePublicResultV1,
    *,
    effect: OperationEffect = OperationEffect.UPDATED,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[BaseModel, dict[str, object]]], list[UUID]]:
    bound_profiles: list[UUID] = []
    client = object()

    def require_client(_ctx: object, *, expected_profile_id: UUID) -> object:
        bound_profiles.append(expected_profile_id)
        return client

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    submissions: list[tuple[BaseModel, dict[str, object]]] = []

    def submit(submitted_client: object, request: BaseModel, **kwargs: object):
        assert submitted_client is client
        submissions.append((request, kwargs))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submissions, bound_profiles


def _capture() -> bridge.JustificanteCaptureRead:
    return bridge.capture_justificante_for_cli(
        cast(typer.Context, cast(object, None)),
        profile_id=_PROFILE,
        modelo="130",
        year=2025,
        period=Period.from_year_and_code(2025, "1T"),
    )


def test_capture_submits_exact_profile_and_filing_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection()
    submissions, bound_profiles = _bind(monkeypatch, projection)

    captured = _capture()

    assert bound_profiles == [_PROFILE]
    assert captured.completion.operation_id == _OPERATION_ID
    assert captured.projection == projection
    assert submissions == [
        (
            JustificanteCaptureRequest(
                profile_id=_PROFILE,
                modelo="130",
                year=2025,
                period="1T",
            ),
            {
                "definition_id": JUSTIFICANTE_CAPTURE_DEFINITION_ID,
                "subject_ref": profile_operation_subject(str(_PROFILE)),
                "result_type": JustificanteCapturePublicResultV1,
                "request_version": 1,
                "result_version": 1,
                "timeout": 120,
            },
        ),
    ]


@pytest.mark.parametrize(
    "projection_update",
    [
        {"bucket_id": str(_OTHER_PROFILE)},
        {"modelo": "303"},
        {"filing_year": 2024},
        {"period": "2T"},
    ],
    ids=["profile", "modelo", "year", "period"],
)
def test_capture_refuses_projection_outside_the_submitted_pair(
    monkeypatch: pytest.MonkeyPatch,
    projection_update: dict[str, object],
) -> None:
    _bind(monkeypatch, _projection(**projection_update))

    with pytest.raises(CliRefusedBoundaryError) as error:
        _capture()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


@pytest.mark.parametrize(
    ("effect", "condition", "refusal_code"),
    [
        (OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED, None),
        (OperationEffect.UNKNOWN, OperationTerminalCondition.SUCCEEDED, None),
        (OperationEffect.UPDATED, OperationTerminalCondition.REFUSED, None),
        (OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, RuntimeRefusalCode.UNAVAILABLE.value),
    ],
)
def test_capture_refuses_a_receipt_that_does_not_settle_successfully(
    monkeypatch: pytest.MonkeyPatch,
    effect: OperationEffect,
    condition: OperationTerminalCondition,
    refusal_code: str | None,
) -> None:
    _bind(
        monkeypatch,
        _projection(),
        effect=effect,
        condition=condition,
        refusal_code=refusal_code,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        _capture()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


@pytest.mark.parametrize(
    "projection_update",
    [
        {"calendar_evidence_available": False},
        {"modelo_filing_record_required": True},
        {"filing_record_id": None},
    ],
)
def test_capture_refuses_inconsistent_evidence_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    projection_update: dict[str, object],
) -> None:
    _bind(monkeypatch, _projection(**projection_update))

    with pytest.raises(CliRefusedBoundaryError) as error:
        _capture()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_capture_refuses_a_period_for_a_different_year_before_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submissions, bound_profiles = _bind(monkeypatch, _projection())

    with pytest.raises(typer.BadParameter, match="period year"):
        bridge.capture_justificante_for_cli(
            cast(typer.Context, cast(object, None)),
            profile_id=_PROFILE,
            modelo="130",
            year=2025,
            period=Period.from_year_and_code(2024, "1T"),
        )

    assert bound_profiles == []
    assert submissions == []
