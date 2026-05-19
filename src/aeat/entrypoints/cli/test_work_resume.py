"""CLI surface tests for `aeat app modelo work resume WORKFLOW_RUN_ID`."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.workflow import (
    WorkflowAbortReason,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
    save_run,
)
from aeat.domain.deadlines import FilingObligation, ObligationStatus
from aeat.entrypoints.cli._modelo import work_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{tmp_path / 'resume.db'}")
    with EphemeralMasterKeyProvider():
        try:
            yield
        finally:
            dispose_engine()


_T = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)


def _obligation() -> FilingObligation:
    return FilingObligation(
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
    assert "WORKFLOW_RUN_ID" in result.output
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


def test_resume_emits_no_bucket_event() -> None:
    """The resume verb is structurally read-only: it neither emits a bucket
    event nor calls into BucketEventHistoryRepository at all.

    Verified at the source level so a future refactor that adds an event
    emission to the verb must consciously update this contract."""
    from aeat.entrypoints.cli import _modelo

    source = Path(_modelo.__file__).read_text(encoding="utf-8")
    # Slice the source to just the work_resume function definition.
    assert "def work_resume" in source
    start = source.index("def work_resume")
    end = source.index("def _parse_amendment_casilla", start)
    body = source[start:end]
    assert "bucket_event" not in body.lower()
    assert "BucketEventHistory" not in body
