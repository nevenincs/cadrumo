"""Single filed-pull CLI submits one exact-profile registered capture."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.live.filed_single_capture_operation import (
    FILED_SINGLE_CAPTURE_DEFINITION_ID,
    FiledCaptureNoticeV1,
    FiledReconciliationNoticeV1,
    FiledReconciliationV1,
    FiledSingleCapturePublicResultV1,
    FiledSingleCaptureRequest,
)
from ....application.modelo.filing_chain_reconciliation import FilingReconciliationOutcome
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.json_contract import Notice, NoticeSeverity
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from .. import _app_live as handler
from .. import runtime_filed_single as bridge
from .._app_live_filed_payloads import FiledCaptureResult
from .._filing_chain_payloads import filing_reconciliation_notices
from .._profile_authentication_gate import _uses_runtime_profile_client
from ..command_specs import COMMAND_GRAPH
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_OUTPUT_ROOT = Path("filed")


def _projection() -> FiledSingleCapturePublicResultV1:
    return FiledSingleCapturePublicResultV1(
        output_root=str(_OUTPUT_ROOT),
        modelo="303",
        year=2025,
        captured_count=1,
        reached_count=1,
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
        ),
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: FiledSingleCapturePublicResultV1,
    *,
    effect: OperationEffect,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
):
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    client = SimpleNamespace(profile_id=_PROFILE)
    monkeypatch.setattr(bridge, "require_profile_client", lambda *_args, **_kwargs: client)
    submissions: list[tuple[object, FiledSingleCaptureRequest, dict[str, object]]] = []

    def submit(_client: object, request: FiledSingleCaptureRequest, **kwargs: object):
        submissions.append((client, request, kwargs))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submissions


def _read() -> bridge.FiledSingleCaptureRead:
    return bridge.read_filed_single_capture_for_cli(
        cast(typer.Context, cast(object, None)),
        modelo="303",
        year=2025,
        output_root=_OUTPUT_ROOT,
        period=Period.from_year_and_code(2025, "1T"),
        expediente_id="exp-1",
        limit=2,
    )


def test_single_capture_submits_exact_profile_and_reconstructs_report(monkeypatch: pytest.MonkeyPatch) -> None:
    submissions = _bind(monkeypatch, _projection(), effect=OperationEffect.UPDATED)

    read = _read()

    assert read.completion.operation_id == _OPERATION_ID
    assert read.report.output_root == str(_OUTPUT_ROOT)
    assert read.report.modelo == "303"
    assert read.report.year == 2025
    assert read.report.reached_count == 1
    assert read.report.evidence_notices[0].context == {"reason": "unavailable"}
    reconciliation = read.report.reconciliation_results[0]
    assert reconciliation.outcome is FilingReconciliationOutcome.CONFIRMED
    assert reconciliation.period == Period.from_year_and_code(2025, "1T")
    assert reconciliation.notices[0].context == {"reason": "receipt"}
    assert len(submissions) == 1
    _client, request, options = submissions[0]
    assert request == FiledSingleCaptureRequest(
        profile_id=_PROFILE,
        output_root=_OUTPUT_ROOT,
        modelo="303",
        year=2025,
        period="1T",
        expediente_id="exp-1",
        limit=2,
    )
    assert options["definition_id"] == FILED_SINGLE_CAPTURE_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is FiledSingleCapturePublicResultV1


@pytest.mark.parametrize("mismatch", ["pair", "effect", "terminal"])
def test_single_capture_mismatch_refuses_with_correlated_receipt(
    monkeypatch: pytest.MonkeyPatch, mismatch: str
) -> None:
    projection = _projection()
    effect = OperationEffect.UPDATED
    condition = OperationTerminalCondition.SUCCEEDED
    if mismatch == "pair":
        projection = projection.model_copy(update={"year": 2024})
    elif mismatch == "effect":
        effect = OperationEffect.NONE
    else:
        condition = OperationTerminalCondition.REFUSED
    _bind(monkeypatch, projection, effect=effect, condition=condition)

    with pytest.raises(CliRefusedBoundaryError) as error:
        _read()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_single_capture_cli_emits_restored_metrics_and_notices(monkeypatch: pytest.MonkeyPatch) -> None:
    _bind(monkeypatch, _projection(), effect=OperationEffect.UPDATED)
    read = _read()
    monkeypatch.setattr(bridge, "read_filed_single_capture_for_cli", lambda *_args, **_kwargs: read)
    monkeypatch.setattr(handler, "resolve_optional_root", lambda *_args, **_kwargs: _OUTPUT_ROOT)
    envelopes: list[dict[str, object]] = []
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))

    handler._emit_single_filed_pull(
        cast(typer.Context, cast(object, None)),
        modelo="303",
        year=2025,
        output_root=_OUTPUT_ROOT,
        period="1T",
        expediente_id="exp-1",
        limit=2,
    )

    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "app.live.filed.pull"
    result = envelope["result"]
    assert isinstance(result, FiledCaptureResult)
    assert result.captured_count == 1
    assert result.reconciliations[0].outcome is FilingReconciliationOutcome.CONFIRMED
    notices = cast("tuple[Notice, ...]", envelope["notices"])
    assert any(notice.code == "live.filed.capture_test" for notice in notices)
    assert any(notice.code == "modelo.filing_chain.receipt_totals_only" for notice in notices)


def test_filing_instance_evidence_notice_renders_after_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection()
    row = projection.reconciliations[0].model_copy(
        update={
            "outcome": "unverifiable",
            "notices": (FiledReconciliationNoticeV1(code="filing_instance_evidence_unavailable", context=()),),
        }
    )
    _bind(monkeypatch, projection.model_copy(update={"reconciliations": (row,)}), effect=OperationEffect.UPDATED)

    (notice,) = filing_reconciliation_notices(_read().report.reconciliation_results)
    assert notice.code == "modelo.filing_chain.filing_instance_evidence_unavailable"
    assert notice.message and "{modelo}" not in notice.message


def test_profile_runtime_admission_covers_single_and_bulk_modes() -> None:
    spec = COMMAND_GRAPH.node("app_live_filed_pull").spec

    assert _uses_runtime_profile_client(
        spec,
        {"modelos": ["303"], "year": 2025, "year_from": None, "year_to": None},
    )
    assert _uses_runtime_profile_client(
        spec,
        {"modelos": ["303"], "year": 2025, "year_from": 2024, "year_to": 2025},
    )
    assert _uses_runtime_profile_client(
        spec,
        {"modelos": ["303", "390"], "year": 2025, "year_from": None, "year_to": None},
    )
    assert _uses_runtime_profile_client(
        spec,
        {"modelos": ["303"], "year": None, "year_from": None, "year_to": None},
    )
