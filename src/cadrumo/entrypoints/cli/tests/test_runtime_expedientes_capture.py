"""Expedientes capture pull uses the bound profile runtime and keeps its CLI shape."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....application.live.expedientes_capture_operation import (
    EXPEDIENTES_BULK_CAPTURE_DEFINITION_ID,
    EXPEDIENTES_SINGLE_CAPTURE_DEFINITION_ID,
    ExpedientesBulkCapturePublicResultV1,
    ExpedientesBulkCaptureRequest,
    ExpedientesSingleCapturePublicResultV1,
    ExpedientesSingleCaptureRequest,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import _app_live_expedientes_cli as handler
from .. import runtime_expedientes_capture as bridge
from .._app_live_expedientes_payloads import ExpedientesCaptureResult
from .._profile_authentication_gate import _uses_runtime_profile_client
from ..command_specs import COMMAND_GRAPH
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion
from ..registered_operation_deadlines import provider_login_settlement_seconds

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_FOREIGN_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_CAPTURED_AT = datetime(2025, 3, 6, 7, 8, tzinfo=UTC)
_PERSISTED_AT = datetime(2025, 3, 6, 7, 9, tzinfo=UTC)
_SOURCE_URL = "declarations:modelo=303:ejercicio=2025"


def _single_projection(**updates: object) -> ExpedientesSingleCapturePublicResultV1:
    projection = ExpedientesSingleCapturePublicResultV1(
        bucket_id=str(_PROFILE),
        snapshot_id="2" * 64,
        captured_at=_CAPTURED_AT,
        persisted_at=_PERSISTED_AT,
        declaration_count=3,
        source_url=_SOURCE_URL,
    )
    return projection.model_copy(update=updates)


def _bulk_projection(**updates: object) -> ExpedientesBulkCapturePublicResultV1:
    projection = ExpedientesBulkCapturePublicResultV1(
        bucket_id=str(_PROFILE),
        modelos=("303", "390"),
        year_from=2024,
        year_to=2025,
        captured_snapshot_count=1,
        declaration_count=4,
        snapshot_ids=("3" * 64,),
        failed_count=1,
        failures=(
            {
                "modelo": "390",
                "year": 2024,
                "error_type": "TimeoutError",
                "message": "Register walk timed out",
            },
        ),
    )
    return projection.model_copy(update=updates)


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: BaseModel,
    *,
    effect: OperationEffect = OperationEffect.UPDATED,
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
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
            terminal_condition=terminal_condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted, bound_profiles


def _context() -> typer.Context:
    return cast(typer.Context, cast(object, None))


def test_single_and_bulk_submit_the_exact_profile_and_operation_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    single_projection = _single_projection()
    submitted_single, bound_single = _bind(monkeypatch, single_projection, effect=OperationEffect.NONE)
    single = bridge.read_expedientes_single_capture_for_cli(_context(), profile_id=_PROFILE, modelo="303", year=2025)

    bulk_projection = _bulk_projection()
    submitted_bulk, bound_bulk = _bind(monkeypatch, bulk_projection)
    bulk = bridge.read_expedientes_bulk_capture_for_cli(
        _context(), profile_id=_PROFILE, modelos=("303", "390"), year_from=2024, year_to=2025
    )

    assert bound_single == bound_bulk == [_PROFILE]
    assert single.projection is single_projection
    assert bulk.projection is bulk_projection
    assert submitted_single == [
        (
            ExpedientesSingleCaptureRequest(profile_id=_PROFILE, modelo="303", year=2025),
            {
                "definition_id": EXPEDIENTES_SINGLE_CAPTURE_DEFINITION_ID,
                "subject_ref": profile_operation_subject(str(_PROFILE)),
                "result_type": ExpedientesSingleCapturePublicResultV1,
                "request_version": 1,
                "result_version": 1,
                "timeout": 120,
                "settlement_timeout": provider_login_settlement_seconds(after_login=120),
            },
        )
    ]
    assert submitted_bulk == [
        (
            ExpedientesBulkCaptureRequest(profile_id=_PROFILE, modelos=("303", "390"), year_from=2024, year_to=2025),
            {
                "definition_id": EXPEDIENTES_BULK_CAPTURE_DEFINITION_ID,
                "subject_ref": profile_operation_subject(str(_PROFILE)),
                "result_type": ExpedientesBulkCapturePublicResultV1,
                "request_version": 1,
                "result_version": 1,
                "timeout": 120,
                "settlement_timeout": provider_login_settlement_seconds(after_login=120),
            },
        )
    ]


@pytest.mark.parametrize(
    ("is_bulk", "projection", "effect", "terminal_condition", "refusal_code"),
    [
        (
            False,
            _single_projection(bucket_id=str(_FOREIGN_PROFILE)),
            OperationEffect.UPDATED,
            OperationTerminalCondition.SUCCEEDED,
            None,
        ),
        (
            False,
            _single_projection(source_url="declarations:modelo=390:ejercicio=2024"),
            OperationEffect.UPDATED,
            OperationTerminalCondition.SUCCEEDED,
            None,
        ),
        (False, _single_projection(), OperationEffect.UNKNOWN, OperationTerminalCondition.SUCCEEDED, None),
        (True, _bulk_projection(year_to=2026), OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, None),
        (True, _bulk_projection(failed_count=0), OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, None),
        (True, _bulk_projection(), OperationEffect.UPDATED, OperationTerminalCondition.REFUSED, None),
        (
            True,
            _bulk_projection(),
            OperationEffect.UPDATED,
            OperationTerminalCondition.SUCCEEDED,
            RuntimeRefusalCode.UNAVAILABLE.value,
        ),
    ],
)
def test_invalid_scope_or_receipt_is_correlated_to_the_submitted_operation(
    monkeypatch: pytest.MonkeyPatch,
    is_bulk: bool,
    projection: BaseModel,
    effect: OperationEffect,
    terminal_condition: OperationTerminalCondition,
    refusal_code: str | None,
) -> None:
    _bind(
        monkeypatch,
        projection,
        effect=effect,
        terminal_condition=terminal_condition,
        refusal_code=refusal_code,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        if is_bulk:
            bridge.read_expedientes_bulk_capture_for_cli(
                _context(), profile_id=_PROFILE, modelos=("303", "390"), year_from=2024, year_to=2025
            )
        else:
            bridge.read_expedientes_single_capture_for_cli(_context(), profile_id=_PROFILE, modelo="303", year=2025)

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_pull_keeps_single_and_bulk_cli_payloads_and_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(handler, "active_bucket_id_or_refuse", lambda: str(_PROFILE))
    monkeypatch.setattr(handler, "emit_live_auth_preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(handler, "resolve_pull_year_range", lambda **_kwargs: (2024, 2025))
    single_projection = _single_projection()
    single_read = bridge.ExpedientesSingleCaptureRead(
        completion=RegisteredOperationCompletion(
            operation_id=_OPERATION_ID, projection=single_projection, effect=OperationEffect.UPDATED
        ),
        projection=single_projection,
    )
    bulk_projection = _bulk_projection()
    bulk_read = bridge.ExpedientesBulkCaptureRead(
        completion=RegisteredOperationCompletion(
            operation_id=_OPERATION_ID, projection=bulk_projection, effect=OperationEffect.UPDATED
        ),
        projection=bulk_projection,
    )
    calls: list[tuple[str, dict[str, object]]] = []

    def single(_ctx: typer.Context, **kwargs: object) -> bridge.ExpedientesSingleCaptureRead:
        calls.append(("single", kwargs))
        return single_read

    def bulk(_ctx: typer.Context, **kwargs: object) -> bridge.ExpedientesBulkCaptureRead:
        calls.append(("bulk", kwargs))
        return bulk_read

    monkeypatch.setattr(handler, "read_expedientes_single_capture_for_cli", single)
    monkeypatch.setattr(handler, "read_expedientes_bulk_capture_for_cli", bulk)
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: emitted.append(kwargs))
    ctx = _context()

    handler.expedientes_pull(ctx, modelos=["303"], year=2025)
    handler.expedientes_pull(ctx, modelos=["303", "390"], year_from=2024, year_to=2025)
    handler.expedientes_pull(ctx)

    assert calls == [
        ("single", {"profile_id": _PROFILE, "modelo": "303", "year": 2025}),
        ("bulk", {"profile_id": _PROFILE, "year_from": 2024, "year_to": 2025, "modelos": ("303", "390")}),
        ("bulk", {"profile_id": _PROFILE, "year_from": 2024, "year_to": 2025, "modelos": None}),
    ]
    single_result = cast(ExpedientesCaptureResult, emitted[0]["result"])
    assert single_result.model_dump(mode="json") == {
        "mode": "single",
        "bucket_id": str(_PROFILE),
        "snapshot_id": "2" * 64,
        "captured_at": _CAPTURED_AT.isoformat(),
        "persisted_at": _PERSISTED_AT.isoformat(),
        "declaration_count": 3,
        "source_url": _SOURCE_URL,
        "modelos": [],
        "year_from": None,
        "year_to": None,
        "captured_snapshot_count": 0,
        "snapshot_ids": [],
        "failed_count": 0,
        "failures": [],
    }
    assert emitted[0]["lines"] == [
        f"bucket\t{_PROFILE}",
        f"snapshot_id\t{'2' * 64}",
        f"captured_at\t{_CAPTURED_AT.isoformat()}",
        "declaration_count\t3",
        f"source_url\t{_SOURCE_URL}",
    ]
    bulk_result = cast(ExpedientesCaptureResult, emitted[1]["result"])
    assert bulk_result.mode == "bulk"
    assert bulk_result.modelos == ["303", "390"]
    assert bulk_result.failed_count == 1
    assert bulk_result.failures[0].modelo == "390"
    assert emitted[1]["lines"] == [
        f"bucket\t{_PROFILE}",
        "modelo_count=2",
        "year_from=2024",
        "year_to=2025",
        "captured_snapshot_count=1",
        "declaration_count=4",
        "failed_count=1",
        f"snapshot_ids={'3' * 64}",
        "failure=390\t2024\tTimeoutError\tRegister walk timed out",
    ]


def test_pull_uses_runtime_profile_authentication_admission() -> None:
    spec = COMMAND_GRAPH.node("app_live_expedientes_pull").spec

    assert _uses_runtime_profile_client(spec, {})
