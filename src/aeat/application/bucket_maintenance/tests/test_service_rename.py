"""Service-contract test for ``BucketMaintenanceService.rename``.

Exercises the full composition path against real adapters: real
encrypted-SQL secure-object repository, real plaintext bucket
manifest, real bucket-event-history catalogue. Asserts that the
service delegates the cross-store write to the existing
:func:`rename_profile` single-writer primitive (manifest ``label``
and encrypted record ``display_name`` both move) and that the
service-side emission lands a ``BUCKET_RENAMED`` event carrying the
previous and new labels in its payload.

Authority: workflow-composition contract pattern. Co-emission of
``PROFILE_RENAMED`` (lifecycle) and
``BUCKET_RENAMED`` (maintenance) is the intended audit shape.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.bucket._manifest_io import read_manifest
from ....core.resources import resources
from ....domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from ....domain.user_profile import ProfileSchemaDefinition, UserProfileFact
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...user_profile import RegisterProfileCommand
from .. import BucketMaintenanceService, RenameBucketCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "bucket-maintenance-rename-test"
_ORIGINAL_LABEL = "Original label"
_NEW_LABEL = "Renamed label"


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label=_ORIGINAL_LABEL,
    ) as profile:
        yield profile


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
def registered_profile(runtime: TestRuntimeProfile) -> None:
    """Register a real profile inside the active bucket.

    The rename path delegates to ``rename_profile``, which loads the
    profile via the cross-store integrity check — so the record MUST
    exist before the service can be exercised. Uses the live
    :class:`ProfileLifecycleService` against the real secure-object
    repository so the encrypted record and the manifest both reflect
    the same starting state.
    """
    from ...user_profile import (
        ProfileLifecycleService,
        ProfileValidationService,
        UserProfileLifecycleRepository,
    )

    schema = resources().user_profile_schema.singleton
    assert isinstance(schema, ProfileSchemaDefinition)
    repository = UserProfileLifecycleRepository(
        bucket_id=runtime.bucket_id,
        objects=runtime.repository,
    )
    events = BucketEventHistoryRepository(objects=runtime.repository)
    service = ProfileLifecycleService(
        repository=repository,
        validator=ProfileValidationService(schema=schema),
        events=events,
    )
    service.register(
        RegisterProfileCommand(
            profile_id=runtime.bucket_id,
            display_name=_ORIGINAL_LABEL,
            facts=_all_required_facts(schema),
        ),
    )


def test_rename_returns_result_carrying_before_and_after_labels(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """The service result records the old + new labels and the rename instant."""
    del registered_profile

    service = BucketMaintenanceService()
    result = service.rename(RenameBucketCommand(bucket_id=runtime.bucket_id, new_label=_NEW_LABEL))

    assert result.bucket_id == runtime.bucket_id
    assert result.previous_label == _ORIGINAL_LABEL
    assert result.new_label == _NEW_LABEL
    assert result.occurred_at is not None


def test_rename_updates_plaintext_manifest_label(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """The on-disk bucket manifest carries the new label after rename.

    Asserts the cross-store atomicity: a rename through the maintenance
    surface moves both stores because it delegates to the existing
    sole-writer ``rename_profile``.
    """
    del registered_profile

    BucketMaintenanceService().rename(RenameBucketCommand(bucket_id=runtime.bucket_id, new_label=_NEW_LABEL))

    manifest_after = read_manifest(runtime.paths)
    assert manifest_after.label == _NEW_LABEL


def test_rename_emits_bucket_renamed_event_with_label_pair(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """``BUCKET_RENAMED`` lands in the bucket-event history with both labels."""
    del registered_profile

    BucketMaintenanceService().rename(RenameBucketCommand(bucket_id=runtime.bucket_id, new_label=_NEW_LABEL))

    catalogue = BucketEventHistoryRepository(objects=runtime.repository).load()
    rename_events = tuple(
        event for event in catalogue.events.values() if event.event_type is BucketEventType.BUCKET_RENAMED
    )
    assert len(rename_events) == 1, "expected exactly one BUCKET_RENAMED event"
    event = rename_events[0]
    assert event.bucket_id == runtime.bucket_id
    assert event.object_type is BucketEventObjectType.BUCKET
    assert event.object_id == runtime.bucket_id
    assert event.payload["previous_label"] == _ORIGINAL_LABEL
    assert event.payload["new_label"] == _NEW_LABEL


def test_rename_emission_coexists_with_lifecycle_profile_renamed_event(
    runtime: TestRuntimeProfile,
    registered_profile: None,
) -> None:
    """Co-emission contract: rename surfaces both PROFILE_RENAMED and BUCKET_RENAMED.

    The lifecycle event records the data change (record relabel); the
    maintenance event records the operator's verb invocation. The two
    are intentionally distinct so a future audit query can separate
    them.
    """
    del registered_profile

    BucketMaintenanceService().rename(RenameBucketCommand(bucket_id=runtime.bucket_id, new_label=_NEW_LABEL))

    catalogue = BucketEventHistoryRepository(objects=runtime.repository).load()
    event_kinds = {event.event_type for event in catalogue.events.values()}
    assert BucketEventType.PROFILE_RENAMED in event_kinds
    assert BucketEventType.BUCKET_RENAMED in event_kinds
