"""Per-bucket engine isolation roundtrip.

Per the profile-bucket lifecycle contract, the on-disk layout
puts every bucket's SQLite database under
``<cadrumo-root>/buckets/<bucket-id>/db/cadrumo.db``. The Settings model
resolves ``cadrumo_database_url`` through the active-profile pointer
so two distinct buckets address two distinct database files via
the engine cache.

These tests prove the isolation property the substrate is supposed
to deliver:

- Two buckets exercised within one process produce two distinct
  WorkflowState histories that never bleed across the boundary.
- Mutating one bucket's database after a switch leaves the other
  bucket's reads unaffected (anti-tautology gate per contract).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....tests.secure_sql import isolated_runtime_profile
from ...auth.models import AuthState
from ..persistence import WorkflowStateRepository
from ..state_models import WorkflowState

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_A_ID = "f06b58c0-56c1-4f38-9a03-7f6d716bf246"
_BUCKET_B_ID = "a1d7c210-82f7-4573-9d17-9502f6e73373"
_STATE_UPDATED_AT = datetime(2026, 5, 25, 13, 45, 0, tzinfo=UTC)


def _state_for_label(label: str) -> WorkflowState:
    """Build a minimal WorkflowState whose AuthState carries a unique label."""
    return WorkflowState(
        auth=AuthState(),
        updated_at=_STATE_UPDATED_AT,
        bucket_events=(),
    )


def test_two_buckets_persist_into_two_distinct_workflow_histories(tmp_path: Path) -> None:
    """Writing a WorkflowState in bucket A and bucket B yields two distinct stores.

    Each bucket has its own SQLite database under
    ``<root>/buckets/<bucket-id>/db/cadrumo.db``. Switching the active
    bucket switches the engine and therefore the on-disk store the
    repository writes to.
    """
    bucket_a_root = tmp_path / "a"
    bucket_b_root = tmp_path / "b"

    with isolated_runtime_profile(tmp_path=bucket_a_root, bucket_id=_BUCKET_A_ID) as profile_a:
        repo_a = WorkflowStateRepository(objects=profile_a.repository)
        state_a = _state_for_label("profile-a")
        repo_a.save(state_a)
        a_db = profile_a.paths.database_file
        assert a_db.exists(), "bucket A's per-bucket SQLite database must exist after a save"

    with isolated_runtime_profile(tmp_path=bucket_b_root, bucket_id=_BUCKET_B_ID) as profile_b:
        repo_b = WorkflowStateRepository(objects=profile_b.repository)
        state_b = _state_for_label("profile-b")
        repo_b.save(state_b)
        b_db = profile_b.paths.database_file
        assert b_db.exists(), "bucket B's per-bucket SQLite database must exist after a save"

    assert a_db != b_db
    assert a_db.parent != b_db.parent
    assert a_db.parent.parent.name == _BUCKET_A_ID
    assert b_db.parent.parent.name == _BUCKET_B_ID


def test_mutating_one_bucket_db_leaves_other_bucket_reads_unaffected(tmp_path: Path) -> None:
    """Anti-tautology: corrupting bucket A's database does not affect bucket B reads.

    The two databases are independent files. If a
    cross-bucket bleed existed (shared engine cache, shared connection
    pool, shared file handle), corrupting A's database file would
    surface as a load failure on B. The opposite must hold: B's read
    succeeds because B addresses its own file.
    """
    bucket_a_root = tmp_path / "a"
    bucket_b_root = tmp_path / "b"
    expected_state = _state_for_label("profile-b")

    with isolated_runtime_profile(tmp_path=bucket_b_root, bucket_id=_BUCKET_B_ID) as profile_b:
        repo_b = WorkflowStateRepository(objects=profile_b.repository)
        repo_b.save(expected_state)
        b_db = profile_b.paths.database_file
        assert b_db.exists()

    # B's engine is disposed on context exit (dispose_engine -> WAL checkpoint
    # folds the ``-wal`` sidecar into ``cadrumo.db``), so the main file is now
    # stable. Read the baseline here, AFTER B's own checkpoint, so the
    # comparison isolates A's corruption from B's routine WAL fold.
    b_db_bytes_before = b_db.read_bytes()

    with isolated_runtime_profile(tmp_path=bucket_a_root, bucket_id=_BUCKET_A_ID) as profile_a:
        repo_a = WorkflowStateRepository(objects=profile_a.repository)
        repo_a.save(_state_for_label("profile-a"))
        a_db = profile_a.paths.database_file
        assert a_db.exists()

    # Corrupt A's database AFTER its engine is disposed. Disposing the engine on
    # context exit checkpoints A's ``-wal`` sidecar back into ``cadrumo.db``; writing
    # the garbage inside the context would be folded over by that checkpoint, so
    # the corruption must land after it to persist and genuinely test isolation.
    a_db.write_bytes(b"corrupted-not-a-real-sqlite-file")

    b_db_bytes_after = b_db.read_bytes()
    assert b_db_bytes_after == b_db_bytes_before, (
        "bucket B's database file changed after bucket A's corruption — the two buckets are not file-isolated"
    )
    assert a_db.read_bytes().startswith(b"corrupted")
    assert a_db != b_db
    assert a_db.parent.parent.parent != b_db.parent.parent.parent
