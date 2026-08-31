"""Real-filesystem tests for durable secret-free config-reset journals."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError

from ...adapters.persistence.storage.bucket._layout import bucket_paths
from ...core.bucket_pointer import BucketPointer
from ...core.directory_scan import scan_directory
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_location
from ...domain.user_profile.values import ProfileSetupState
from .._bucket_deletion_contracts import BucketDeletionFingerprint
from .._config_reset_models import (
    ConfigResetDeletionMarker,
    ConfigResetOperation,
    ConfigResetOperationStatus,
    ConfigResetPauseReason,
    ConfigResetPointerSnapshot,
    ConfigResetRetentionDecision,
    ConfigResetSummary,
    ConfigResetTarget,
    ConfigResetTargetPhase,
)
from .._config_reset_repository import (
    ConfigResetJournalAlreadyExistsError,
    ConfigResetJournalCorruptError,
    ConfigResetJournalError,
    ConfigResetJournalRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"reset-operations"})
"""Taxonomy-vocabulary literals this module deliberately pins.

Both sites test the repository's own resolution behaviour: one composes the
expected value independently to prove ``path_for`` resolves under the real
segment name, and the other plants a symlink at that exact real location to
prove a redirected root cannot smuggle operation bytes into a bucket -- the
literal has to name the real segment for that attack to be meaningful.
"""


_OPERATION_ID = "c" * 64
_BUCKET_ID = "77777777-7777-4777-8777-777777777777"


def _operation(*, updated_offset: int = 0) -> ConfigResetOperation:
    started_at = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
    return ConfigResetOperation(
        operation_id=_OPERATION_ID,
        status=ConfigResetOperationStatus.INCOMPLETE,
        started_at=started_at,
        updated_at=started_at + timedelta(seconds=updated_offset),
        pointer_snapshot=ConfigResetPointerSnapshot(record=BucketPointer.absent(transition_revision=0)),
        targets=(
            ConfigResetTarget(
                bucket_id=_BUCKET_ID,
                exists_at_snapshot=False,
            ),
        ),
    )


def test_create_roundtrips_atomically_with_restrictive_permissions(
    tmp_path: Path,
) -> None:
    """A complete journal document lands outside buckets with no staged residue."""
    repository = ConfigResetJournalRepository(storage_root=tmp_path)
    operation = _operation()

    repository.create(operation)

    path = repository.path_for(operation.operation_id)
    assert repository.load(operation.operation_id) == operation
    assert repository.list() == (operation,)
    assert path.parent == tmp_path / "reset-operations"
    assert tmp_path / storage_location(StorageCategory.BUCKETS).subpath not in path.parents
    assert scan_directory(path.parent, pattern="*.tmp") == ()
    if os.name != "nt":
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_create_refuses_existing_operation_identity(
    tmp_path: Path,
) -> None:
    """Create never replaces a journal that already owns the operation id."""
    repository = ConfigResetJournalRepository(storage_root=tmp_path)
    operation = _operation()
    repository.create(operation)

    with pytest.raises(ConfigResetJournalAlreadyExistsError):
        repository.create(operation.model_copy(update={"updated_at": operation.updated_at + timedelta(seconds=1)}))

    assert repository.load(operation.operation_id) == operation


def test_create_persists_canonical_bucket_identities(
    tmp_path: Path,
) -> None:
    """Every persisted reset identity uses the storage-wide canonical spelling."""
    repository = ConfigResetJournalRepository(storage_root=tmp_path)
    started_at = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
    wrapped_bucket_id = f" {_BUCKET_ID} "
    operation = ConfigResetOperation(
        operation_id=_OPERATION_ID,
        status=ConfigResetOperationStatus.PAUSED,
        started_at=started_at,
        updated_at=started_at,
        pointer_snapshot=ConfigResetPointerSnapshot(
            record=BucketPointer.selected(bucket_id=wrapped_bucket_id, transition_revision=0),
        ),
        targets=(
            ConfigResetTarget(
                bucket_id=wrapped_bucket_id,
                label="Canonical operator",
                setup_state_at_snapshot=ProfileSetupState.COMPLETE,
                exists_at_snapshot=True,
                fingerprint=BucketDeletionFingerprint(
                    digest="b" * 64,
                    file_count=1,
                    total_bytes=1,
                ),
                phase=ConfigResetTargetPhase.DELETING,
                retention=ConfigResetRetentionDecision(
                    assessed_at=started_at,
                    blocks_erase=False,
                    retained_record_count=0,
                ),
                deletion_marker=ConfigResetDeletionMarker(
                    operation_id=_OPERATION_ID,
                    bucket_id=wrapped_bucket_id,
                    fingerprint="b" * 64,
                    marked_at=started_at,
                ),
            ),
        ),
        pause_reason=ConfigResetPauseReason.TARGET_STATE_CHANGED,
        paused_target_ids=(wrapped_bucket_id,),
    )

    repository.create(operation)

    document = json.loads(repository.path_for(operation.operation_id).read_text(encoding="utf-8"))
    assert document["pointer_snapshot"]["record"]["selection"] == "selected"
    assert document["pointer_snapshot"]["record"]["bucket_id"] == _BUCKET_ID
    assert document["targets"][0]["bucket_id"] == _BUCKET_ID
    assert document["targets"][0]["deletion_marker"]["bucket_id"] == _BUCKET_ID
    assert document["paused_target_ids"] == [_BUCKET_ID]
    assert repository.load(operation.operation_id) == operation


def test_retention_decision_refuses_override_when_nothing_blocks_erase() -> None:
    """An override cannot be journaled when the assessment needs no override."""
    with pytest.raises(ValueError):
        ConfigResetRetentionDecision(
            assessed_at=datetime(2026, 7, 16, 8, 0, tzinfo=UTC),
            blocks_erase=False,
            retained_record_count=0,
            override_approved=True,
            override_reason="No blocking record exists.",
        )


def test_corrupt_and_filename_mismatched_journals_refuse(
    tmp_path: Path,
) -> None:
    """Malformed JSON and a payload copied under another id both fail closed."""
    repository = ConfigResetJournalRepository(storage_root=tmp_path)
    operation = _operation()
    repository.create(operation)
    path = repository.path_for(operation.operation_id)
    path.write_text('{"operation_id":', encoding="utf-8")

    with pytest.raises(ConfigResetJournalCorruptError):
        repository.load(operation.operation_id)

    repository.save(operation)
    other_id = "d" * 64
    repository.path_for(other_id).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ConfigResetJournalCorruptError):
        repository.load(other_id)


def test_noncurrent_schema_versions_are_refused_as_corrupt(
    tmp_path: Path,
) -> None:
    repository = ConfigResetJournalRepository(storage_root=tmp_path)
    operation = _operation()
    repository.create(operation)
    path = repository.path_for(operation.operation_id)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["schema_version"] = 1
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ConfigResetJournalCorruptError):
        repository.load(operation.operation_id)

    document["schema_version"] = 3
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ConfigResetJournalCorruptError):
        repository.load(operation.operation_id)


def test_complete_operation_requires_every_target_deleted() -> None:
    operation = _operation()

    with pytest.raises(ValidationError, match="every target to be deleted"):
        ConfigResetOperation(
            operation_id=operation.operation_id,
            status=ConfigResetOperationStatus.COMPLETE,
            started_at=operation.started_at,
            updated_at=operation.updated_at,
            pointer_snapshot=operation.pointer_snapshot,
            targets=operation.targets,
            summary=ConfigResetSummary(
                target_count=1,
                deleted_count=0,
                already_absent_count=1,
                retention_override_count=0,
                completed_at=operation.updated_at,
            ),
        )


def test_complete_operation_requires_exact_summary_counts() -> None:
    operation = _operation()
    target = ConfigResetTarget(
        bucket_id=_BUCKET_ID,
        exists_at_snapshot=False,
        phase=ConfigResetTargetPhase.DELETED,
        completed_at=operation.updated_at,
    )

    with pytest.raises(ValidationError, match="target count does not match"):
        ConfigResetOperation(
            operation_id=operation.operation_id,
            status=ConfigResetOperationStatus.COMPLETE,
            started_at=operation.started_at,
            updated_at=operation.updated_at,
            pointer_snapshot=operation.pointer_snapshot,
            targets=(target,),
            summary=ConfigResetSummary(
                target_count=2,
                deleted_count=0,
                already_absent_count=2,
                retention_override_count=0,
                completed_at=operation.updated_at,
            ),
        )


def test_repository_excludes_non_journals_and_bucket_discovery(
    tmp_path: Path,
) -> None:
    """External journal files are neither bucket targets nor repository members."""
    from ..workflow.profile_bucket_scan import list_profile_buckets

    repository = ConfigResetJournalRepository(storage_root=tmp_path)
    operation = _operation()
    repository.create(operation)
    (repository.root / "operator-note.txt").write_text("not a reset journal", encoding="utf-8")

    assert repository.list() == (operation,)
    assert list_profile_buckets(root=tmp_path) == {}


def test_repository_refuses_linked_root_redirected_into_bucket(
    tmp_path: Path,
) -> None:
    """A link-like journal root cannot redirect operation bytes into a target."""
    bucket_dir = bucket_paths(tmp_path, _BUCKET_ID).bucket_dir
    bucket_dir.mkdir(parents=True)
    linked_root = tmp_path / "reset-operations"
    linked_root.symlink_to(bucket_dir, target_is_directory=True)
    repository = ConfigResetJournalRepository(storage_root=tmp_path)

    with pytest.raises(ConfigResetJournalError):
        repository.create(_operation())

    assert scan_directory(bucket_dir, pattern="*.json") == ()


def test_concurrent_fresh_process_writers_leave_one_complete_document(
    tmp_path: Path,
) -> None:
    """Real child processes serialize replacement and never expose torn JSON."""
    repository = ConfigResetJournalRepository(storage_root=tmp_path)
    repository.create(_operation())
    script = (
        "from datetime import timedelta;"
        "from pathlib import Path;"
        "from cadrumo.application._config_reset_repository import ConfigResetJournalRepository;"
        "root=Path(__import__('sys').argv[1]);"
        "offset=int(__import__('sys').argv[2]);"
        "repo=ConfigResetJournalRepository(storage_root=root);"
        "op=repo.load('" + _OPERATION_ID + "');"
        "repo.save(op.model_copy(update={'updated_at':op.started_at+timedelta(seconds=offset)}))"
    )
    processes = [
        subprocess.Popen(  # noqa: S603 - fixed interpreter and repository-owned inline script
            [sys.executable, "-c", script, str(tmp_path), str(offset)],
            cwd=Path.cwd(),
        )
        for offset in range(1, 5)
    ]

    assert [process.wait(timeout=60) for process in processes] == [0, 0, 0, 0]
    loaded = repository.load(_OPERATION_ID)
    assert loaded.operation_id == _OPERATION_ID
    assert loaded.updated_at in {loaded.started_at + timedelta(seconds=offset) for offset in range(1, 5)}
    assert scan_directory(repository.root, pattern="*.tmp") == ()


def test_fresh_process_reloads_exact_journal(
    tmp_path: Path,
) -> None:
    """A new interpreter reads the same validated operation from disk."""
    repository = ConfigResetJournalRepository(storage_root=tmp_path)
    repository.create(_operation(updated_offset=7))
    script = (
        "from pathlib import Path;"
        "from cadrumo.application._config_reset_repository import ConfigResetJournalRepository;"
        "repo=ConfigResetJournalRepository(storage_root=Path(__import__('sys').argv[1]));"
        "op=repo.load(__import__('sys').argv[2]);"
        "print(op.model_dump_json())"
    )

    completed = subprocess.run(  # noqa: S603 - fixed interpreter and repository-owned inline script
        [sys.executable, "-c", script, str(tmp_path), _OPERATION_ID],
        cwd=Path.cwd(),
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert ConfigResetOperation.model_validate_json(completed.stdout) == _operation(updated_offset=7)
