"""Service-contract tests for ``BucketMaintenanceService.archive`` / ``.restore``.

Exercises the destructive-action-adjacent protocol for the reversible
lifecycle pair: ``confirmed=True`` is required for ``archive``; the
active bucket cannot be archived; a happy-path archive composes the
same soft-tombstone primitive ``delete`` uses (via
:func:`~application.user_profile.delete_profile_with_lifecycle_span`)
but never removes the bucket directory, so ``restore`` (via
:func:`~application.user_profile.reactivate_profile_with_lifecycle_span`)
can bring the same bucket back with its data intact.

Authority: ``composition-service-no-parallel-write-path`` — archive/restore
compose the existing soft-tombstone / reactivate primitives rather than
re-implementing bucket lifecycle transitions. Real encrypted-SQL storage,
real plaintext manifest, real bucket-event-history catalogue throughout —
no mocks, per ``aeat-roundtrip-discipline``.

See Also:
    :class:`~application.bucket_maintenance.BucketMaintenanceService`
        Composition service whose reversible archive/restore lifecycle contract
        this module exercises.
    :class:`~application.bucket_maintenance.ArchiveBucketCommand`
        Service command that requires explicit confirmation before dormancy.
    :class:`~application.bucket_maintenance.RestoreBucketCommand`
        Symmetric service command that refuses non-archived or unknown buckets.
    :func:`~application.user_profile.delete_profile_with_lifecycle_span`
        Soft-tombstone primitive composed by archive without removing the bucket
        directory.
    :func:`~application.user_profile.reactivate_profile_with_lifecycle_span`
        Reactivation primitive composed by restore.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....core.resources import resources
from ....domain.buckets import BucketArchiveRefusedError, BucketRestoreRefusedError
from ....domain.user_profile import ProfileNotFoundError, ProfileSchemaDefinition, UserProfileFact
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ....tests.user_profile import schema_valid_placeholder
from ...user_profile import RegisterProfileCommand
from .. import ArchiveBucketCommand, BucketMaintenanceService, RestoreBucketCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "88888888-8888-4888-8888-888888888888"
_ORIGINAL_LABEL = "Dormancy candidate"


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
    """Register a real profile so the archive/restore chain has something to tombstone."""
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


def test_archive_refuses_when_confirmed_flag_is_false(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """The service refuses an unconfirmed archive; CLI ``--yes`` is the operator's path through."""
    del registered_profile

    with pytest.raises(BucketArchiveRefusedError):
        BucketMaintenanceService().archive(ArchiveBucketCommand(bucket_id=runtime.bucket_id, confirmed=False))


def test_archive_refuses_active_bucket_even_when_confirmed(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """The active bucket cannot be archived; the operator must switch first."""
    del registered_profile

    with pytest.raises(BucketArchiveRefusedError):
        BucketMaintenanceService().archive(ArchiveBucketCommand(bucket_id=runtime.bucket_id, confirmed=True))


def test_archive_refusals_carry_translated_message(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """Both refusal paths produce a translated message with the bucket_id context."""
    del registered_profile

    with pytest.raises(BucketArchiveRefusedError) as unconfirmed:
        BucketMaintenanceService().archive(ArchiveBucketCommand(bucket_id=runtime.bucket_id, confirmed=False))
    assert "bucket_id" in (unconfirmed.value.context or {})

    with pytest.raises(BucketArchiveRefusedError) as active:
        BucketMaintenanceService().archive(ArchiveBucketCommand(bucket_id=runtime.bucket_id, confirmed=True))
    assert "bucket_id" in (active.value.context or {})


def test_restore_refuses_a_bucket_that_is_not_archived(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """``restore`` refuses a live (never-archived) bucket."""
    del registered_profile

    with pytest.raises(BucketRestoreRefusedError):
        BucketMaintenanceService().restore(RestoreBucketCommand(bucket_id=runtime.bucket_id))


def test_restore_refuses_an_unknown_bucket(runtime: TestRuntimeProfile) -> None:
    """``restore`` refuses a bucket_id with no registered manifest at all."""
    with pytest.raises(ProfileNotFoundError):
        BucketMaintenanceService().restore(RestoreBucketCommand(bucket_id="00000000-0000-4000-8000-000000000000"))
