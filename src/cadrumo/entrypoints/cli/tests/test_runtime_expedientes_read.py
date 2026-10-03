"""Registered expedientes reads preserve profile scope and CLI presentation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....application.live.expedientes_read_operation import (
    EXPEDIENTES_LATEST_DEFINITION_ID,
    EXPEDIENTES_LIST_DEFINITION_ID,
    EXPEDIENTES_SHOW_DEFINITION_ID,
    ExpedienteDeclarationPublicV1,
    ExpedientesLatestPublicResultV1,
    ExpedientesLatestRequest,
    ExpedientesListPublicResultV1,
    ExpedientesListRequest,
    ExpedientesShowPublicResultV1,
    ExpedientesShowRequest,
    ExpedientesSnapshotSummaryPublicV1,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import _app_live_expedientes_cli as handler
from .. import runtime_expedientes_read as bridge
from .._app_live_expedientes_payloads import (
    ExpedientesLatestResult,
    ExpedientesListResult,
    ExpedientesViewResult,
)
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_FOREIGN_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_CAPTURED_AT = datetime(2025, 3, 6, 7, 8, tzinfo=UTC)
_SOURCE_URL = "https://sede.example/expedientes"
_SNAPSHOT_ID = "2" * 64
_EXPEDIENTE_ID = "20250000000000001A"


def _summary(snapshot_id: str = _SNAPSHOT_ID) -> ExpedientesSnapshotSummaryPublicV1:
    return ExpedientesSnapshotSummaryPublicV1(
        snapshot_id=snapshot_id,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE_URL,
        declaration_count=2,
    )


def _declaration(*, expediente_id: str = _EXPEDIENTE_ID, period: str = "1T") -> ExpedienteDeclarationPublicV1:
    return ExpedienteDeclarationPublicV1(
        modelo="303",
        ejercicio=2025,
        period=period,
        expediente_id=expediente_id,
        estado="ALTA",
        tipo_solicitud="Original",
        observaciones="Synthetic declaration",
        presented_at=_CAPTURED_AT,
        justificante_link_text="Justificante",
        archive_link_text="CSV",
        declaration_copy_link_text="Copia declaración",
        justificante_cell_index=7,
        archive_cell_index=8,
        declaration_copy_cell_index=9,
        mode="read",
    )


def _list_projection() -> ExpedientesListPublicResultV1:
    return ExpedientesListPublicResultV1(
        bucket_id=str(_PROFILE),
        count=1,
        rows=(_summary(),),
    )


def _show_projection(*, snapshot_id: str = _SNAPSHOT_ID) -> ExpedientesShowPublicResultV1:
    return ExpedientesShowPublicResultV1(
        bucket_id=str(_PROFILE),
        snapshot_id=snapshot_id,
        captured_at=_CAPTURED_AT,
        source_url=_SOURCE_URL,
        declaration_count=2,
        declarations=(
            _declaration(),
            _declaration(expediente_id="20250000000000002B", period="2T"),
        ),
    )


def _latest_projection(*, snapshot_id: str | None = _SNAPSHOT_ID) -> ExpedientesLatestPublicResultV1:
    return ExpedientesLatestPublicResultV1(
        bucket_id=str(_PROFILE),
        snapshot_id=snapshot_id,
        captured_at=_CAPTURED_AT if snapshot_id is not None else None,
        source_url=_SOURCE_URL if snapshot_id is not None else None,
        declaration_count=2 if snapshot_id is not None else None,
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projections: Mapping[str, BaseModel],
    *,
    effect: OperationEffect = OperationEffect.NONE,
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[BaseModel, dict[str, object]]], list[UUID]]:
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    bound_profiles: list[UUID] = []
    client = object()

    def require_client(_ctx: object, *, expected_profile_id: UUID) -> object:
        bound_profiles.append(expected_profile_id)
        return client

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
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

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted, bound_profiles


def _context() -> typer.Context:
    return cast(typer.Context, cast(object, None))


def _completion[ResultT: BaseModel](projection: ResultT) -> RegisteredOperationCompletion[ResultT]:
    return RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )


def test_list_show_latest_submit_exact_profile_and_validate_public_results(monkeypatch: pytest.MonkeyPatch) -> None:
    projections = {
        EXPEDIENTES_LIST_DEFINITION_ID: _list_projection(),
        EXPEDIENTES_SHOW_DEFINITION_ID: _show_projection(),
        EXPEDIENTES_LATEST_DEFINITION_ID: _latest_projection(),
    }
    submitted, bound_profiles = _bind(monkeypatch, projections)

    listed = bridge.read_expedientes_list_for_cli(_context())
    shown = bridge.read_expedientes_show_for_cli(_context(), snapshot_id="22")
    latest = bridge.read_expedientes_latest_for_cli(_context())

    assert bound_profiles == [_PROFILE, _PROFILE, _PROFILE]
    assert (
        listed.completion.operation_id
        == shown.completion.operation_id
        == latest.completion.operation_id
        == _OPERATION_ID
    )
    assert [request for request, _ in submitted] == [
        ExpedientesListRequest(profile_id=_PROFILE),
        ExpedientesShowRequest(profile_id=_PROFILE, snapshot_id="22"),
        ExpedientesLatestRequest(profile_id=_PROFILE),
    ]
    for (_request, options), definition_id, result_type in zip(
        submitted,
        (EXPEDIENTES_LIST_DEFINITION_ID, EXPEDIENTES_SHOW_DEFINITION_ID, EXPEDIENTES_LATEST_DEFINITION_ID),
        (ExpedientesListPublicResultV1, ExpedientesShowPublicResultV1, ExpedientesLatestPublicResultV1),
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
    ("definition_id", "read_name", "update", "snapshot_prefix"),
    [
        (EXPEDIENTES_LIST_DEFINITION_ID, "list", {"bucket_id": str(_FOREIGN_PROFILE)}, None),
        (EXPEDIENTES_LIST_DEFINITION_ID, "list", {"count": 0}, None),
        (EXPEDIENTES_SHOW_DEFINITION_ID, "show", {"bucket_id": str(_FOREIGN_PROFILE)}, "22"),
        (EXPEDIENTES_SHOW_DEFINITION_ID, "show", {"snapshot_id": "3" * 64}, "22"),
        (EXPEDIENTES_SHOW_DEFINITION_ID, "show", {"declaration_count": 0}, "22"),
        (
            EXPEDIENTES_LATEST_DEFINITION_ID,
            "latest",
            {"captured_at": None},
            None,
        ),
    ],
)
def test_scope_or_shape_mismatch_is_a_correlated_invalid_frame(
    monkeypatch: pytest.MonkeyPatch,
    definition_id: str,
    read_name: str,
    update: dict[str, object],
    snapshot_prefix: str | None,
) -> None:
    projections: dict[str, BaseModel] = {
        EXPEDIENTES_LIST_DEFINITION_ID: _list_projection(),
        EXPEDIENTES_SHOW_DEFINITION_ID: _show_projection(),
        EXPEDIENTES_LATEST_DEFINITION_ID: _latest_projection(),
    }
    projections[definition_id] = projections[definition_id].model_copy(update=update)
    _bind(monkeypatch, projections)

    with pytest.raises(CliRefusedBoundaryError) as error:
        if read_name == "list":
            bridge.read_expedientes_list_for_cli(_context())
        elif read_name == "show":
            bridge.read_expedientes_show_for_cli(_context(), snapshot_id=cast(str, snapshot_prefix))
        else:
            bridge.read_expedientes_latest_for_cli(_context())

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_non_read_effect_is_a_correlated_invalid_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    _bind(
        monkeypatch,
        {EXPEDIENTES_LIST_DEFINITION_ID: _list_projection()},
        effect=OperationEffect.UPDATED,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        bridge.read_expedientes_list_for_cli(_context())

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_handlers_keep_json_and_text_fields_including_full_declaration_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listed_projection = _list_projection()
    shown_projection = _show_projection()
    latest_projection = _latest_projection()
    monkeypatch.setattr(
        handler,
        "read_expedientes_list_for_cli",
        lambda _ctx: bridge.ExpedientesListRead(_completion(listed_projection), listed_projection),
    )
    monkeypatch.setattr(
        handler,
        "read_expedientes_show_for_cli",
        lambda _ctx, *, snapshot_id: bridge.ExpedientesShowRead(_completion(shown_projection), shown_projection),
    )
    monkeypatch.setattr(
        handler,
        "read_expedientes_latest_for_cli",
        lambda _ctx: bridge.ExpedientesLatestRead(_completion(latest_projection), latest_projection),
    )
    emitted: dict[str, tuple[BaseModel, list[str]]] = {}

    def emit(_ctx: typer.Context, *, command: str, result: BaseModel, lines: list[str]) -> None:
        emitted[command] = (result, lines)

    monkeypatch.setattr(handler, "emit_envelope", emit)

    handler.expedientes_list(_context())
    handler.expedientes_show(_context(), snapshot_id="22")
    handler.expedientes_latest(_context())

    listed, list_lines = emitted["app.live.expedientes.list"]
    assert isinstance(listed, ExpedientesListResult)
    assert listed.model_dump(mode="json") == {
        "bucket_id": str(_PROFILE),
        "count": 1,
        "rows": [
            {
                "snapshot_id": _SNAPSHOT_ID,
                "captured_at": _CAPTURED_AT.isoformat(),
                "source_url": _SOURCE_URL,
                "declaration_count": 2,
            }
        ],
    }
    assert list_lines == [
        f"bucket\t{_PROFILE}",
        "count\t1",
        f"{_SNAPSHOT_ID}\t{_CAPTURED_AT.isoformat()}\tdeclarations=2",
    ]

    shown, show_lines = emitted["app.live.expedientes.view"]
    assert isinstance(shown, ExpedientesViewResult)
    assert shown.declaration_count == 2
    assert [row.model_dump(mode="json") for row in shown.declarations] == [
        {
            "modelo": "303",
            "ejercicio": 2025,
            "period": "1T",
            "expediente_id": _EXPEDIENTE_ID,
            "estado": "ALTA",
            "tipo_solicitud": "Original",
            "observaciones": "Synthetic declaration",
            "presented_at": _CAPTURED_AT.isoformat(),
            "justificante_link_text": "Justificante",
            "archive_link_text": "CSV",
            "declaration_copy_link_text": "Copia declaración",
            "justificante_cell_index": 7,
            "archive_cell_index": 8,
            "declaration_copy_cell_index": 9,
            "mode": "read",
        },
        {
            "modelo": "303",
            "ejercicio": 2025,
            "period": "2T",
            "expediente_id": "20250000000000002B",
            "estado": "ALTA",
            "tipo_solicitud": "Original",
            "observaciones": "Synthetic declaration",
            "presented_at": _CAPTURED_AT.isoformat(),
            "justificante_link_text": "Justificante",
            "archive_link_text": "CSV",
            "declaration_copy_link_text": "Copia declaración",
            "justificante_cell_index": 7,
            "archive_cell_index": 8,
            "declaration_copy_cell_index": 9,
            "mode": "read",
        },
    ]
    assert show_lines == [
        f"bucket\t{_PROFILE}",
        f"snapshot_id\t{_SNAPSHOT_ID}",
        f"captured_at\t{_CAPTURED_AT.isoformat()}",
        f"source_url\t{_SOURCE_URL}",
        "declaration_count\t2",
        f"{_EXPEDIENTE_ID}\t303\t2025\t2025 1T\tALTA\t{_CAPTURED_AT.isoformat()}",
        f"20250000000000002B\t303\t2025\t2025 2T\tALTA\t{_CAPTURED_AT.isoformat()}",
    ]

    latest, latest_lines = emitted["app.live.expedientes.latest"]
    assert isinstance(latest, ExpedientesLatestResult)
    assert latest.model_dump(mode="json") == {
        "bucket_id": str(_PROFILE),
        "snapshot_id": _SNAPSHOT_ID,
        "captured_at": _CAPTURED_AT.isoformat(),
        "source_url": _SOURCE_URL,
        "declaration_count": 2,
    }
    assert latest_lines == [
        f"bucket\t{_PROFILE}",
        f"snapshot_id\t{_SNAPSHOT_ID}",
        f"captured_at\t{_CAPTURED_AT.isoformat()}",
        "declaration_count\t2",
    ]


def test_empty_latest_keeps_the_existing_json_shape_and_dash_text(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _latest_projection(snapshot_id=None)
    read = bridge.ExpedientesLatestRead(_completion(projection), projection)
    monkeypatch.setattr(handler, "read_expedientes_latest_for_cli", lambda _ctx: read)
    emitted: list[tuple[BaseModel, list[str]]] = []
    monkeypatch.setattr(
        handler,
        "emit_envelope",
        lambda _ctx, *, result, lines, **_kwargs: emitted.append((result, lines)),
    )

    handler.expedientes_latest(_context())

    result, lines = emitted[0]
    assert isinstance(result, ExpedientesLatestResult)
    assert result.model_dump(mode="json") == {
        "bucket_id": str(_PROFILE),
        "snapshot_id": None,
        "captured_at": None,
        "source_url": None,
        "declaration_count": None,
    }
    assert lines == [f"bucket\t{_PROFILE}", "snapshot_id\t-"]
