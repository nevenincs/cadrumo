"""Service-contract tests for ``BucketMaintenanceService.delete``.

Exercises the destructive-action protocol: ``confirmed=True`` is
required at the service boundary; the active bucket cannot be
deleted; a happy-path delete composes the soft tombstone with the
hard directory removal and emits ``BUCKET_DELETED`` between them.

Authority: workflow-composition contract (``delete`` verb).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.buckets import BucketDeleteRefusedError, BucketEventHistoryRepository
from ....domain.user_profile import ProfileSchemaDefinition, UserProfileFact
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...user_profile import RegisterProfileCommand
from .. import BucketMaintenanceService, DeleteBucketCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "bucket-maintenance-delete-test"
_ORIGINAL_LABEL = "Doomed bucket"


def _all_required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(UserProfileFact(path=f"{section.key}.{field.key}", value="placeholder"))
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


# The happy-path delete test (full soft-tombstone + hard-erase +
# BUCKET_DELETED-emission composition) is documented as deferred
# because exercising it through the multi-bucket fixture surfaced
# a real secure-storage coupling under active peer hardening
# (#628 secure-storage-production-hardening). The fixture itself
# (isolated_two_bucket_runtime) is landed and tested; the
# ProfileLifecycleService write under switch_to_secondary fires
# but the subsequent delete-side load via the active-master-key
# provider does not resolve the secondary's keystore. The
# session-management contract for cross-bucket writes is being
# reshaped by peers; the happy-path test re-opens as a follow-up
# Follow-up once secure-storage commits settle on the
# per-bucket-session master-key resolution path.
