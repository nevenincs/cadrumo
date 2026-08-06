"""Service-contract tests for ``BucketMaintenanceService.delete``.

Exercises the destructive-action protocol: ``confirmed=True`` is
required at the service boundary; the active bucket cannot be
deleted; a happy-path delete composes the soft tombstone with the
hard directory removal and emits ``BUCKET_DELETED`` between them.

Authority: workflow-composition contract (``delete`` verb).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....core.resources import resources
from ....domain.buckets import BucketDeleteRefusedError
from ....domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    UserProfileFact,
    UserProfileStatus,
)
from ....tests.secure_sql import (
    MultiBucketTestRuntime,
    TestRuntimeProfile,
    isolated_runtime_profile,
    isolated_two_bucket_runtime,
)
from ....tests.user_profile import schema_valid_placeholder
from ..._config_reset_models import (
    ConfigResetDeletionMarker,
    ConfigResetOperation,
    ConfigResetPointerSnapshot,
    ConfigResetRetentionDecision,
    ConfigResetTarget,
    ConfigResetTargetPhase,
)
from ..._config_reset_repository import ConfigResetJournalRepository
from ...user_profile import RegisterProfileCommand
from .. import (
    AssessBucketDeletionCommand,
    BucketDeletionAssessment,
    BucketDeletionFingerprint,
    BucketMaintenanceService,
    DeleteBucketCommand,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "44444444-4444-4444-8444-444444444444"
_ORIGINAL_LABEL = "Doomed bucket"
_RESET_OPERATION_ID = "a" * 64


def _all_required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(UserProfileFact(path=f"{section.key}.{field.key}", value=schema_valid_placeholder(field)))
    return tuple(facts)


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label=_ORIGINAL_LABEL,
    ) as profile:
        yield profile


@pytest.fixture
def registered_profile(runtime: TestRuntimeProfile) -> None:
    """Register a real profile so the delete chain has something to tombstone."""
    from ...user_profile import (
        ProfileLifecycleService,
        ProfileValidationService,
        UserProfileLifecycleRepository,
    )

    schema = resources().user_profile_schema.singleton
    assert isinstance(schema, ProfileSchemaDefinition)
    service = ProfileLifecycleService(
        repository=UserProfileLifecycleRepository(
            bucket_id=runtime.bucket_id,
            objects=runtime.repository,
        ),
        validator=ProfileValidationService(schema=schema),
        events=BucketEventHistoryRepository(objects=runtime.repository),
    )
    service.register(
        RegisterProfileCommand(
            profile_id=runtime.bucket_id,
            display_name=_ORIGINAL_LABEL,
            facts=_all_required_facts(schema),
        ),
    )


def test_delete_refuses_when_confirmed_flag_is_false(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """The service refuses an unconfirmed delete; CLI ``--yes`` is the operator's path through."""
    del registered_profile

    with pytest.raises(BucketDeleteRefusedError):
        BucketMaintenanceService().delete(DeleteBucketCommand(bucket_id=runtime.bucket_id, confirmed=False))


