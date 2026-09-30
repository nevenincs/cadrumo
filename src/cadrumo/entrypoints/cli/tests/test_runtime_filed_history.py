"""Filed-history CLI routing keeps the worker receipt and existing report semantics."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.live.filed_data_capture import FiledHistoryOnboardingRun, FiledHistoryPairOutcome
from ....application.live.filed_history_operation import (
    FILED_HISTORY_OPERATION_DEFINITION_ID,
    FiledHistoryEvidenceNoticeV1,
    FiledHistoryOperationRequest,
    FiledHistoryPairOutcomePublicV1,
    FiledHistoryPublicResultV1,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from ....core.json_contract import Notice, NoticeSeverity
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import _app_live as handler
from .. import runtime_filed_history as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_TODAY = date(2026, 9, 29)
_OUTPUT_ROOT = Path("filed-history")


def _report() -> FiledHistoryOnboardingRun:
    return FiledHistoryOnboardingRun(
        pairs=(
            FiledHistoryPairOutcome(
                modelo="303",
                ejercicio=2025,
                signals=(FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,),
                row_count=1,
                captured_count=1,
            ),
        ),
        captured_count=1,
        reached_count=1,
        carries_a_taxpayer_specific_denominator=True,
        iva_wallet_status="reconciled",
        notificaciones_status="captured",
        evidence_notices=(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="live.filed.test_evidence",
                message="Receipt evidence unavailable",
                context={"reason": "unavailable"},
            ),
        ),
    )


def _projection(report: FiledHistoryOnboardingRun | None = None) -> FiledHistoryPublicResultV1:
    run = report or _report()
    return FiledHistoryPublicResultV1(
        dry_run=run.dry_run,
        captured_count=run.captured_count,
        reached_count=run.reached_count,
        scoping_signal=run.scoping_signal,
        carries_a_taxpayer_specific_denominator=run.carries_a_taxpayer_specific_denominator,
        denominator_note=run.denominator_note,
        iva_wallet_status=run.iva_wallet_status,
        iva_wallet_divergence=run.iva_wallet_divergence,
        iva_wallet_blocked=run.iva_wallet_blocked,
        notificaciones_status=run.notificaciones_status,
        notificaciones_row_count=run.notificaciones_row_count,
        stage_failures=run.stage_failures,
        sync_run_ref=run.sync_run_ref,
        evidence_notices=tuple(
            FiledHistoryEvidenceNoticeV1(
                severity=notice.severity,
                code=notice.code,
                message=notice.message,
                context=None if notice.context is None else tuple(sorted(notice.context.items())),
            )
            for notice in run.evidence_notices
        ),
        recapture_notices=(),
        pairs=tuple(
            FiledHistoryPairOutcomePublicV1(
                modelo=pair.modelo,
                ejercicio=pair.ejercicio,
                signals=pair.signals,
                row_count=pair.row_count,
                captured_count=pair.captured_count,
                refused=pair.refused,
            )
            for pair in run.pairs
        ),
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: FiledHistoryPublicResultV1,
    *,
    effect: OperationEffect,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
):
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(
        bridge, "require_profile_client", lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE)
    )
    submitted: list[tuple[FiledHistoryOperationRequest, dict[str, object]]] = []

    def submit(_client: object, request: FiledHistoryOperationRequest, **kwargs: object):
        submitted.append((request, kwargs))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted


def _read() -> bridge.FiledHistoryRead:
    return bridge.read_filed_history_for_cli(
        cast(typer.Context, cast(object, None)), output_root=_OUTPUT_ROOT, limit=2, today=_TODAY
    )


def test_registered_pull_uses_exact_profile_and_preserves_public_report(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted = _bind(monkeypatch, _projection(), effect=OperationEffect.UPDATED)

    read = _read()

    assert read.completion.operation_id == _OPERATION_ID
    assert read.report == _report()
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request == FiledHistoryOperationRequest(
        profile_id=_PROFILE,
        output_root=_OUTPUT_ROOT,
        today=_TODAY,
        limit=2,
        dry_run=False,
    )
    assert options["definition_id"] == FILED_HISTORY_OPERATION_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is FiledHistoryPublicResultV1


@pytest.mark.parametrize("mismatch", ["denominator", "effect", "dry_run", "terminal"])
def test_mismatched_result_refuses_with_correlated_receipt(monkeypatch: pytest.MonkeyPatch, mismatch: str) -> None:
    projection = _projection()
    effect = OperationEffect.UPDATED
    if mismatch == "denominator":
        projection = projection.model_copy(update={"denominator_note": "wrong"})
    elif mismatch == "effect":
        effect = OperationEffect.NONE
    elif mismatch == "dry_run":
        projection = projection.model_copy(update={"dry_run": True})
    _bind(
        monkeypatch,
        projection,
        effect=effect,
        condition=OperationTerminalCondition.REFUSED
        if mismatch == "terminal"
        else OperationTerminalCondition.SUCCEEDED,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        _read()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_command_emits_existing_report_and_notice_from_registered_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind(monkeypatch, _projection(), effect=OperationEffect.UPDATED)
    read = _read()
    monkeypatch.setattr(bridge, "read_filed_history_for_cli", lambda *_args, **_kwargs: read)
    envelopes: list[dict[str, object]] = []
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))

    handler.filed_pull_all_cmd(cast(typer.Context, cast(object, None)), output_root=_OUTPUT_ROOT, limit=2)

    assert len(envelopes) == 1
    envelope = envelopes[0]
    expected_result, expected_lines = handler._filed_pull_all_result_and_lines(_report())
    assert envelope["command"] == "app.live.filed.pull_all"
    assert envelope["result"] == expected_result
    lines = envelope["lines"]
    assert isinstance(lines, tuple)
    assert lines[: len(expected_lines)] == expected_lines
    notices = envelope["notices"]
    assert isinstance(notices, list)
    assert any(notice.code == "live.filed.test_evidence" for notice in notices)
