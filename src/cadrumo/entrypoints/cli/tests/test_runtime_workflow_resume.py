"""Resume bridge retains the registered terminal receipt through rendering."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.operations.public_period import PublicPeriod
from ....application.runtime.contracts import RuntimeRefusalCode
from ....application.workflow.abort import WorkflowAbortReason
from ....application.workflow.resume import WorkflowResumeContext, WorkflowResumeTargetResolution
from ....application.workflow.resume_operation import (
    WorkflowResumeAddress,
    WorkflowResumeProjection,
    WorkflowResumeRequest,
    WorkflowResumeSuccess,
)
from ....application.workflow.run_models import WorkflowObligationFacts
from ....application.workflow.run_projection import WorkflowObligationSnapshot
from ....core.modelo import Modelo
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ....domain.deadlines.models import ObligationStatus
from .. import _modelo_work_runs_cli as cli
from .. import runtime_workflow_resume as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_RUN_ID = "b" * 16
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 4, 12, 9, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")


def _completion() -> bridge.WorkflowResumeCompletion:
    obligation = WorkflowObligationSnapshot.from_obligation(
        WorkflowObligationFacts(
            modelo=Modelo("303"),
            period=_PERIOD,
            opens_on=date(2025, 4, 1),
            closes_on=date(2025, 4, 20),
            status=ObligationStatus.UPCOMING,
        )
    )
    address = WorkflowResumeAddress(
        run_id=_RUN_ID,
        source="workflow_run_id",
        modelo="303",
        period=PublicPeriod.from_period(_PERIOD),
        filing_year=2025,
        work_unit_id=None,
        short_work_unit_id=None,
        calculation_revision_id=None,
        short_calculation_revision_id=None,
    )
    projection = WorkflowResumeProjection(
        profile_id=_PROFILE,
        outcome=WorkflowResumeSuccess(
            address=address,
            obligation=obligation,
            aborted_reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
        ),
    )
    receipt = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        terminal_condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
    )
    return bridge.WorkflowResumeCompletion(
        completion=receipt,
        context=WorkflowResumeContext(
            resumed_from_run_id=_RUN_ID,
            modelo="303",
            period=_PERIOD,
            obligation=obligation.to_obligation(),
            aborted_reason=WorkflowAbortReason.DRAFT_HAS_ERRORS,
        ),
        resolution=WorkflowResumeTargetResolution(
            run_id=_RUN_ID,
            source="workflow_run_id",
            modelo="303",
            period=_PERIOD,
            filing_year=2025,
        ),
    )


def test_resume_bridge_returns_context_bound_to_matching_operation_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(
        bridge,
        "require_profile_client",
        lambda *_args, **_kwargs: SimpleNamespace(profile_id=_PROFILE),
    )
    expected = _completion()
    submitted: list[tuple[WorkflowResumeRequest, dict[str, object]]] = []

    def run(
        _client: object, request: WorkflowResumeRequest, **kwargs: object
    ) -> RegisteredOperationCompletion[WorkflowResumeProjection]:
        submitted.append((request, kwargs))
        return expected.completion

    monkeypatch.setattr(bridge, "run_registered_operation", run)
    completed = bridge.read_workflow_resume_context(
        cast(typer.Context, cast(object, None)),
        target=_RUN_ID,
        work_unit_id=None,
        calculation_revision_id=None,
        modelo=None,
        period=None,
        revision_id=None,
        selector=None,
        bucket_id=None,
    )

    assert completed.completion is expected.completion
    assert completed.completion.operation_id == _OPERATION_ID
    assert completed.completion.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert completed.completion.effect is OperationEffect.NONE
    assert completed.context == expected.context
    assert completed.resolution == expected.resolution
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request.profile_id == _PROFILE
    assert request.target == _RUN_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["allow_refusal_detail"] is True


def _install_resume(monkeypatch: pytest.MonkeyPatch, completion: bridge.WorkflowResumeCompletion) -> None:
    monkeypatch.setattr(cli, "activate_subcommand_output_language", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "resolve_optional_cli_period", lambda **_kwargs: None)
    monkeypatch.setattr(cli, "read_workflow_resume_context", lambda *_args, **_kwargs: completion)


def test_resume_presentation_failure_preserves_known_terminal_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    completion = _completion()
    _install_resume(monkeypatch, completion)

    def fail_presentation(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("presentation failure")

    monkeypatch.setattr(cli, "_emit_work_resume", fail_presentation)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        cli.work_resume(cast(typer.Context, cast(object, None)))

    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["reason"] == RuntimeRefusalCode.UNAVAILABLE.value
    assert refused.value.context["terminal_condition"] == OperationTerminalCondition.SUCCEEDED.value
    assert refused.value.context["effect"] == OperationEffect.NONE.value


def test_resume_presentation_reraises_typer_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    completion = _completion()
    _install_resume(monkeypatch, completion)
    expected = typer.Exit(code=0)
    monkeypatch.setattr(cli, "_emit_work_resume", lambda *_args, **_kwargs: (_ for _ in ()).throw(expected))

    with pytest.raises(typer.Exit) as raised:
        cli.work_resume(cast(typer.Context, cast(object, None)))
    assert raised.value is expected
