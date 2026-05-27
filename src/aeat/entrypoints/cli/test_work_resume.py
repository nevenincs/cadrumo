"""CLI surface tests for `aeat app modelo work resume WORKFLOW_RUN_ID`."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.user_profile._orchestration import profile_create_storage_span
from aeat.application.workflow import (
    WorkflowAbortReason,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
    save_run,
)
from aeat.domain.deadlines import ModeloDeadline, ObligationStatus
from aeat.entrypoints.cli._modelo import work_app
from aeat.tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        try:
            yield
        finally:
            dispose_engine()


_T = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)


def _obligation() -> ModeloDeadline:
    return ModeloDeadline(
        modelo="130",
        period="2026Q1",
        opens_on=date(2026, 4, 1),
        closes_on=date(2026, 4, 20),
        status=ObligationStatus.UPCOMING,
        applies_because="economic activity",
    )


def _aborted_run(run_id: str, *, reason: WorkflowAbortReason) -> WorkflowResult:
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
        obligation=_obligation(),
        steps=(step,),
        summary="aborted",
    )


def _done_run(run_id: str) -> WorkflowResult:
    step = WorkflowStep(
        stage=WorkflowStage.LOADING_PROFILE,
        started_at=_T,
        ended_at=_T,
        success=True,
        summary="ok",
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=_T,
        ended_at=_T,
        final_stage=WorkflowStage.DONE,
        aborted_reason=None,
        obligation=_obligation(),
        steps=(step,),
        summary="ok",
    )


def test_resume_help_advertises_the_command(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(work_app, ["resume", "--help"])
    assert result.exit_code == 0
    assert "TARGET" in result.output
    assert "AEAT" in result.output  # the docstring mentions the non-contact guarantee


def test_resume_surfaces_obligation_for_resumable_run(cli_runner: CliRunner) -> None:
    run_id = "a" * 16
    save_run(_aborted_run(run_id, reason=WorkflowAbortReason.SITE_UNAVAILABLE))
    result = cli_runner.invoke(work_app, ["resume", run_id])
    assert result.exit_code == 0, result.output
    assert "modelo\t130" in result.output
    assert "period\t2026Q1" in result.output
    assert "aborted_reason\tSITE_UNAVAILABLE" in result.output


def test_resume_refuses_done_run_with_bad_parameter(cli_runner: CliRunner) -> None:
    run_id = "b" * 16
    save_run(_done_run(run_id))
    result = cli_runner.invoke(work_app, ["resume", run_id])
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_resume_refuses_missing_run_with_bad_parameter(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(work_app, ["resume", "0" * 16])
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_resume_refuses_non_resumable_reason(cli_runner: CliRunner) -> None:
    run_id = "c" * 16
    save_run(_aborted_run(run_id, reason=WorkflowAbortReason.USER_CANCELLED))
    result = cli_runner.invoke(work_app, ["resume", run_id])
    assert result.exit_code != 0
    assert "terminal by design" in result.output


def test_runs_lists_persisted_run_ids(cli_runner: CliRunner) -> None:
    """`work runs` lists persisted runs with their run ids so an
    operator can discover the 16-character id `work resume` needs."""

    save_run(_aborted_run("a" * 16, reason=WorkflowAbortReason.SITE_UNAVAILABLE))
    save_run(_done_run("b" * 16))

    result = cli_runner.invoke(work_app, ["runs"])
    assert result.exit_code == 0, result.output
    assert "run_count\t2" in result.output
    assert "a" * 16 in result.output
    assert "b" * 16 in result.output
    assert "130\t2026Q1" in result.output


def test_resume_rejects_a_malformed_target(cli_runner: CliRunner) -> None:
    """A target that is neither a 16-character run id nor a
    64-character work-unit id is refused with operator guidance."""

    result = cli_runner.invoke(work_app, ["resume", "not-an-id"])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "work runs" in result.output


def test_resume_accepts_run_id_directly(cli_runner: CliRunner) -> None:
    """A 16-character run id passed directly resolves to that run."""

    run_id = "e" * 16
    save_run(_aborted_run(run_id, reason=WorkflowAbortReason.SITE_UNAVAILABLE))
    result = cli_runner.invoke(work_app, ["resume", run_id])
    assert result.exit_code == 0, result.output
    assert f"prior_workflow_run_id\t{run_id}" in result.output


def test_resume_emits_no_bucket_event(cli_runner: CliRunner) -> None:
    """The resume verb must not emit any bucket event into BucketEventHistoryRepository.

    Drives `work resume` against a real persisted aborted run through the CLI
    runner and asserts that the real BucketEventHistoryRepository (backed by
    the isolated SQLite engine) has zero entries after the command completes.
    """
    from aeat.domain.buckets import BucketEventHistoryRepository

    run_id = "d" * 16
    save_run(_aborted_run(run_id, reason=WorkflowAbortReason.SITE_UNAVAILABLE))

    repo = BucketEventHistoryRepository()
    before = repo.load().events

    result = cli_runner.invoke(work_app, ["resume", run_id])

    after = repo.load().events
    new_event_ids = set(after.keys()) - set(before.keys())
    assert not new_event_ids, (
        f"`work resume` emitted {len(new_event_ids)} unexpected bucket event(s): "
        f"{new_event_ids!r}. The resume verb must be read-only. "
        f"CLI output:\n{result.output}"
    )
