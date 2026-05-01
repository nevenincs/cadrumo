"""Unit tests for :mod:`aeat.workflow._persistence`."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from . import (
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
    list_runs,
    load_run,
    save_run,
)
from ._errors import WorkflowError

pytestmark = [pytest.mark.unit, pytest.mark.domain_mediation]


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


class TestPersistenceRoundTrip:
    def test_save_load_round_trip(self, tmp_path: Path) -> None:
        original = _result("a" * 16, datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC))
        save_run(original, runs_dir=tmp_path)
        reloaded = load_run(original.run_id, runs_dir=tmp_path)
        assert reloaded == original

    def test_load_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(WorkflowError):
            load_run("missing", runs_dir=tmp_path)

    def test_load_rejects_traversal_id(self, tmp_path: Path) -> None:
        with pytest.raises(WorkflowError, match="simple filename token"):
            load_run("../escape", runs_dir=tmp_path)

    def test_save_rejects_traversal_id(self, tmp_path: Path) -> None:
        escaped = _result("a" * 16, datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)).model_copy(
            update={"run_id": "../escape"}
        )
        with pytest.raises(WorkflowError, match="simple filename token"):
            save_run(escaped, runs_dir=tmp_path)

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

    def test_save_run_lock_target_aligns_with_rotation(
        self,
        tmp_path: Path,
    ) -> None:
        # regression: the workflow run writer must
        # acquire the writer-canonical sidecar lock so concurrent
        # rotate-master-key contends on the same OS-level lock-byte
        # target. The runs_dir contains
        # ``<run_id>.envelope.json`` files; the -canonical
        # sidecar is ``<run_id>.lock`` (not ``<run_id>.envelope.lock``).
        from ...adapters.persistence.storage import LockAcquisitionError, RotationPlanEntry, exclusive_file_lock

        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        result = _result("c" * 16, datetime(2026, 4, 13, tzinfo=UTC))
        save_run(result, runs_dir=runs_dir)

        envelope_path = runs_dir / f"{result.run_id}.envelope.json"
        rotation_entry = RotationPlanEntry(
            store_dir=runs_dir,
            hkdf_context=b"aeat.application.workflow.run.v1",
        )
        rotation_lock_target = rotation_entry.lock_path_for(envelope_path)
        expected_writer_lock_target = runs_dir / f"{result.run_id}.lock"
        assert rotation_lock_target == expected_writer_lock_target

        with (
            exclusive_file_lock(expected_writer_lock_target),
            pytest.raises(LockAcquisitionError),
            exclusive_file_lock(rotation_lock_target, timeout=0.0),
        ):
            pass
