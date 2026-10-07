"""The reconcile-list CLI bridge correlates profile and requested scope."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.modelo.reconciliation_list_operation import (
    MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,
    ModeloReconciliationAdvisoryProjection,
    ModeloReconciliationListEntryProjection,
    ModeloReconciliationListProjection,
    ModeloReconciliationListRequest,
)
from ....application.modelo.reconciliation_records import (
    ModeloReconciliationDiff,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationVerdict,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import _modelo_reconcile_cli as handler
from .. import runtime_modelo_reconciliation_list as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_WORK_A = "1" * 64
_WORK_B = "2" * 64
_OPERATION_ID = "a" * 64


def _row(work_unit_id: str = _WORK_A) -> ModeloReconciliationListEntryProjection:
    return ModeloReconciliationListEntryProjection(
        event_id="b" * 64,
        bucket_id=str(_PROFILE),
        work_unit_id=work_unit_id,
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        source_path="C:/synthetic/evidence.pdf",
        verdict=ModeloReconciliationVerdict.MATCHES,
        diff_count=0,
        actor="synthetic-test-operator",
        reconciled_at=datetime(2026, 3, 10, 12, tzinfo=UTC),
    )


def _projection(work_unit_id: str | None, rows: tuple[ModeloReconciliationListEntryProjection, ...] = ()):
    return ModeloReconciliationListProjection(
        profile_id=_PROFILE,
        work_unit_id=work_unit_id,
        reconciliation_count=len(rows),
        reconciliations=rows,
    )


def _invoke(*, work_unit_id: str | None = None):
    return bridge.read_modelo_reconciliation_list(cast(typer.Context, cast(object, None)), work_unit_id=work_unit_id)


def _bind(monkeypatch: pytest.MonkeyPatch, completion, submitted: list[ModeloReconciliationListRequest]) -> None:
    monkeypatch.setattr(bridge, "bound_profile_client", lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE))

    def submit(_client: object, request: ModeloReconciliationListRequest, **kwargs: object):
        submitted.append(request)
        assert kwargs["definition_id"] == MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is ModeloReconciliationListProjection
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def test_bridge_submits_exact_profile_filter_and_accepts_settled_read(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloReconciliationListRequest] = []
    projection = _projection(_WORK_A, (_row(_WORK_A),))
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        ),
        submitted,
    )

    result = _invoke(work_unit_id=f" {_WORK_A} ")

    assert result is projection
    assert submitted == [ModeloReconciliationListRequest(profile_id=_PROFILE, work_unit_id=_WORK_A)]


def test_bridge_normalizes_empty_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloReconciliationListRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(None),
            effect=OperationEffect.NONE,
        ),
        submitted,
    )
    assert _invoke(work_unit_id="  ").work_unit_id is None
    assert submitted == [ModeloReconciliationListRequest(profile_id=_PROFILE, work_unit_id=None)]


def test_bridge_rejects_nonsettled_receipt_and_scope_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloReconciliationListRequest] = []
    refused_completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=_projection(_WORK_A, (_row(_WORK_A),)),
        effect=OperationEffect.NONE,
        terminal_condition=OperationTerminalCondition.REFUSED,
    )
    _bind(monkeypatch, refused_completion, submitted)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke(work_unit_id=_WORK_A)
    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"

    invalid_projection = ModeloReconciliationListProjection.model_construct(
        profile_id=_PROFILE,
        work_unit_id=_WORK_A,
        reconciliation_count=1,
        reconciliations=(_row(_WORK_B),),
    )
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=invalid_projection,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        ),
        submitted,
    )
    with pytest.raises(CliRefusedBoundaryError) as scope_refused:
        _invoke(work_unit_id=_WORK_A)
    assert scope_refused.value.context is not None
    assert scope_refused.value.context["reason"] == "runtime_invalid_frame"

    foreign_profile_projection = ModeloReconciliationListProjection.model_construct(
        profile_id=_OTHER,
        work_unit_id=_WORK_A,
        reconciliation_count=1,
        reconciliations=(_row(_WORK_A),),
    )
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=foreign_profile_projection,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        ),
        submitted,
    )
    with pytest.raises(CliRefusedBoundaryError) as profile_refused:
        _invoke(work_unit_id=_WORK_A)
    assert profile_refused.value.context is not None
    assert profile_refused.value.context["reason"] == "runtime_invalid_frame"


def test_bridge_rejects_mutating_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloReconciliationListRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(None),
            effect=OperationEffect.UPDATED,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        ),
        submitted,
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke()
    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"


def test_bridge_rejects_success_receipt_with_refusal_code(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[ModeloReconciliationListRequest] = []
    _bind(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=_projection(None),
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            refusal_code="unexpected-refusal",
        ),
        submitted,
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke()
    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"


def test_history_renderer_preserves_saved_differences_and_advisory_context(monkeypatch: pytest.MonkeyPatch) -> None:
    diff = ModeloReconciliationDiff(
        field_name="period", work_unit_value="1T", evidence_value="2T", kind="period_mismatch"
    )
    advisory = ModeloReconciliationAdvisoryProjection(
        code="missing_evidence", message="Captured content is unavailable", context=(("capture", "unavailable"),)
    )
    row = _row().model_copy(update={"diffs": (diff,), "advisories": (advisory,), "diff_count": 1, "advisory_count": 1})
    monkeypatch.setattr(bridge, "read_modelo_reconciliation_list", lambda *args, **kwargs: _projection(None, (row,)))
    emitted = {}
    monkeypatch.setattr(handler, "emit_envelope", lambda _ctx, **kwargs: emitted.update(kwargs))
    handler.reconcile_list_verb(cast(typer.Context, cast(object, None)))
    payload = emitted["result"].reconciliations[0]
    assert payload.diffs == (diff,)
    assert dict(payload.advisories[0].context) == {"capture": "unavailable"}
    assert any("work_unit=1T\tevidence=2T" in line for line in emitted["lines"])