def test_delete_refuses_active_bucket_even_when_confirmed(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """The active bucket cannot be deleted; the operator must switch first."""
    del registered_profile

    with pytest.raises(BucketDeleteRefusedError):
        BucketMaintenanceService().delete(DeleteBucketCommand(bucket_id=runtime.bucket_id, confirmed=True))


def test_delete_refusals_carry_translated_message(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """Both refusal paths produce a translated message with the bucket_id context.

    The CLI surface renders these messages directly; a missing
    translation key would fall back to a developer-facing string and
    leak through to the operator.
    """
    del registered_profile

    with pytest.raises(BucketDeleteRefusedError) as unconfirmed:
        BucketMaintenanceService().delete(DeleteBucketCommand(bucket_id=runtime.bucket_id, confirmed=False))
    assert "bucket_id" in (unconfirmed.value.context or {})

    with pytest.raises(BucketDeleteRefusedError) as active:
        BucketMaintenanceService().delete(DeleteBucketCommand(bucket_id=runtime.bucket_id, confirmed=True))
    assert "bucket_id" in (active.value.context or {})


def _register_secondary_profile(runtime: MultiBucketTestRuntime) -> None:
    from ....adapters.persistence.storage.bucket import read_manifest
    from ...user_profile import (
        ProfileLifecycleService,
        ProfileValidationService,
        UserProfileLifecycleRepository,
    )

    schema = resources().user_profile_schema.singleton
    assert isinstance(schema, ProfileSchemaDefinition)
    with runtime.switch_to_secondary():
        ProfileLifecycleService(
            repository=UserProfileLifecycleRepository(
                bucket_id=runtime.secondary.bucket_id,
                objects=runtime.secondary.repository,
            ),
            validator=ProfileValidationService(schema=schema),
            events=BucketEventHistoryRepository(objects=runtime.secondary.repository),
        ).register(
            RegisterProfileCommand(
                profile_id=runtime.secondary.bucket_id,
                display_name=read_manifest(runtime.secondary.paths).label,
                facts=_all_required_facts(schema),
            ),
        )


def _persist_deleting_marker(
    assessment: BucketDeletionAssessment,
    *,
    operation_id: str = _RESET_OPERATION_ID,
) -> None:
    assert assessment.exists
    assert assessment.label is not None
    assert assessment.status is not None
    assert assessment.fingerprint is not None
    assert assessment.retention is not None
    recorded_at = datetime.now(UTC)
    retention = assessment.retention
    ConfigResetJournalRepository().create(
        ConfigResetOperation(
            operation_id=operation_id,
            started_at=recorded_at,
            updated_at=recorded_at,
            pointer_snapshot=ConfigResetPointerSnapshot(present=False),
            targets=(
                ConfigResetTarget(
                    bucket_id=assessment.bucket_id,
                    label=assessment.label,
                    status_at_snapshot=assessment.status,
                    exists_at_snapshot=True,
                    fingerprint=assessment.fingerprint,
                    phase=ConfigResetTargetPhase.DELETING,
                    retention=ConfigResetRetentionDecision(
                        assessed_at=retention.as_of,
                        blocks_erase=retention.blocks_erase,
                        retained_record_count=len(retention.retained),
                        latest_safe_erase_date=retention.latest_safe_erase_date,
                    ),
                    deletion_marker=ConfigResetDeletionMarker(
                        operation_id=operation_id,
                        bucket_id=assessment.bucket_id,
                        fingerprint=assessment.fingerprint.digest,
                        marked_at=recorded_at,
                    ),
                ),
            ),
        ),
    )


def test_operation_owned_delete_rejects_changed_fingerprint_without_mutation(
    tmp_path: Path,
) -> None:
    """A reset-owned delete cannot erase a target that changed after assessment."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        _register_secondary_profile(runtime)
        service = BucketMaintenanceService()
        assessment = service.assess_deletion(
            AssessBucketDeletionCommand(bucket_id=runtime.secondary.bucket_id),
        )
        assert assessment.fingerprint is not None
        _persist_deleting_marker(assessment)

        with pytest.raises(BucketDeleteRefusedError) as raised:
            service.delete(
                DeleteBucketCommand(
                    bucket_id=runtime.secondary.bucket_id,
                    confirmed=True,
                    reset_operation_id=_RESET_OPERATION_ID,
                    expected_deletion_fingerprint="f" * 64,
                ),
            )

        assert "expected_fingerprint" in (raised.value.context or {})
        assert runtime.secondary.paths.bucket_dir.is_dir()
        observed = service.assess_deletion(
            AssessBucketDeletionCommand(bucket_id=runtime.secondary.bucket_id),
        )
        assert observed.fingerprint == assessment.fingerprint


def test_linked_bucket_root_is_neither_assessed_nor_deleted(
    tmp_path: Path,
) -> None:
    """A redirected bucket root cannot turn external storage into a target."""
    from ....adapters.persistence.storage.bucket import manifest_path
    from ....adapters.persistence.storage.sql import dispose_engines_for_bucket

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        _register_secondary_profile(runtime)
        external_bucket = tmp_path / "external-target"
        dispose_engines_for_bucket(runtime.secondary.bucket_id)
        runtime.secondary.paths.bucket_dir.rename(external_bucket)
        runtime.secondary.paths.bucket_dir.symlink_to(
            external_bucket,
            target_is_directory=True,
        )
        external_manifest = manifest_path(
            runtime.secondary.paths.model_copy(update={"bucket_dir": external_bucket}),
        )
        manifest_before = external_manifest.read_bytes()
        sentinel = external_bucket / "external-sentinel.bin"
        sentinel.write_bytes(b"must-survive")

        service = BucketMaintenanceService()
        with pytest.raises(BucketDeleteRefusedError):
            service.assess_deletion(
                AssessBucketDeletionCommand(bucket_id=runtime.secondary.bucket_id),
            )
        with pytest.raises(BucketDeleteRefusedError):
            service.delete(
                DeleteBucketCommand(
                    bucket_id=runtime.secondary.bucket_id,
                    confirmed=True,
                ),
            )

        assert runtime.secondary.paths.bucket_dir.is_symlink()
        assert external_manifest.read_bytes() == manifest_before
        assert sentinel.read_bytes() == b"must-survive"


def test_operation_owned_delete_erases_matching_target(
    tmp_path: Path,
) -> None:
    """Matching journal ownership and fingerprint permit the canonical hard erase."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        _register_secondary_profile(runtime)
        service = BucketMaintenanceService()
        assessment = service.assess_deletion(
            AssessBucketDeletionCommand(bucket_id=runtime.secondary.bucket_id),
        )
        assert assessment.fingerprint is not None
        _persist_deleting_marker(assessment)

        from ....core import clear_pointer
        from ....core.config import load_settings

        clear_pointer(load_settings().cadrumo_local_storage_root)

        result = service.delete(
            DeleteBucketCommand(
                bucket_id=runtime.secondary.bucket_id,
                confirmed=True,
                reset_operation_id=_RESET_OPERATION_ID,
                expected_deletion_fingerprint=assessment.fingerprint.digest,
            ),
        )

        assert result.already_absent is False
        assert result.reset_operation_id == _RESET_OPERATION_ID
        assert result.deletion_fingerprint == assessment.fingerprint.digest
        assert runtime.secondary.paths.bucket_dir.exists() is False


def test_absence_requires_journal_proof_and_then_is_idempotently_accepted(
    tmp_path: Path,
) -> None:
    """Generic absence remains an error; an owned deleting marker can prove completion."""
    missing_bucket_id = "66666666-6666-4666-8666-666666666666"
    expected_fingerprint = "b" * 64
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label=_ORIGINAL_LABEL):
        service = BucketMaintenanceService()
        with pytest.raises(ProfileNotFoundError):
            service.delete(
                DeleteBucketCommand(
                    bucket_id=missing_bucket_id,
                    confirmed=True,
                ),
            )

        with pytest.raises(BucketDeleteRefusedError):
            service.delete(
                DeleteBucketCommand(
                    bucket_id=missing_bucket_id,
                    confirmed=True,
                    reset_operation_id=_RESET_OPERATION_ID,
                    expected_deletion_fingerprint=expected_fingerprint,
                ),
            )

        recorded_at = datetime.now(UTC)
        fingerprint = BucketDeletionFingerprint(
            digest=expected_fingerprint,
            manifest_digest="c" * 64,
            file_count=1,
            total_bytes=1,
        )
        ConfigResetJournalRepository().create(
            ConfigResetOperation(
                operation_id=_RESET_OPERATION_ID,
                started_at=recorded_at,
                updated_at=recorded_at,
                pointer_snapshot=ConfigResetPointerSnapshot(present=False),
                targets=(
                    ConfigResetTarget(
                        bucket_id=missing_bucket_id,
                        label="Former bucket",
                        status_at_snapshot=UserProfileStatus.ACTIVE,
                        exists_at_snapshot=True,
                        fingerprint=fingerprint,
                        phase=ConfigResetTargetPhase.DELETING,
                        retention=ConfigResetRetentionDecision(
                            assessed_at=recorded_at,
                            blocks_erase=False,
                            retained_record_count=0,
                        ),
                        deletion_marker=ConfigResetDeletionMarker(
                            operation_id=_RESET_OPERATION_ID,
                            bucket_id=missing_bucket_id,
                            fingerprint=expected_fingerprint,
                            marked_at=recorded_at,
                        ),
                    ),
                ),
            ),
        )

        result = service.delete(
            DeleteBucketCommand(
                bucket_id=missing_bucket_id,
                confirmed=True,
                reset_operation_id=_RESET_OPERATION_ID,
                expected_deletion_fingerprint=expected_fingerprint,
            ),
        )

        assert result.already_absent is True
        assert result.previous_label is None
        assert result.deletion_fingerprint == expected_fingerprint
        assert result.reset_operation_id == _RESET_OPERATION_ID
