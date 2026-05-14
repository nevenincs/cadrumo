"""Unit tests for secure workflow-run persistence.

Covers :func:`aeat.application.workflow.save_run`,
:func:`aeat.application.workflow.load_run`, and
:func:`aeat.application.workflow.list_runs`, including round-tripping
and traversal-safe id validation.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider, override_master_key_provider
from ...adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from ...core.config import Settings
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


@dataclass(frozen=True)
class SecureWorkflowBackend:
    objects: SecureObjectRepository
    db_path: Path


@pytest.fixture
def secure_backend(tmp_path: Path) -> Iterator[SecureWorkflowBackend]:
    db_path = tmp_path / "aeat.db"
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    override_master_key_provider(EphemeralMasterKeyProvider())
    try:
        yield SecureWorkflowBackend(objects=SecureObjectRepository(engine=engine), db_path=db_path)
    finally:
        override_master_key_provider(None)
        engine.dispose()


def _database_bytes(backend: SecureWorkflowBackend) -> bytes:
    return backend.db_path.read_bytes()


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

    def test_save_load_round_trip(self, tmp_path: Path, secure_backend: SecureWorkflowBackend) -> None:
        original = _result("a" * 16, datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC))
        marker = save_run(original, runs_dir=tmp_path, objects=secure_backend.objects)
        reloaded = load_run(original.run_id, runs_dir=tmp_path, objects=secure_backend.objects)
        assert reloaded == original
        assert marker.as_posix().endswith(original.run_id)
        raw = _database_bytes(secure_backend)
        assert b"secure_objects" in raw
        assert original.run_id.encode("utf-8") not in raw
        assert b"translation" not in raw

    def test_load_missing_raises(self, tmp_path: Path, secure_backend: SecureWorkflowBackend) -> None:
        with pytest.raises(WorkflowError, match=r"workflow"):
            load_run("missing", runs_dir=tmp_path, objects=secure_backend.objects)

    def test_load_rejects_traversal_id(self, tmp_path: Path, secure_backend: SecureWorkflowBackend) -> None:
        with pytest.raises(WorkflowError, match="path separators"):
            load_run("../escape", runs_dir=tmp_path, objects=secure_backend.objects)

    def test_save_rejects_traversal_id(self, tmp_path: Path, secure_backend: SecureWorkflowBackend) -> None:
        escaped = _result("a" * 16, datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)).model_copy(
            update={"run_id": "../escape"}
        )
        with pytest.raises(WorkflowError, match="path separators"):
            save_run(escaped, runs_dir=tmp_path, objects=secure_backend.objects)

    def test_list_runs_sorted_descending(self, secure_backend: SecureWorkflowBackend) -> None:
        early = _result("a" * 16, datetime(2026, 4, 10, tzinfo=UTC))
        late = _result("b" * 16, datetime(2026, 4, 12, tzinfo=UTC))
        save_run(early, objects=secure_backend.objects)
        save_run(late, objects=secure_backend.objects)
        runs = list_runs(objects=secure_backend.objects)
        assert [r.run_id for r in runs] == [late.run_id, early.run_id]

    def test_list_runs_since_filter(self, secure_backend: SecureWorkflowBackend) -> None:
        early = _result("a" * 16, datetime(2026, 4, 10, tzinfo=UTC))
        late = _result("b" * 16, datetime(2026, 4, 12, tzinfo=UTC))
        save_run(early, objects=secure_backend.objects)
        save_run(late, objects=secure_backend.objects)
        runs = list_runs(since=date(2026, 4, 11), objects=secure_backend.objects)
        assert [r.run_id for r in runs] == [late.run_id]

    def test_list_runs_missing_dir(self, tmp_path: Path, secure_backend: SecureWorkflowBackend) -> None:
        assert list_runs(runs_dir=tmp_path / "does-not-exist", objects=secure_backend.objects) == ()

    def test_save_run_does_not_create_envelope_files(
        self,
        tmp_path: Path,
        secure_backend: SecureWorkflowBackend,
    ) -> None:
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        result = _result("c" * 16, datetime(2026, 4, 13, tzinfo=UTC))
        save_run(result, runs_dir=runs_dir, objects=secure_backend.objects)
        assert list(runs_dir.iterdir()) == []

    def test_resumed_from_round_trips(self, secure_backend: SecureWorkflowBackend) -> None:
        result = _result("d" * 16, datetime(2026, 4, 14, tzinfo=UTC)).model_copy(
            update={"resumed_from": "a" * 16}
        )
        save_run(result, objects=secure_backend.objects)
        assert load_run(result.run_id, objects=secure_backend.objects).resumed_from == "a" * 16


class _EmitError(RuntimeError):
    """Real exception injected to simulate a downstream emit failure."""


def test_reset_workflow_state_emit_failure_leaves_row_intact(
    secure_backend: SecureWorkflowBackend,
) -> None:
    """When event emit fails, the secure-object row must remain present.

    The reset routine emits the ``workflow_state.reset`` event before
    discarding the secure-object row. If the emit raises, the delete
    must not execute -- the row stays, the next reset attempt picks
    up where this one left off, and no plaintext is leaked. The
    failure path is exercised through the repository's event-emitter
    dependency with a real callable that raises; no test double or Mock is used.
    """

    from ._persistence import WorkflowStateRepository

    def _raise(**_: object) -> None:
        raise _EmitError("simulated downstream emit failure")

    repository = WorkflowStateRepository(objects=secure_backend.objects, emit_reset_event=_raise)
    from ._models import WorkflowState

    repository.save(WorkflowState())
    assert repository._objects.exists("aeat.workflow", "state")

    with pytest.raises(_EmitError):
        repository.reset_workflow_state()

    assert repository._objects.exists("aeat.workflow", "state"), (
        "emit-first contract violated: secure-object row was deleted before the "
        "audit event landed; the recovery route lost its trail."
    )
