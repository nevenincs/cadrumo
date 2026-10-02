"""The four spreadsheet CLI routes submit correlated registered requests."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.modelo.modelo_spreadsheet_operation_contracts import (
    MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE,
    MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID,
    ModeloSpreadsheetCalculateOutcome,
    ModeloSpreadsheetCalculateProjection,
    ModeloSpreadsheetCalculateRequest,
    ModeloSpreadsheetExportOutcome,
    ModeloSpreadsheetExportProjection,
    ModeloSpreadsheetExportRequest,
    ModeloSpreadsheetProjection,
    ModeloSpreadsheetPullOutcome,
    ModeloSpreadsheetPullProjection,
    ModeloSpreadsheetPullRequest,
    ModeloSpreadsheetVerifyOutcome,
    ModeloSpreadsheetVerifyProjection,
    ModeloSpreadsheetVerifyRequest,
    SpreadsheetOutputPathRefusal,
    SpreadsheetPullMetadata,
    SpreadsheetRowIngressRefusal,
    SpreadsheetSnapshotMismatchRefusal,
)
from ....application.operations.models import OperationId
from ....application.operations.public_period import PublicPeriod
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition
from .. import runtime_modelo_spreadsheet as runtime
from ..errors import CliRecordedOperationError, CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("12345678-1234-4234-8234-123456789abc")
_PERIOD = PublicPeriod(filing_year=2025, code="1T")
_REVISION = "2025-r1"


def _ctx() -> typer.Context:
    return cast(typer.Context, SimpleNamespace())


def _install_completion(
    monkeypatch: pytest.MonkeyPatch,
    projection: BaseModel,
    effect: OperationEffect,
    *,
    terminal_condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> dict[str, object]:
    client = cast(RuntimeFrontendClient, cast(object, SimpleNamespace(profile_id=_PROFILE_ID)))
    captured: dict[str, object] = {}

    monkeypatch.setattr(runtime, "bound_profile_client", lambda _ctx: client)

    def require_client(_ctx: typer.Context, *, expected_profile_id: UUID) -> RuntimeFrontendClient:
        assert expected_profile_id == _PROFILE_ID
        return client

    def run(
        actual_client: RuntimeFrontendClient,
        request: BaseModel,
        **kwargs: object,
    ) -> RegisteredOperationCompletion[BaseModel]:
        captured.update(client=actual_client, request=request, **kwargs)
        return RegisteredOperationCompletion[BaseModel](
            operation_id=cast(OperationId, "a" * 64),
            projection=projection,
            effect=effect,
            terminal_condition=terminal_condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(runtime, "require_profile_client", require_client)
    monkeypatch.setattr(runtime, "run_registered_operation", run)
    return captured


def _base_outcome(operation: str, *, outcome: str = "succeeded") -> dict[str, Any]:
    return _base_projection() | {"operation": operation, "outcome": outcome}


def _model[ModelT: BaseModel](model_type: type[ModelT], **fields: Any) -> ModelT:
    return model_type.model_validate(fields)


def _base_projection() -> dict[str, Any]:
    return ModeloSpreadsheetProjection(
        profile_id=_PROFILE_ID,
        modelo="303",
        revision=_REVISION,
        period=_PERIOD,
    ).model_dump()


def test_export_submits_local_output_election_and_requires_updated_receipt(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "modelo-303-2025-1T.xlsx"
    result_projection = _model(
        ModeloSpreadsheetExportProjection,
        **_base_projection(),
        output_path=str(output.absolute()),
        byte_size=512,
        sha256="a" * 64,
        tab_names=("Portada", "Liquidación"),
        casilla_count=24,
        prefill_relations=True,
    )
    projection = _model(ModeloSpreadsheetExportOutcome, **_base_outcome("export"), result=result_projection)
    captured = _install_completion(monkeypatch, projection, OperationEffect.UPDATED)

    result = runtime.export_modelo_spreadsheet(
        _ctx(),
        modelo="303",
        period=_PERIOD,
        output=output,
        replace_existing=True,
        prefill_relations=True,
    )

    request = cast(ModeloSpreadsheetExportRequest, captured["request"])
    client = cast(RuntimeFrontendClient, captured["client"])
    assert client.profile_id == _PROFILE_ID
    assert request.profile_id == _PROFILE_ID
    assert request.modelo == "303" and request.period == _PERIOD
    assert request.output_path == str(output.absolute())
    assert request.replace_existing is True and request.prefill_relations is True
    assert captured["definition_id"] == MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID
    assert captured["subject_ref"] == f"profile:{_PROFILE_ID}"
    assert captured["request_version"] == captured["result_version"] == 1
    assert captured["timeout"] == 120
    assert captured["allow_refusal_detail"] is True
    assert result is result_projection


def test_pull_submits_exact_remote_handle_and_assembly_election(monkeypatch) -> None:
    metadata = SpreadsheetPullMetadata(
        modelo_id="303",
        revision_id=_REVISION,
        filing_year=2025,
        period="1T",
        engine_version="test-engine",
        registry_sha="b" * 64,
        exported_at="2025-01-01T00:00:00Z",
    )
    result_projection = _model(
        ModeloSpreadsheetPullProjection,
        **_base_projection(),
        spreadsheet_id="remote-sheet-1",
        metadata_match="matches",
        metadata=metadata,
        cells_read=0,
        operator_edits_populated=0,
        binding_edits_populated=0,
        relation_edits_populated=0,
        operator_edits_total=0,
        operator_edits=(),
        binding_edits=(),
        relation_edits=(),
        row_set_edits_populated=0,
        row_set_cells_populated=0,
        row_set_edits=(),
        assembled_groupings=(),
        assembled_observation_count=0,
    )
    projection = _model(ModeloSpreadsheetPullOutcome, **_base_outcome("pull"), result=result_projection)
    captured = _install_completion(monkeypatch, projection, OperationEffect.NONE)

    result = runtime.pull_modelo_spreadsheet(
        _ctx(),
        modelo="303",
        period=_PERIOD,
        spreadsheet_id="remote-sheet-1",
        assemble_observations=True,
    )

    request = cast(ModeloSpreadsheetPullRequest, captured["request"])
    assert request.profile_id == _PROFILE_ID
    assert request.modelo == "303" and request.period == _PERIOD
    assert request.spreadsheet_id == "remote-sheet-1"
    assert request.assemble_observations is True
    assert captured["definition_id"] == MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID
    assert captured["allow_refusal_detail"] is True
    assert result is result_projection


def test_calculate_submits_the_remote_handle_and_correlates_nonwriting_result(monkeypatch) -> None:
    result_projection = _model(
        ModeloSpreadsheetCalculateProjection,
        **_base_projection(),
        spreadsheet_id="remote-sheet-2",
        metadata_match="matches",
        cells_read=7,
        operator_edits_populated=1,
        binding_edits_populated=2,
        relation_edits_populated=0,
        computed=(),
    )
    projection = _model(ModeloSpreadsheetCalculateOutcome, **_base_outcome("calculate"), result=result_projection)
    captured = _install_completion(monkeypatch, projection, OperationEffect.NONE)

    result = runtime.calculate_modelo_spreadsheet(
        _ctx(),
        modelo="303",
        period=_PERIOD,
        spreadsheet_id="remote-sheet-2",
    )

    request = cast(ModeloSpreadsheetCalculateRequest, captured["request"])
    assert request.profile_id == _PROFILE_ID
    assert request.modelo == "303" and request.period == _PERIOD
    assert request.spreadsheet_id == "remote-sheet-2"
    assert captured["definition_id"] == MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID
    assert result is result_projection


def test_verify_submits_only_scenario_path_and_digest_and_requires_write_receipt(monkeypatch, tmp_path: Path) -> None:
    scenario = tmp_path / "scenario.json"
    scenario_bytes = b'{"scenario_label":"cli-test"}'
    scenario.write_bytes(scenario_bytes)
    result_projection = _model(
        ModeloSpreadsheetVerifyProjection,
        **_base_projection(),
        spreadsheet_id="remote-sheet-3",
        spreadsheet_url="https://sheets.example/remote-sheet-3",
        verdict="all_match",
        aeat_oracle_present=False,
        computed_count=1,
        divergence_count=0,
        divergences=(),
    )
    projection = _model(ModeloSpreadsheetVerifyOutcome, **_base_outcome("verify"), result=result_projection)
    captured = _install_completion(monkeypatch, projection, OperationEffect.UPDATED)

    result = runtime.verify_modelo_spreadsheet(
        _ctx(),
        modelo="303",
        period=_PERIOD,
        scenario_path=scenario,
    )

    request = cast(ModeloSpreadsheetVerifyRequest, captured["request"])
    assert request.profile_id == _PROFILE_ID
    assert request.modelo == "303" and request.period == _PERIOD
    assert request.scenario_path == str(scenario.absolute())
    assert request.scenario_sha256 == hashlib.sha256(scenario_bytes).hexdigest()
    assert captured["definition_id"] == MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID
    assert result is result_projection


def test_export_rejects_a_completion_with_the_wrong_effect(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "wrong-effect.xlsx"
    result_projection = _model(
        ModeloSpreadsheetExportProjection,
        **_base_projection(),
        output_path=str(output.absolute()),
        byte_size=1,
        sha256="c" * 64,
        tab_names=("Portada",),
        casilla_count=1,
        prefill_relations=False,
    )
    projection = _model(ModeloSpreadsheetExportOutcome, **_base_outcome("export"), result=result_projection)
    _install_completion(monkeypatch, projection, OperationEffect.NONE)

    with pytest.raises(CliRefusedBoundaryError) as raised:
        runtime.export_modelo_spreadsheet(
            _ctx(),
            modelo="303",
            period=_PERIOD,
            output=output,
            replace_existing=False,
            prefill_relations=False,
        )

    assert raised.value.context is not None
    assert raised.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_export_translates_only_the_correlated_closed_output_path_refusal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "existing.xlsx"
    request_path = str(output.absolute())
    refusal = SpreadsheetOutputPathRefusal(output_path=request_path, reason="existing_file")
    outcome = _model(
        ModeloSpreadsheetExportOutcome,
        **_base_outcome("export", outcome="refused"),
        refusal=refusal,
    )
    captured = _install_completion(
        monkeypatch,
        outcome,
        OperationEffect.NONE,
        terminal_condition=OperationTerminalCondition.REFUSED,
        refusal_code="REFUSED_MODELO_EXPORT_OUTPUT_PATH",
    )

    with pytest.raises(CliRecordedOperationError) as raised:
        runtime.export_modelo_spreadsheet(
            _ctx(),
            modelo="303",
            period=_PERIOD,
            output=output,
            replace_existing=False,
            prefill_relations=False,
        )

    assert captured["allow_refusal_detail"] is True
    assert raised.value.recorded_code == "REFUSED_MODELO_EXPORT_OUTPUT_PATH"
    assert raised.value.translated_message == "application.modelo.errors.export_output_path_invalid"
    assert raised.value.context == {"output_path": request_path, "reason": "path is an existing file"}


@pytest.mark.parametrize("mismatch", ["code", "effect", "path"])
def test_export_does_not_translate_an_uncorrelated_output_refusal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mismatch: str,
) -> None:
    output = tmp_path / "selected.xlsx"
    refusal_path = str(output.absolute())
    refusal_code = "REFUSED_MODELO_EXPORT_OUTPUT_PATH"
    effect = OperationEffect.NONE
    if mismatch == "code":
        refusal_code = MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE
    elif mismatch == "effect":
        effect = OperationEffect.UPDATED
    else:
        refusal_path = str((tmp_path / "another.xlsx").absolute())
    outcome = _model(
        ModeloSpreadsheetExportOutcome,
        **_base_outcome("export", outcome="refused"),
        refusal=SpreadsheetOutputPathRefusal(output_path=refusal_path, reason="existing_file"),
    )
    _install_completion(
        monkeypatch,
        outcome,
        effect,
        terminal_condition=OperationTerminalCondition.REFUSED,
        refusal_code=refusal_code,
    )

    with pytest.raises(CliRefusedBoundaryError) as raised:
        runtime.export_modelo_spreadsheet(
            _ctx(),
            modelo="303",
            period=_PERIOD,
            output=output,
            replace_existing=False,
            prefill_relations=False,
        )

    assert raised.value.context is not None
    assert raised.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_pull_translates_a_correlated_row_ingress_refusal_without_cell_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refusal = SpreadsheetRowIngressRefusal(
        reason="unknown_field",
        grouping="declared-group",
        row_index=4,
        binding_id="unknown.binding",
    )
    outcome = _model(
        ModeloSpreadsheetPullOutcome,
        **_base_outcome("pull", outcome="refused"),
        refusal=refusal,
    )
    captured = _install_completion(
        monkeypatch,
        outcome,
        OperationEffect.NONE,
        terminal_condition=OperationTerminalCondition.REFUSED,
        refusal_code=MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE,
    )

    with pytest.raises(CliRecordedOperationError) as raised:
        runtime.pull_modelo_spreadsheet(
            _ctx(),
            modelo="303",
            period=_PERIOD,
            spreadsheet_id="remote-sheet-1",
            assemble_observations=True,
        )

    assert captured["allow_refusal_detail"] is True
    assert raised.value.recorded_code == MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE
    assert raised.value.translated_message == "application.calculations.row_set.errors.row_assembly_failed"
    assert raised.value.context == {
        "row_index": 4,
        "validation_error_type": "row_set_ingress",
        "validation_error_detail": "the row contains an unknown binding",
    }


def test_pull_translates_a_correlated_snapshot_refusal_with_closed_workbook_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refusal = SpreadsheetSnapshotMismatchRefusal(
        spreadsheet_id="remote-sheet-1",
        metadata_match="stale",
        workbook_modelo="303",
        snapshot_modelo="303",
        workbook_revision="old-revision",
        snapshot_revision=_REVISION,
        workbook_engine_version="old-engine",
        expected_engine_version="current-engine",
        workbook_registry_sha="old-registry",
        snapshot_registry_sha="b" * 16,
    )
    outcome = _model(
        ModeloSpreadsheetPullOutcome,
        **_base_outcome("pull", outcome="refused"),
        refusal=refusal,
    )
    _install_completion(
        monkeypatch,
        outcome,
        OperationEffect.NONE,
        terminal_condition=OperationTerminalCondition.REFUSED,
        refusal_code="REFUSED_OUTBOUND_STORAGE_CONFLICT",
    )

    with pytest.raises(CliRecordedOperationError) as raised:
        runtime.pull_modelo_spreadsheet(
            _ctx(),
            modelo="303",
            period=_PERIOD,
            spreadsheet_id="remote-sheet-1",
            assemble_observations=False,
        )

    assert raised.value.recorded_code == "REFUSED_OUTBOUND_STORAGE_CONFLICT"
    assert raised.value.translated_message == "adapters.google.calc_sheets.errors.workbook_snapshot_mismatch"
    assert raised.value.context == {
        "spreadsheet_id": "remote-sheet-1",
        "metadata_match": "stale",
        "workbook_modelo": "303",
        "snapshot_modelo": "303",
        "workbook_revision": "old-revision",
        "snapshot_revision": _REVISION,
        "workbook_engine_version": "old-engine",
        "expected_engine_version": "current-engine",
        "workbook_registry_sha": "old-registry",
        "snapshot_registry_sha": "b" * 16,
    }
