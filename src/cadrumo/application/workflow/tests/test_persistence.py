"""Unit tests for secure workflow-run persistence.

Covers :func:`cadrumo.application.workflow.save_run`,
:func:`cadrumo.application.workflow.load_run`, and
:func:`cadrumo.application.workflow.list_runs`, including round-tripping
and traversal-safe id validation.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from cadrumo.application.workflow.persistence import list_runs, load_run, save_run
from cadrumo.application.workflow.run_models import WorkflowResult, WorkflowStage, WorkflowStep

from ....adapters.persistence.storage.bucket import bucket_paths
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....core import scan_directory
from ..errors import WorkflowError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "56f638b9-5bbe-4888-bb30-574a8e7bc0e9"


_patch_secure_backend = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=True, name="_patch_secure_backend")


def _database_bytes(tmp_path: Path) -> bytes:
    from ....tests.secure_sql import read_db_at_rest_bytes

    return read_db_at_rest_bytes(bucket_paths(tmp_path / "cadrumo-storage", _BUCKET_ID).database_file)


def _result(run_id: str, started: datetime) -> WorkflowResult:
    step = WorkflowStep(
        stage=WorkflowStage.LOADING_PROFILE,
        started_at=started,
        ended_at=started,
        success=True,
        summary_locale_key="application.workflow.steps.profile_loaded",
    )
    return WorkflowResult(
        run_id=run_id,
        started_at=started,
        ended_at=started,
        final_stage=WorkflowStage.DONE,
        aborted_reason=None,
        steps=(step,),
        summary_locale_key="application.workflow.results.completed",
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
        assert b"application.workflow.steps.profile_loaded" not in raw

    def test_load_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(WorkflowError) as excinfo:
            load_run("missing")
        assert excinfo.value.translated_message == "application.workflow.errors.run_not_found"

    def test_load_rejects_traversal_id(self, tmp_path: Path) -> None:
        with pytest.raises(WorkflowError) as excinfo:
            load_run("../escape")
        assert excinfo.value.translated_message == "application.workflow.errors.run_id_invalid_separators"

    def test_save_rejects_traversal_id(self, tmp_path: Path) -> None:
        escaped = _result("a" * 16, datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)).model_copy(
            update={"run_id": "../escape"},
        )
        with pytest.raises(WorkflowError) as excinfo:
            save_run(escaped, runs_dir=tmp_path)
        assert excinfo.value.translated_message == "application.workflow.errors.run_id_invalid_separators"

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
        runs_dir = tmp_path / "probe-runs"
        runs_dir.mkdir()
        result = _result("c" * 16, datetime(2026, 4, 13, tzinfo=UTC))
        save_run(result, runs_dir=runs_dir)
        assert scan_directory(runs_dir) == ()


class _EmitError(RuntimeError):
    """Real exception injected to simulate a downstream emit failure."""


def test_reset_workflow_state_emit_failure_leaves_row_intact() -> None:
    """When event emit fails, the secure-object row must remain present.

    The reset routine emits the ``workflow_state.reset`` event before
    discarding the secure-object row. If the emit raises, the delete
    must not execute -- the row stays, the next reset attempt picks
    up where this one left off, and no plaintext is leaked. The
    failure path is exercised by injecting a real failing emitter
    through the repository's ``emit_reset`` constructor argument.
    """

    from ....adapters.persistence.storage import WORKFLOW_STATE_NAMESPACE
    from ..persistence import WorkflowStateRepository
    from ..state_models import WorkflowState

    def _raise(**_: object) -> None:
        raise _EmitError("simulated downstream emit failure")

    repository = WorkflowStateRepository(emit_reset=_raise)
    repository.save(WorkflowState())
    assert repository._objects.exists(
        WORKFLOW_STATE_NAMESPACE.namespace,
        WORKFLOW_STATE_NAMESPACE.require_default_object_key(),
    )

    with pytest.raises(_EmitError):
        repository.reset_workflow_state()

    assert repository._objects.exists(
        WORKFLOW_STATE_NAMESPACE.namespace,
        WORKFLOW_STATE_NAMESPACE.require_default_object_key(),
    ), (
        "emit-first contract violated: secure-object row was deleted before the "
        "audit event landed; the recovery route lost its trail."
    )


def test_fingerprint_state_classifies_healthy_envelope_as_readable() -> None:
    """A freshly-persisted, decryptable state envelope fingerprints as ``readable``.

    The dry-run preview of ``repair reset-progress`` must never slander a
    sound envelope as ``unreadable``: on a fresh storage root the
    operator has only just written a healthy state, so the
    classification must reflect that.
    """

    from ..persistence import WorkflowStateRepository
    from ..state_models import WorkflowState

    repository = WorkflowStateRepository()
    repository.save(WorkflowState())

    fingerprint = repository.fingerprint_state()

    assert fingerprint.reason_class == "readable"
    assert fingerprint.byte_length is not None and fingerprint.byte_length > 0
    assert fingerprint.schema_version == 1


def test_fingerprint_state_classifies_absent_envelope_as_absent() -> None:
    """With no state envelope persisted the fingerprint classifies as ``absent``."""

    from ..persistence import WorkflowStateRepository

    fingerprint = WorkflowStateRepository().fingerprint_state()

    assert fingerprint.reason_class == "absent"
    assert fingerprint.byte_length is None
    assert fingerprint.schema_version is None


def test_fingerprint_state_honours_explicit_reason_class_override() -> None:
    """An explicit ``reason_class`` from a caller that knows the trigger wins."""

    from ..persistence import WorkflowStateRepository
    from ..state_models import WorkflowState

    repository = WorkflowStateRepository()
    repository.save(WorkflowState())

    fingerprint = repository.fingerprint_state(reason_class="caller-supplied")

    assert fingerprint.reason_class == "caller-supplied"
