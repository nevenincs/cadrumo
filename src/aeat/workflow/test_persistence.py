"""Unit tests for :mod:`aeat.workflow._persistence`."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from aeat.workflow import (
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
    list_runs,
    load_run,
    save_run,
)
from aeat.workflow._errors import WorkflowError


def _result(run_id: str, started: datetime) -> WorkflowResult:
    step = WorkflowStep(
        stage=WorkflowStage.LOADING_PROFILE,
        started_at=started,
        ended_at=started,
        success=True,
        summary={"en": "ok"},
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=started,
        ended_at=started,
        final_stage=WorkflowStage.DONE,
        aborted_reason=None,
        steps=(step,),
        summary={"en": "ok"},
    )


@pytest.mark.unit
class TestPersistenceRoundTrip:
    def test_save_load_round_trip(self, tmp_path: Path) -> None:
        original = _result("a" * 16, datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC))
        save_run(original, runs_dir=tmp_path)
        reloaded = load_run(original.run_id, runs_dir=tmp_path)
        assert reloaded == original

    def test_load_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(WorkflowError):
            load_run("missing", runs_dir=tmp_path)

    def test_list_runs_sorted_descending(self, tmp_path: Path) -> None:
        early = _result("a" * 16, datetime(2026, 4, 10, tzinfo=UTC))
        late = _result("b" * 16, datetime(2026, 4, 12, tzinfo=UTC))
        save_run(early, runs_dir=tmp_path)
        save_run(late, runs_dir=tmp_path)
        runs = list_runs(runs_dir=tmp_path)
        assert [r.run_id for r in runs] == [late.run_id, early.run_id]

    def test_list_runs_since_filter(self, tmp_path: Path) -> None:
        early = _result("a" * 16, datetime(2026, 4, 10, tzinfo=UTC))
        late = _result("b" * 16, datetime(2026, 4, 12, tzinfo=UTC))
        save_run(early, runs_dir=tmp_path)
        save_run(late, runs_dir=tmp_path)
        runs = list_runs(runs_dir=tmp_path, since=date(2026, 4, 11))
        assert [r.run_id for r in runs] == [late.run_id]

    def test_list_runs_missing_dir(self, tmp_path: Path) -> None:
        assert list_runs(runs_dir=tmp_path / "does-not-exist") == ()
