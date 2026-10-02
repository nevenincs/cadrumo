"""Bulk filed-pull submits one exact-profile registered capture."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.live.filed_bulk_capture_operation import (
    FILED_BULK_CAPTURE_DEFINITION_ID,
    FiledBulkCapturePublicResultV1,
    FiledBulkCaptureRequest,
    FiledBulkFailureV1,
    FiledBulkSkippedCasillaV1,
)
from ....application.live.filed_single_capture_operation import (
    FiledCaptureNoticeV1,
    FiledReconciliationNoticeV1,
    FiledReconciliationV1,
)
from ....application.live.remote_state_models import FiledCapturePairOutcome
from ....application.modelo.filing_chain_reconciliation import FilingReconciliationOutcome
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.json_contract import Notice, NoticeSeverity
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from .. import _app_live as handler
from .. import runtime_filed_bulk as bridge
from .._app_live_filed_payloads import FiledCaptureResult
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "c" * 64
_OUTPUT_ROOT = Path("filed")
_SYNC_RUN_REF = "sync-run:filed_declarations:" + ("d" * 64)


def _capture_notice(code: str, *, message: str) -> FiledCaptureNoticeV1:
    return FiledCaptureNoticeV1(
        severity=NoticeSeverity.WARNING,
        code=code,
        message=message,
        context=(("reason", "capture"),),
    )


def _pair(
    modelo: str,
    year: int,
    *,
    rows: int = 0,
    reached: int = 0,
    captured: int = 0,
    attempted: bool = True,
    completed: bool = True,
) -> FiledCapturePairOutcome:
    return FiledCapturePairOutcome(
        modelo=modelo,
        year=year,
        walk_attempted=attempted,
        walk_completed=completed,
        row_count=rows,
        reached_count=reached,
        captured_count=captured,
    )


def _projection(*, dry_run: bool = False) -> FiledBulkCapturePublicResultV1:
    persisted = not dry_run
    reconciliation_rows = (
        ()
        if dry_run
        else (
            FiledReconciliationV1(
                outcome=FilingReconciliationOutcome.CONFIRMED.value,
                bucket_id=str(_PROFILE),
                modelo="303",
                filing_year=2025,
                period="1T",
                member_nif="X1234567A",
                filing_record_id="record-1",
                affected_filing_record_ids=("record-2",),
                differing_casilla_ids=("casilla.a",),
                evidence_basis="casillas",
                notices=(
                    FiledReconciliationNoticeV1(
                        code="receipt_totals_only",
                        context=(("reason", "receipt"),),
                    ),
                ),
            ),
        )
    )
    return FiledBulkCapturePublicResultV1(
        output_root=str(_OUTPUT_ROOT),
        modelos=("303", "390"),
        year_from=2023,
        year_to=2025,
        dry_run=dry_run,
        captured_count=1 if persisted else 0,
        reached_count=3,
        pair_outcomes=(
            _pair("303", 2025, rows=2, reached=2, captured=1 if persisted else 0),
            _pair("303", 2024),
            _pair("303", 2023),
            _pair("390", 2025),
            _pair("390", 2024, rows=1, reached=1),
            _pair("390", 2023, attempted=False, completed=False),
        ),
        failed_count=1,
        sync_run_ref=_SYNC_RUN_REF if persisted else None,
        observation_paths=("encrypted-observation",) if persisted else (),
        artefact_refs=("sha256:1234",) if persisted else (),
        justificante_metadata_count=1 if persisted else 0,
        justificante_csvs=("csv-1",) if persisted else (),
        filing_evidence_stamped_count=1 if persisted else 0,
        filing_record_ids=("record-1",) if persisted else (),
        filing_evidence_conflict_count=0,
        filing_evidence_conflict_record_ids=(),
        casilla_count=2 if persisted else 0,
        calculation_observation_count=1 if persisted else 0,
        calculation_observation_keys=("observation-1",) if persisted else (),
        evidence_notices=(_capture_notice("live.filed.evidence_test", message="Evidence advisory"),),
        reconciliations=reconciliation_rows,
        failures=(
            FiledBulkFailureV1(
                modelo="390",
                year=2024,
                period="4T",
                expediente_id="20240000000000001X",
                error_type="RegisterReadError",
                message="Declaration could not be read",
            ),
        ),
        skipped_casillas=(
            FiledBulkSkippedCasillaV1(
                modelo="303",
                year=2025,
                period="1T",
                expediente_id="20250000000000001A",
                casilla_id="casilla.address",
                label="Taxpayer address",
                value_kind="text",
                reason="non_numeric",
            ),
        )
        if persisted
        else (),
        recapture_notices=(_capture_notice("live.filed.recapture_test", message="Recapture changed values"),),
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: FiledBulkCapturePublicResultV1,
    *,
    effect: OperationEffect,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
):
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    client = SimpleNamespace(profile_id=_PROFILE)
    profile_bindings: list[UUID] = []

    def require_client(_ctx: object, *, expected_profile_id: UUID):
        profile_bindings.append(expected_profile_id)
        return client

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    submissions: list[tuple[object, FiledBulkCaptureRequest, dict[str, object]]] = []

    def submit(_client: object, request: FiledBulkCaptureRequest, **kwargs: object):
        submissions.append((client, request, kwargs))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submissions, profile_bindings


def _read(*, dry_run: bool = False) -> bridge.FiledBulkCaptureRead:
    return bridge.read_filed_bulk_capture_for_cli(
        cast(typer.Context, cast(object, None)),
        output_root=_OUTPUT_ROOT,
        year_from=2023,
        year_to=2025,
        modelos=("303", "390"),
        limit=7,
        dry_run=dry_run,
    )


def test_bulk_capture_submits_exact_profile_and_preserves_report_lanes(monkeypatch: pytest.MonkeyPatch) -> None:
    submissions, profile_bindings = _bind(
        monkeypatch,
        _projection(),
        effect=OperationEffect.UPDATED,
    )

    read = _read()

    assert read.completion.operation_id == _OPERATION_ID
    report = read.report
    assert report.dry_run is False
    assert report.sync_run_ref == _SYNC_RUN_REF
    assert report.captured_count == 1
    assert report.failed_count == 1
    assert report.failures[0].period == Period.from_year_and_code(2024, "4T")
    assert report.skipped_casillas[0].period == Period.from_year_and_code(2025, "1T")
    assert report.skipped_casillas[0].reason == "non_numeric"
    assert report.evidence_notices[0].context == {"reason": "capture"}
    assert report.recapture_notices[0].code == "live.filed.recapture_test"
    reconciliation = report.reconciliation_results[0]
    assert reconciliation.outcome is FilingReconciliationOutcome.CONFIRMED
    assert reconciliation.period == Period.from_year_and_code(2025, "1T")
    assert reconciliation.notices[0].context == {"reason": "receipt"}
    assert profile_bindings == [_PROFILE]
    assert len(submissions) == 1
    _client, request, options = submissions[0]
    assert request == FiledBulkCaptureRequest(
        profile_id=_PROFILE,
        output_root=_OUTPUT_ROOT,
        year_from=2023,
        year_to=2025,
        modelos=("303", "390"),
        limit=7,
        dry_run=False,
    )
    assert options["definition_id"] == FILED_BULK_CAPTURE_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is FiledBulkCapturePublicResultV1


def test_bulk_dry_run_keeps_preview_effect_and_recapture_advisory(monkeypatch: pytest.MonkeyPatch) -> None:
    _bind(monkeypatch, _projection(dry_run=True), effect=OperationEffect.NONE)

    read = _read(dry_run=True)

    assert read.report.dry_run is True
    assert read.report.sync_run_ref is None
    assert read.report.captured_count == 0
    assert read.report.reached_count == 3
    assert read.report.failures[0].modelo == "390"
    assert read.report.recapture_notices[0].message == "Recapture changed values"
    assert read.report.skipped_casillas == ()
    assert read.report.reconciliation_results == ()


@pytest.mark.parametrize(
    "mismatch",
    [
        "effect",
        "terminal",
        "refusal_code",
        "scope",
        "modelos",
        "dry_run",
        "failure_scope",
        "skipped_scope",
        "reconciliation_scope",
    ],
)
def test_bulk_capture_rejects_mismatched_receipt_or_scope(monkeypatch: pytest.MonkeyPatch, mismatch: str) -> None:
    projection = _projection()
    effect = OperationEffect.UPDATED
    condition = OperationTerminalCondition.SUCCEEDED
    refusal_code: str | None = None
    if mismatch == "effect":
        effect = OperationEffect.NONE
    elif mismatch == "terminal":
        condition = OperationTerminalCondition.REFUSED
    elif mismatch == "refusal_code":
        refusal_code = "unexpected_refusal"
    elif mismatch == "scope":
        projection = projection.model_copy(update={"year_to": 2024})
    elif mismatch == "modelos":
        projection = projection.model_copy(update={"modelos": ("303",)})
    elif mismatch == "dry_run":
        projection = _projection(dry_run=True)
        effect = OperationEffect.NONE
    elif mismatch == "failure_scope":
        failure = projection.failures[0].model_copy(update={"year": 2022})
        projection = projection.model_copy(update={"failures": (failure,)})
    elif mismatch == "skipped_scope":
        skipped = projection.skipped_casillas[0].model_copy(update={"modelo": "721"})
        projection = projection.model_copy(update={"skipped_casillas": (skipped,)})
    else:
        row = projection.reconciliations[0].model_copy(update={"filing_year": 2022})
        projection = projection.model_copy(update={"reconciliations": (row,)})
    _bind(monkeypatch, projection, effect=effect, condition=condition, refusal_code=refusal_code)

    with pytest.raises(CliRefusedBoundaryError) as error:
        _read()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_bulk_dry_run_accepts_session_write_effect_without_capturing_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection(dry_run=True)
    _bind(monkeypatch, projection, effect=OperationEffect.UPDATED)

    read = _read(dry_run=True)
    assert read.completion.effect is OperationEffect.UPDATED
    assert read.report.dry_run is True
    assert read.report.captured_count == 0 and read.report.observation_paths == ()
    assert all(pair.captured_count == 0 for pair in read.report.pair_outcomes)
    assert read.report.sync_run_ref is None


def test_bulk_cli_uses_runtime_bridge_and_emits_capture_accounting_and_notices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind(monkeypatch, _projection(), effect=OperationEffect.UPDATED)
    read = _read()
    bridge_calls: list[dict[str, object]] = []

    def read_bulk(_ctx: typer.Context, **kwargs: object) -> bridge.FiledBulkCaptureRead:
        bridge_calls.append(kwargs)
        return read

    monkeypatch.setattr(bridge, "read_filed_bulk_capture_for_cli", read_bulk)
    monkeypatch.setattr(handler, "resolve_optional_root", lambda *_args, **_kwargs: _OUTPUT_ROOT)
    envelopes: list[dict[str, object]] = []
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))

    handler._emit_bulk_filed_pull(
        cast(typer.Context, cast(object, None)),
        selected_modelos=("303", "390"),
        year=None,
        year_from=2023,
        year_to=2025,
        output_root=_OUTPUT_ROOT,
        limit=7,
        dry_run=False,
    )

    assert bridge_calls == [
        {
            "year_from": 2023,
            "year_to": 2025,
            "output_root": _OUTPUT_ROOT,
            "modelos": ("303", "390"),
            "limit": 7,
            "dry_run": False,
        }
    ]
    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "app.live.filed.pull"
    result = envelope["result"]
    assert isinstance(result, FiledCaptureResult)
    assert result.reached_count == 3
    assert result.pair_outcomes == list(read.report.pair_outcomes)
    assert result.pair_outcomes[-1].walk_attempted is False
    assert result.pair_outcomes[-1].walk_completed is False
    assert result.sync_run_ref == _SYNC_RUN_REF
    notices = cast("list[Notice]", envelope["notices"])
    recapture = next(notice for notice in notices if notice.code == "live.filed.recapture_test")
    skipped = next(notice for notice in notices if notice.code == "live.filed.pull.casillas_not_enrolled")
    assert recapture.message == "Recapture changed values"
    assert skipped.context == {
        "skipped_casilla_count": "1",
        "casilla_ids": "casilla.address",
        "modelos": "303",
    }
    lines = cast("tuple[str, ...]", envelope["lines"])
    assert f"notice\tlive.filed.recapture_test\t{recapture.message}" in lines
    assert skipped.message in lines


@pytest.mark.parametrize("mismatch", ["outside_scope", "duplicate", "incomplete_counts", "reached", "captured"])
def test_bulk_pair_accounting_refuses_contradictions_with_correlated_receipt(
    monkeypatch: pytest.MonkeyPatch, mismatch: str
) -> None:
    projection = _projection()
    pairs = list(projection.pair_outcomes)
    if mismatch == "outside_scope":
        pairs[0] = pairs[0].model_copy(update={"modelo": "721"})
    elif mismatch == "duplicate":
        pairs[1] = pairs[0]
    elif mismatch == "incomplete_counts":
        pairs[0] = pairs[0].model_copy(update={"walk_completed": False})
    elif mismatch == "reached":
        pairs[0] = pairs[0].model_copy(update={"reached_count": 3})
    else:
        pairs[0] = pairs[0].model_copy(update={"captured_count": 2})
    projection = projection.model_copy(update={"pair_outcomes": tuple(pairs)})
    _bind(monkeypatch, projection, effect=OperationEffect.UPDATED)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        _read()
    assert caught.value.context is not None
    assert caught.value.context["operation_id"] == _OPERATION_ID
    assert caught.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_bulk_unvisited_pair_retains_observation_and_persistence_distinctions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind(monkeypatch, _projection(), effect=OperationEffect.UPDATED)
    read = _read()
    assert read.report.pair_outcomes == _projection().pair_outcomes
    assert read.report.pair_outcomes[-1].walk_attempted is False
    assert read.report.pair_outcomes[-1].walk_completed is False
    assert read.report.reached_count == 3 and read.report.captured_count == 1


@pytest.mark.parametrize("mutation", ["captured", "observation", "sync_run"])
def test_bulk_dry_run_refuses_captured_data_despite_session_write_effect(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    projection = _projection(dry_run=True)
    if mutation == "captured":
        pairs = list(projection.pair_outcomes)
        pairs[0] = pairs[0].model_copy(update={"captured_count": 1})
        projection = projection.model_copy(update={"captured_count": 1, "pair_outcomes": tuple(pairs)})
    elif mutation == "observation":
        projection = projection.model_copy(update={"observation_paths": ("encrypted-observation",)})
    else:
        projection = projection.model_copy(update={"sync_run_ref": _SYNC_RUN_REF})
    _bind(monkeypatch, projection, effect=OperationEffect.UPDATED)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        _read(dry_run=True)
    assert caught.value.context is not None
    assert caught.value.context["operation_id"] == _OPERATION_ID
    assert caught.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
