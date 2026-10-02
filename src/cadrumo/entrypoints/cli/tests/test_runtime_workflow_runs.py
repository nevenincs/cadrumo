"""CLI workflow-run bridge correlates terminal snapshots with the submitted receipt."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.operations.public_period import PublicPeriod
from ....application.runtime.contracts import RuntimeRefusalCode
from ....application.workflow.run_models import WorkflowObligationFacts, WorkflowResult, WorkflowStage
from ....application.workflow.run_projection import WorkflowRunSnapshot
from ....application.workflow.run_read_operation import (
    WorkflowRunListProjection,
    WorkflowRunReadProjection,
    WorkflowRunReadRequest,
)
from ....core.modelo import Modelo
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....core.period import Period
from ....domain.deadlines.models import ObligationStatus
from .. import _modelo_work_runs_cli as cli
from .. import runtime_workflow_runs as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 4, 12, 9, tzinfo=UTC)


def _snapshot(*, run_id: str = "b" * 16) -> WorkflowRunSnapshot:
    period = Period.from_year_and_code(2025, "1T")
    return WorkflowRunSnapshot.from_run(
        WorkflowResult(
            run_id=run_id,
            started_at=_NOW,
            ended_at=_NOW,
            final_stage=WorkflowStage.DONE,
            obligation=WorkflowObligationFacts(
                modelo=Modelo("303"),
                period=period,
                opens_on=date(2025, 4, 1),
                closes_on=date(2025, 4, 20),
                status=ObligationStatus.UPCOMING,
            ),
            steps=(),
            summary_locale_key="application.workflow.results.completed",
        )
    )


def _client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(
        bridge, "require_profile_client", lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE)
    )


def test_exact_run_bridge_returns_only_matching_terminal_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    _client(monkeypatch)
    submitted: list[WorkflowRunReadRequest] = []

    def submit(_client: object, request: WorkflowRunReadRequest, **_kwargs: object):
        submitted.append(request)
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=WorkflowRunReadProjection(profile_id=_PROFILE, expected_period=None, run=_snapshot()),
            effect=OperationEffect.NONE,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    observed = bridge.read_workflow_run(cast(typer.Context, cast(object, None)), run_id="b" * 16)
    assert observed.run.run_id == "b" * 16
    assert observed.completion.operation_id == _OPERATION_ID
    assert observed.completion.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert observed.completion.effect is OperationEffect.NONE
    assert len(submitted) == 1
    assert submitted[0].profile_id == _PROFILE
    assert submitted[0].expected_period is None


def test_inventory_bridge_returns_matching_receipt_and_all_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    _client(monkeypatch)
    run = _snapshot()
    submitted: list[object] = []

    def submit(_client: object, request: object, **_kwargs: object):
        submitted.append(request)
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=WorkflowRunListProjection(profile_id=_PROFILE, runs=(run,)),
            effect=OperationEffect.NONE,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    observed = bridge.read_workflow_runs(cast(typer.Context, cast(object, None)))
    assert observed.runs == (run,)
    assert observed.completion.operation_id == _OPERATION_ID
    assert observed.completion.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert observed.completion.effect is OperationEffect.NONE
    assert len(submitted) == 1


@pytest.mark.parametrize(
    ("profile", "run_id", "expected", "condition", "effect"),
    [
        (_OTHER, "b" * 16, None, OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        (_PROFILE, "c" * 16, None, OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        (_PROFILE, "b" * 16, "period", OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        (_PROFILE, "b" * 16, None, OperationTerminalCondition.REFUSED, OperationEffect.NONE),
        (_PROFILE, "b" * 16, None, OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED),
    ],
)
def test_bad_exact_run_result_retains_receipt(
    monkeypatch: pytest.MonkeyPatch,
    profile: UUID,
    run_id: str,
    expected: str | None,
    condition: OperationTerminalCondition,
    effect: OperationEffect,
) -> None:
    _client(monkeypatch)
    period = PublicPeriod.from_period(Period.from_year_and_code(2025, "1T")) if expected else None
    monkeypatch.setattr(
        bridge,
        "run_registered_operation",
        lambda *_args, **_kwargs: RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=WorkflowRunReadProjection(
                profile_id=profile, expected_period=period, run=_snapshot(run_id=run_id)
            ),
            terminal_condition=condition,
            effect=effect,
        ),
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.read_workflow_run(cast(typer.Context, cast(object, None)), run_id="b" * 16)
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == effect.value
    assert refused.value.context["terminal_condition"] == condition.value


@pytest.mark.parametrize("profile,effect", [(_OTHER, OperationEffect.NONE), (_PROFILE, OperationEffect.UPDATED)])
def test_bad_inventory_result_retains_receipt(
    monkeypatch: pytest.MonkeyPatch, profile: UUID, effect: OperationEffect
) -> None:
    _client(monkeypatch)
    monkeypatch.setattr(
        bridge,
        "run_registered_operation",
        lambda *_args, **_kwargs: RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=WorkflowRunListProjection(profile_id=profile, runs=(_snapshot(),)),
            effect=effect,
        ),
    )
    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.read_workflow_runs(cast(typer.Context, cast(object, None)))
    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["effect"] == effect.value


def _read_completion(run_id: str = "b" * 16) -> bridge.WorkflowRunReadCompletion:
    run = _snapshot(run_id=run_id)
    projection = WorkflowRunReadProjection(profile_id=_PROFILE, expected_period=None, run=run)
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )
    return bridge.WorkflowRunReadCompletion(completion=completion, run=run)


def _runs_completion() -> bridge.WorkflowRunsReadCompletion:
    runs = (_snapshot(),)
    projection = WorkflowRunListProjection(profile_id=_PROFILE, runs=runs)
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )
    return bridge.WorkflowRunsReadCompletion(completion=completion, runs=runs)


@pytest.mark.parametrize(
    ("handler_name", "inventory"),
    [("work_run_details", False), ("work_run", False), ("work_runs", True)],
)
@pytest.mark.parametrize("failure_stage", ["render", "emit"])
def test_run_presentation_failure_retains_terminal_receipt(
    monkeypatch: pytest.MonkeyPatch,
    handler_name: str,
    inventory: bool,
    failure_stage: str,
) -> None:
    monkeypatch.setattr(cli, "activate_subcommand_output_language", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        cli,
        "read_workflow_runs" if inventory else "read_workflow_run",
        (lambda *_args, **_kwargs: _runs_completion())
        if inventory
        else (lambda _ctx, *, run_id: _read_completion(run_id)),
    )

    def fail_presentation(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("presentation failure")

    if failure_stage == "render":
        monkeypatch.setattr(cli, "_workflow_run_projection", fail_presentation)
    else:
        monkeypatch.setattr(
            cli,
            "_workflow_run_projection",
            lambda *_args, **_kwargs: SimpleNamespace(
                modelo="303",
                period="2025-1T",
                summary_stage=None,
                summary_locale_key="application.workflow.results.completed",
                summary_details=None,
                site_health_alert=None,
                action=None,
            ),
        )
        monkeypatch.setattr(cli, "_render_workflow_step_summary", lambda *_args, **_kwargs: "completed")
        monkeypatch.setattr(cli, "emit_envelope", fail_presentation)

    handler = getattr(cli, handler_name)
    context = cast(typer.Context, cast(object, None))
    with pytest.raises(CliRefusedBoundaryError) as refused:
        handler(context) if inventory else handler(context, run_id="b" * 16)

    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["reason"] == RuntimeRefusalCode.UNAVAILABLE.value
    assert refused.value.context["terminal_condition"] == OperationTerminalCondition.SUCCEEDED.value
    assert refused.value.context["effect"] == OperationEffect.NONE.value


@pytest.mark.parametrize("handler_name", ["work_run_details", "work_run", "work_runs"])
def test_run_presentation_preserves_typer_exit(
    monkeypatch: pytest.MonkeyPatch,
    handler_name: str,
) -> None:
    monkeypatch.setattr(cli, "activate_subcommand_output_language", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "read_workflow_run", lambda _ctx, *, run_id: _read_completion(run_id))
    monkeypatch.setattr(cli, "read_workflow_runs", lambda *_args, **_kwargs: _runs_completion())
    monkeypatch.setattr(
        cli,
        "_workflow_run_projection",
        lambda *_args, **_kwargs: SimpleNamespace(
            modelo="303",
            period="2025-1T",
            summary_stage=None,
            summary_locale_key="application.workflow.results.completed",
            summary_details=None,
            site_health_alert=None,
            action=None,
        ),
    )
    monkeypatch.setattr(cli, "_render_workflow_step_summary", lambda *_args, **_kwargs: "completed")
    expected = typer.Exit(code=0)
    monkeypatch.setattr(cli, "emit_envelope", lambda *_args, **_kwargs: (_ for _ in ()).throw(expected))

    handler = getattr(cli, handler_name)
    context = cast(typer.Context, cast(object, None))
    with pytest.raises(typer.Exit) as raised:
        handler(context) if handler_name == "work_runs" else handler(context, run_id="b" * 16)
    assert raised.value is expected
