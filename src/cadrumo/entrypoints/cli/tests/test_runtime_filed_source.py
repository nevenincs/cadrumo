"""Source filed-pull submits one exact-profile registered capture."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.live.filed_single_capture_operation import (
    FiledCaptureNoticeV1,
    FiledReconciliationNoticeV1,
    FiledReconciliationV1,
)
from ....application.live.filed_source_capture_operation import (
    FILED_SOURCE_CAPTURE_DEFINITION_ID,
    FiledSourceCapturePublicResultV1,
    FiledSourceCaptureRequest,
)
from ....application.modelo.filing_chain_reconciliation import FilingReconciliationOutcome
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.json_contract import Notice, NoticeSeverity
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from .. import _app_live as handler
from .. import runtime_filed_source as bridge
from .._app_live_filed_payloads import FiledCaptureSourcesResult
from .._profile_authentication_gate import _uses_runtime_profile_client
from ..command_specs import COMMAND_GRAPH
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "b" * 64
_OUTPUT_ROOT = Path("filed")


def _projection() -> FiledSourceCapturePublicResultV1:
    return FiledSourceCapturePublicResultV1(
        output_root=str(_OUTPUT_ROOT),
        target_modelo="303",
        target_year=2025,
        target_period="1T",
        captured_count=1,
        reached_count=2,
        observation_paths=("encrypted-observation",),
        artefact_refs=("sha256:1234",),
        justificante_metadata_count=1,
        justificante_csvs=("csv-1",),
        filing_evidence_stamped_count=1,
        filing_record_ids=("record-1",),
        filing_evidence_conflict_count=0,
        filing_evidence_conflict_record_ids=(),
        casilla_count=2,
        calculation_observation_count=1,
        calculation_observation_keys=("observation-1",),
        evidence_notices=(
            FiledCaptureNoticeV1(
                severity=NoticeSeverity.WARNING,
                code="live.filed.capture_test",
                message="Receipt metadata was incomplete",
                context=(("reason", "unavailable"),),
            ),
        ),
        reconciliations=(
            FiledReconciliationV1(
                outcome=FilingReconciliationOutcome.CONFIRMED.value,
                bucket_id=str(_PROFILE),
                modelo="303",
                filing_year=2024,
                period="4T",
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
        ),
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: FiledSourceCapturePublicResultV1,
    *,
    effect: OperationEffect,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
):
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    client = SimpleNamespace(profile_id=_PROFILE)
    monkeypatch.setattr(bridge, "require_profile_client", lambda *_args, **_kwargs: client)
    submissions: list[tuple[object, FiledSourceCaptureRequest, dict[str, object]]] = []

    def submit(_client: object, request: FiledSourceCaptureRequest, **kwargs: object):
        submissions.append((client, request, kwargs))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submissions


def _read() -> bridge.FiledSourceCaptureRead:
    return bridge.read_filed_source_capture_for_cli(
        cast(typer.Context, cast(object, None)),
        modelo="303",
        year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        output_root=_OUTPUT_ROOT,
    )


def test_source_capture_submits_exact_profile_and_restores_complete_report(monkeypatch: pytest.MonkeyPatch) -> None:
    submissions = _bind(monkeypatch, _projection(), effect=OperationEffect.UPDATED)

    read = _read()

    assert read.completion.operation_id == _OPERATION_ID
    assert read.report.output_root == str(_OUTPUT_ROOT)
    assert read.report.target_modelo == "303"
    assert read.report.target_year == 2025
    assert read.report.target_period == Period.from_year_and_code(2025, "1T")
    assert read.report.reached_count == 2
    assert read.report.evidence_notices[0].context == {"reason": "unavailable"}
    reconciliation = read.report.reconciliation_results[0]
    assert reconciliation.outcome is FilingReconciliationOutcome.CONFIRMED
    assert reconciliation.period == Period.from_year_and_code(2024, "4T")
    assert reconciliation.notices[0].context == {"reason": "receipt"}
    assert len(submissions) == 1
    _client, request, options = submissions[0]
    assert request == FiledSourceCaptureRequest(
        profile_id=_PROFILE,
        output_root=_OUTPUT_ROOT,
        modelo="303",
        year=2025,
        period="1T",
    )
    assert options["definition_id"] == FILED_SOURCE_CAPTURE_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is FiledSourceCapturePublicResultV1


@pytest.mark.parametrize("mismatch", ["target", "effect", "terminal", "profile"])
def test_source_capture_mismatch_refuses_with_correlated_receipt(
    monkeypatch: pytest.MonkeyPatch, mismatch: str
) -> None:
    projection = _projection()
    effect = OperationEffect.UPDATED
    condition = OperationTerminalCondition.SUCCEEDED
    if mismatch == "target":
        projection = projection.model_copy(update={"target_year": 2024})
    elif mismatch == "effect":
        effect = OperationEffect.NONE
    elif mismatch == "terminal":
        condition = OperationTerminalCondition.REFUSED
    else:
        row = projection.reconciliations[0].model_copy(update={"bucket_id": "5aa00000-0000-4000-8000-0000000000bb"})
        projection = projection.model_copy(update={"reconciliations": (row,)})
    _bind(monkeypatch, projection, effect=effect, condition=condition)

    with pytest.raises(CliRefusedBoundaryError) as error:
        _read()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_source_capture_cli_emits_existing_metrics_reconciliations_and_notices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind(monkeypatch, _projection(), effect=OperationEffect.UPDATED)
    read = _read()
    monkeypatch.setattr(bridge, "read_filed_source_capture_for_cli", lambda *_args, **_kwargs: read)
    monkeypatch.setattr(handler, "resolve_optional_root", lambda *_args, **_kwargs: _OUTPUT_ROOT)
    envelopes: list[dict[str, object]] = []
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))

    handler.filed_pull_sources_cmd(
        cast(typer.Context, cast(object, None)),
        modelo="303",
        year=2025,
        period="1T",
        output_root=_OUTPUT_ROOT,
    )

    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "app.live.filed.pull_sources"
    result = envelope["result"]
    assert isinstance(result, FiledCaptureSourcesResult)
    assert result.target_period == Period.from_year_and_code(2025, "1T")
    assert result.captured_count == 1
    assert result.reconciliations[0].outcome is FilingReconciliationOutcome.CONFIRMED
    lines = cast("tuple[str, ...]", envelope["lines"])
    assert "reconciliation_count\t1" in lines
    assert "captured_count=1" in lines
    notices = cast("tuple[Notice, ...]", envelope["notices"])
    assert any(notice.code == "live.filed.capture_test" for notice in notices)
    assert any(notice.code == "modelo.filing_chain.receipt_totals_only" for notice in notices)


def test_source_pull_always_uses_runtime_profile_admission() -> None:
    spec = COMMAND_GRAPH.node("app_live_filed_pull_sources").spec

    assert _uses_runtime_profile_client(spec, {})
