"""Unit tests for secure workflow-run persistence.

Covers :func:`aeat.application.workflow.save_run`,
:func:`aeat.application.workflow.load_run`, and
:func:`aeat.application.workflow.list_runs`, including round-tripping
and traversal-safe id validation.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider
from ...adapters.persistence.storage.sql.engine import dispose_engine
from . import (
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
    list_runs,
    load_run,
    save_run,
)
from ._errors import WorkflowError

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _patch_secure_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{tmp_path / 'aeat.db'}")
    with EphemeralMasterKeyProvider():
        try:
            yield
        finally:
            dispose_engine()


def _database_bytes(tmp_path: Path) -> bytes:
    return (tmp_path / "aeat.db").read_bytes()


def _result(run_id: str, started: datetime) -> WorkflowResult:
    step = WorkflowStep(
        stage=WorkflowStage.LOADING_PROFILE,
        started_at=started,
        ended_at=started,
        success=True,
        summary="translation",
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=started,
        ended_at=started,
        final_stage=WorkflowStage.DONE,
        aborted_reason=None,
        steps=(step,),
        summary="translation",
    )


class TestPersistenceRoundTrip:
    """End-to-end coverage of save/load/list and lock-target alignment."""

    def test_save_load_round_trip(self, tmp_path: Path) -> None:
        original = _result("a" * 16, datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC))
        marker = save_run(original, runs_dir=tmp_path)
        reloaded = load_run(original.run_id)
        assert reloaded == original
        assert marker.as_posix().endswith(original.run_id)
        raw = _database_bytes(tmp_path)
        assert b"secure_objects" in raw
        assert original.run_id.encode("utf-8") not in raw
        assert b"translation" not in raw

    def test_load_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(WorkflowError, match=r"workflow"):
            load_run("missing")

    def test_load_rejects_traversal_id(self, tmp_path: Path) -> None:
        with pytest.raises(WorkflowError, match="path separators"):
            load_run("../escape")

    def test_save_rejects_traversal_id(self, tmp_path: Path) -> None:
        escaped = _result("a" * 16, datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)).model_copy(
            update={"run_id": "../escape"}
        )
        with pytest.raises(WorkflowError, match="path separators"):
            save_run(escaped, runs_dir=tmp_path)

    def test_list_runs_sorted_descending(self, tmp_path: Path) -> None:
        early = _result("a" * 16, datetime(2026, 4, 10, tzinfo=UTC))
        late = _result("b" * 16, datetime(2026, 4, 12, tzinfo=UTC))
        save_run(early, runs_dir=tmp_path)
        save_run(late, runs_dir=tmp_path)
        runs = list_runs()
        assert [r.run_id for r in runs] == [late.run_id, early.run_id]

    def test_list_runs_since_filter(self, tmp_path: Path) -> None:
        early = _result("a" * 16, datetime(2026, 4, 10, tzinfo=UTC))
        late = _result("b" * 16, datetime(2026, 4, 12, tzinfo=UTC))
        save_run(early, runs_dir=tmp_path)
        save_run(late, runs_dir=tmp_path)
        runs = list_runs(since=date(2026, 4, 11))
        assert [r.run_id for r in runs] == [late.run_id]

    def test_save_run_does_not_create_envelope_files(
        self,
        tmp_path: Path,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        result = _result("c" * 16, datetime(2026, 4, 13, tzinfo=UTC))
        save_run(result, runs_dir=runs_dir)
        assert list(runs_dir.iterdir()) == []


class _EmitError(RuntimeError):
    """Real exception injected to simulate a downstream emit failure."""


def test_reset_workflow_state_emit_failure_leaves_row_intact() -> None:
    """When event emit fails, the secure-object row must remain present.

    The reset routine emits the ``workflow_state.reset`` event before
    discarding the secure-object row. If the emit raises, the delete
    must not execute -- the row stays, the next reset attempt picks
    up where this one left off, and no plaintext is leaked. The
    failure path is exercised by injecting a real failing emitter
    through the repository's ``emit_reset`` constructor seam -- no
    module monkeypatching, no test double or Mock.
    """

    from ._models import WorkflowState
    from ._persistence import WorkflowStateRepository

    def _raise(**_: object) -> None:
        raise _EmitError("simulated downstream emit failure")

    repository = WorkflowStateRepository(emit_reset=_raise)
    repository.save(WorkflowState())
    assert repository._objects.exists("aeat.workflow", "state")

    with pytest.raises(_EmitError):
        repository.reset_workflow_state()

    assert repository._objects.exists("aeat.workflow", "state"), (
        "emit-first contract violated: secure-object row was deleted before the "
        "audit event landed; the recovery route lost its trail."
    )
