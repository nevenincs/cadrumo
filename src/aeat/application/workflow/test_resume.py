"""Tests for the workflow resumption action."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider, override_master_key_provider
from ...adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from ...core.config import Settings
from ...domain.deadlines import FilingObligation, ObligationStatus
from . import (
    WorkflowAbortReason,
    WorkflowError,
    WorkflowResult,
    WorkflowResumeCommand,
    WorkflowResumeContext,
    WorkflowResumeRefusedError,
    WorkflowResumeResult,
    WorkflowStage,
    WorkflowStep,
    resume_modelo_workflow,
    save_run,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    )
    override_master_key_provider(EphemeralMasterKeyProvider())
    try:
        yield SecureObjectRepository(engine=engine)
    finally:
        override_master_key_provider(None)
        engine.dispose()


_T = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)


def _obligation(modelo: str = "130", period: str = "2026Q1") -> FilingObligation:
    return FilingObligation(
        modelo=modelo,
        period=period,
        opens_on=date(2026, 4, 1),
        closes_on=date(2026, 4, 20),
        status=ObligationStatus.UPCOMING,
        applies_because="economic activity",
    )


def _aborted_result(
    *,
    run_id: str,
    reason: WorkflowAbortReason,
    obligation: FilingObligation | None,
) -> WorkflowResult:
    step = WorkflowStep(
        stage=WorkflowStage.BUILDING_DRAFT,
        started_at=_T,
        ended_at=_T,
        success=False,
        summary="aborted",
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=_T,
        ended_at=_T,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=reason,
        obligation=obligation,
        steps=(step,),
        summary="aborted run for resume tests",
    )


def _done_result(run_id: str) -> WorkflowResult:
    step = WorkflowStep(
        stage=WorkflowStage.LOADING_PROFILE,
        started_at=_T,
        ended_at=_T,
        success=True,
        summary="done",
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=_T,
        ended_at=_T,
        final_stage=WorkflowStage.DONE,
        aborted_reason=None,
        obligation=_obligation(),
        steps=(step,),
        summary="done run",
    )


def test_resume_returns_contract_for_resumable_aborted_run(secure_objects: SecureObjectRepository) -> None:
    run_id = "a" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=_obligation(),
        ),
        objects=secure_objects,
    )
    result = resume_modelo_workflow(WorkflowResumeCommand(workflow_run_id=run_id), objects=secure_objects)
    assert isinstance(result, WorkflowResumeResult)
    assert result.prior_workflow_run_id == run_id
    assert result.modelo == "130"
    assert result.period == "2026Q1"
    assert result.aborted_reason is WorkflowAbortReason.SITE_UNAVAILABLE
    assert result.log_fields.as_extra() == {
        "service_name": "workflow_resume",
        "prior_workflow_run_id": run_id,
        "modelo": "130",
        "period": "2026Q1",
        "aborted_reason": "SITE_UNAVAILABLE",
    }
    context = result.context
    assert isinstance(context, WorkflowResumeContext)
    assert context.resumed_from_run_id == run_id
    assert context.modelo == "130"
    assert context.period == "2026Q1"
    assert context.aborted_reason is WorkflowAbortReason.SITE_UNAVAILABLE
    assert context.obligation.modelo == "130"


def test_resume_refuses_done_run(secure_objects: SecureObjectRepository) -> None:
    run_id = "b" * 16
    save_run(_done_result(run_id), objects=secure_objects)
    with pytest.raises(WorkflowResumeRefusedError, match=r"final_stage"):
        resume_modelo_workflow(WorkflowResumeCommand(workflow_run_id=run_id), objects=secure_objects)


@pytest.mark.parametrize(
    "reason",
    [
        WorkflowAbortReason.NO_PENDING_OBLIGATION,
        WorkflowAbortReason.ALREADY_FILED,
        WorkflowAbortReason.USER_CANCELLED,
    ],
)
def test_resume_refuses_non_resumable_reasons(
    secure_objects: SecureObjectRepository,
    reason: WorkflowAbortReason,
) -> None:
    run_id = "c" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=reason,
            obligation=_obligation() if reason is not WorkflowAbortReason.NO_PENDING_OBLIGATION else None,
        ),
        objects=secure_objects,
    )
    with pytest.raises(WorkflowResumeRefusedError, match=r"terminal by design"):
        resume_modelo_workflow(WorkflowResumeCommand(workflow_run_id=run_id), objects=secure_objects)


def test_resume_refuses_run_without_obligation(secure_objects: SecureObjectRepository) -> None:
    run_id = "d" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=None,
        ),
        objects=secure_objects,
    )
    with pytest.raises(WorkflowResumeRefusedError, match=r"obligation"):
        resume_modelo_workflow(WorkflowResumeCommand(workflow_run_id=run_id), objects=secure_objects)


def test_resume_for_missing_run_id_surfaces_workflow_error(secure_objects: SecureObjectRepository) -> None:
    with pytest.raises(WorkflowError, match=r"workflow run not found"):
        resume_modelo_workflow(WorkflowResumeCommand(workflow_run_id="missing-run-id-9"), objects=secure_objects)
