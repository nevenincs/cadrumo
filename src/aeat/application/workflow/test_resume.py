"""Tests for the workflow resumption action."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider, override_master_key_provider
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...domain.deadlines import FilingObligation, ObligationStatus
from . import (
    WorkflowAbortReason,
    WorkflowError,
    WorkflowResult,
    WorkflowResumeContext,
    WorkflowResumeRefusedError,
    WorkflowStage,
    WorkflowStep,
    resume_modelo_workflow,
    save_run,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _patch_secure_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{tmp_path / 'aeat.db'}")
    override_master_key_provider(EphemeralMasterKeyProvider())
    try:
        yield
    finally:
        override_master_key_provider(None)
        dispose_engine()


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


def test_resume_returns_context_for_resumable_aborted_run(tmp_path: Path) -> None:
    run_id = "a" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=_obligation(),
        ),
    )
    context = resume_modelo_workflow(run_id)
    assert isinstance(context, WorkflowResumeContext)
    assert context.resumed_from_run_id == run_id
    assert context.modelo == "130"
    assert context.period == "2026Q1"
    assert context.aborted_reason is WorkflowAbortReason.SITE_UNAVAILABLE
    assert context.obligation.modelo == "130"


def test_resume_refuses_done_run(tmp_path: Path) -> None:
    run_id = "b" * 16
    save_run(_done_result(run_id))
    with pytest.raises(WorkflowResumeRefusedError, match=r"final_stage"):
        resume_modelo_workflow(run_id)


@pytest.mark.parametrize(
    "reason",
    [
        WorkflowAbortReason.NO_PENDING_OBLIGATION,
        WorkflowAbortReason.ALREADY_FILED,
        WorkflowAbortReason.USER_CANCELLED,
    ],
)
def test_resume_refuses_non_resumable_reasons(
    tmp_path: Path, reason: WorkflowAbortReason,
) -> None:
    run_id = "c" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=reason,
            obligation=_obligation() if reason is not WorkflowAbortReason.NO_PENDING_OBLIGATION else None,
        ),
    )
    with pytest.raises(WorkflowResumeRefusedError, match=r"terminal by design"):
        resume_modelo_workflow(run_id)


def test_resume_refuses_run_without_obligation(tmp_path: Path) -> None:
    run_id = "d" * 16
    save_run(
        _aborted_result(
            run_id=run_id,
            reason=WorkflowAbortReason.SITE_UNAVAILABLE,
            obligation=None,
        ),
    )
    with pytest.raises(WorkflowResumeRefusedError, match=r"obligation"):
        resume_modelo_workflow(run_id)


def test_resume_for_missing_run_id_surfaces_workflow_error(tmp_path: Path) -> None:
    with pytest.raises(WorkflowError, match=r"workflow run not found"):
        resume_modelo_workflow("missing-run-id-9")
