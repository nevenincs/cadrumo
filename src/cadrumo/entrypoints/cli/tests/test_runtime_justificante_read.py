"""Registered justificante reads preserve profile scope and CLI presentation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....application.live.justificante_read_operation import (
    JUSTIFICANTE_LIST_DEFINITION_ID,
    JUSTIFICANTE_SHOW_DEFINITION_ID,
    JustificanteListPublicResultV1,
    JustificanteListRequest,
    JustificanteShowPublicResultV1,
    JustificanteShowRequest,
    JustificanteSnapshotSummaryPublicV1,
)
from ....application.live.snapshot_base import SnapshotLifecycleState
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import _app_live_justificante_cli as handler
from .. import runtime_justificante_read as bridge
from .. import runtime_profile_operation as profile_operation
from .._app_live_justificante_payloads import JustificanteListResult, JustificanteViewResult
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_FOREIGN_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_CAPTURED_AT = datetime(2026, 4, 20, 10, 30, tzinfo=UTC)
_SNAPSHOT_ID = "9" * 64
_PDF_SHA256 = "b" * 64


def _summary(snapshot_id: str = _SNAPSHOT_ID) -> JustificanteSnapshotSummaryPublicV1:
    return JustificanteSnapshotSummaryPublicV1(
        snapshot_id=snapshot_id,
        modelo="130",
        filing_year=2026,
        period="1T",
        pdf_sha256=_PDF_SHA256,
        state=SnapshotLifecycleState.ACTIVE.value,
        captured_at=_CAPTURED_AT,
    )


def _list_projection(*, bucket_id: UUID = _PROFILE) -> JustificanteListPublicResultV1:
    return JustificanteListPublicResultV1(bucket_id=str(bucket_id), count=1, rows=(_summary(),))


def _show_projection(*, bucket_id: UUID = _PROFILE, snapshot_id: str = _SNAPSHOT_ID) -> JustificanteShowPublicResultV1:
    return JustificanteShowPublicResultV1(
        bucket_id=str(bucket_id),
        snapshot_id=snapshot_id,
        modelo="130",
        filing_year=2026,
        period="1T",
        expediente_id="202613000010001A",
        csv="ABCD1234EFGH5678",
        pdf_sha256=_PDF_SHA256,
        source_kind="aeat_sede_live_capture",
        state=SnapshotLifecycleState.ACTIVE.value,
        captured_at=_CAPTURED_AT,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projections: Mapping[str, BaseModel],
    *,
    effect: OperationEffect = OperationEffect.NONE,
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[BaseModel, dict[str, object]]], list[UUID]]:
    bound_profiles: list[UUID] = []
    client = SimpleNamespace(profile_id=_PROFILE)

    def require_client(_ctx: object) -> object:
        bound_profiles.append(client.profile_id)
        return client

    monkeypatch.setattr(bridge, "bound_profile_client", require_client)
    submitted: list[tuple[BaseModel, dict[str, object]]] = []

    def submit(
        submitted_client: object, request: BaseModel, **kwargs: object
    ) -> RegisteredOperationCompletion[BaseModel]:
        assert submitted_client is client
        submitted.append((request, kwargs))
        definition_id = cast(str, kwargs["definition_id"])
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


def _completion[ResultT: BaseModel](projection: ResultT) -> RegisteredOperationCompletion[ResultT]:
    return RegisteredOperationCompletion(operation_id=_OPERATION_ID, projection=projection, effect=OperationEffect.NONE)


def test_list_and_show_submit_exact_profile_and_validate_registered_results(monkeypatch: pytest.MonkeyPatch) -> None:
    projections = {
        JUSTIFICANTE_LIST_DEFINITION_ID: _list_projection(),
        JUSTIFICANTE_SHOW_DEFINITION_ID: _show_projection(),
    }
    submitted, bound_profiles = _bind(monkeypatch, projections)

    listed = bridge.read_justificante_list_for_cli(_context())
    shown = bridge.read_justificante_show_for_cli(_context(), snapshot_id="9" * 12)

    assert bound_profiles == [_PROFILE, _PROFILE]
    assert listed.completion.operation_id == shown.completion.operation_id == _OPERATION_ID
    assert [request for request, _ in submitted] == [
        JustificanteListRequest(profile_id=_PROFILE),
        JustificanteShowRequest(profile_id=_PROFILE, snapshot_id="9" * 12),
    ]
    for (_request, options), definition_id, result_type in zip(
        submitted,
        (JUSTIFICANTE_LIST_DEFINITION_ID, JUSTIFICANTE_SHOW_DEFINITION_ID),
        (JustificanteListPublicResultV1, JustificanteShowPublicResultV1),
        strict=True,
    ):
        assert options["definition_id"] == definition_id
        assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert options["result_type"] is result_type
        assert options["request_version"] == options["result_version"] == 1

    assert listed.projection == projections[JUSTIFICANTE_LIST_DEFINITION_ID]
    assert shown.projection == projections[JUSTIFICANTE_SHOW_DEFINITION_ID]


@pytest.mark.parametrize(
    ("read_name", "projection_update", "effect"),
    [
        ("list", {"bucket_id": str(_FOREIGN_PROFILE)}, OperationEffect.NONE),
        ("show", {"bucket_id": str(_FOREIGN_PROFILE)}, OperationEffect.NONE),
        ("list", {}, OperationEffect.UPDATED),
    ],
)
def test_profile_or_receipt_mismatch_is_a_correlated_invalid_frame(
    monkeypatch: pytest.MonkeyPatch,
    read_name: str,
    projection_update: dict[str, object],
    effect: OperationEffect,
) -> None:
    projections: dict[str, BaseModel] = {
        JUSTIFICANTE_LIST_DEFINITION_ID: _list_projection(),
        JUSTIFICANTE_SHOW_DEFINITION_ID: _show_projection(),
    }
    definition_id = JUSTIFICANTE_LIST_DEFINITION_ID if read_name == "list" else JUSTIFICANTE_SHOW_DEFINITION_ID
    projections[definition_id] = projections[definition_id].model_copy(update=projection_update)
    _bind(monkeypatch, projections, effect=effect)

    with pytest.raises(CliRefusedBoundaryError) as error:
        if read_name == "list":
            bridge.read_justificante_list_for_cli(_context())
        else:
            bridge.read_justificante_show_for_cli(_context(), snapshot_id="9" * 12)

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_handlers_keep_existing_json_and_text_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    listed_projection = _list_projection()
    shown_projection = _show_projection()
    monkeypatch.setattr(
        bridge,
        "read_justificante_list_for_cli",
        lambda _ctx: bridge.JustificanteListRead(_completion(listed_projection), listed_projection),
    )
    monkeypatch.setattr(
        bridge,
        "read_justificante_show_for_cli",
        lambda _ctx, *, snapshot_id: bridge.JustificanteShowRead(_completion(shown_projection), shown_projection),
    )
    emitted: dict[str, tuple[BaseModel, list[str]]] = {}

    def emit(_ctx: typer.Context, *, command: str, result: BaseModel, lines: list[str]) -> None:
        emitted[command] = (result, lines)

    monkeypatch.setattr(handler, "emit_envelope", emit)
    handler.justificante_list(_context())
    handler.justificante_view(_context(), snapshot_id="9" * 12)

    listed, list_lines = emitted["app.live.justificante.list"]
    assert isinstance(listed, JustificanteListResult)
    assert listed.bucket_id == str(_PROFILE)
    assert listed.count == 1
    assert listed.rows[0].period == "1T"
    assert list_lines == [
        f"bucket\t{_PROFILE}",
        "count\t1",
        f"{_SNAPSHOT_ID}\t130\t2026\t1T\t{_CAPTURED_AT.isoformat()}",
    ]

    shown, show_lines = emitted["app.live.justificante.view"]
    assert isinstance(shown, JustificanteViewResult)
    assert (shown.snapshot_id, shown.modelo, shown.period, shown.csv) == (
        _SNAPSHOT_ID,
        "130",
        "1T",
        "ABCD1234EFGH5678",
    )
    assert show_lines == [
        f"bucket\t{_PROFILE}",
        f"snapshot_id\t{_SNAPSHOT_ID}",
        "modelo\t130",
        "filing_year\t2026",
        "period\t1T",
        "expediente_id\t202613000010001A",
        f"pdf_sha256\t{_PDF_SHA256}",
        "source_kind\taeat_sede_live_capture",
        "state\tactive",
        f"captured_at\t{_CAPTURED_AT.isoformat()}",
    ]
