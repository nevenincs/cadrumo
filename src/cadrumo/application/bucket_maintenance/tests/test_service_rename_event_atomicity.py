"""Real-behavior tests: a rename and its audit event land together or not at all.

The maintenance rename delegated the relabel to ``rename_profile``, which
commits the record and ``PROFILE_RENAMED``, and only then saved
``BUCKET_RENAMED`` through a second write. A failure in that second write
left the label moved, the lifecycle events emitted, and no maintenance
event -- an audit trail silently missing the verb that changed the name,
with nothing marking the gap for a retry.

The event now rides the record's unit of work through the ``extra_events``
seam, which is the co-emission shape ``build_bucket_event`` was split out to
support and that the modelo revision writer already uses.

The failure injected here is a real refusal from the append contract: a
catalogue that already holds the derived id under a different
``payload_version`` refuses rather than overwriting. Nothing is patched or
stubbed -- the repositories, the encryption, and the SQLite backend are real.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core.time import frozen_clock
from ....domain.buckets import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    BucketEventValidationError,
    append_bucket_event,
    build_bucket_event,
)
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...user_profile import (
    ProfileRepository,
    profile_create_storage_span,
    profile_storage_session,
)
from ...workflow import workflow_state_repository
from .._contracts import RenameBucketCommand
from .._service import BucketMaintenanceService

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_ORIGINAL_LABEL = "original-label"
_NEW_LABEL = "renamed-label"
_TAX_ID = "12345678Z"
# The event id derives from occurred_at, so the collision below is only
# reachable when the seeded event and the rename share an instant. frozen_clock
# is the project's own replay seam on core.time.now, not a patched clock.
#
# The instant is in the future rather than the past: the record's created_at is
# the real clock at fixture time, and the lifecycle invariant requires
# created_at <= updated_at, so freezing backwards refuses for a reason that has
# nothing to do with the seam under test.
_INSTANT = datetime(2030, 1, 1, 10, 0, 0, tzinfo=UTC)


def _event_repository():
    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository

    return BucketEventHistoryRepository()


def _events_of(event_type: BucketEventType) -> tuple[BucketEvent, ...]:
    with profile_storage_session(_BUCKET_ID):
        catalogue = _event_repository().load()
        return tuple(e for e in catalogue if e.event_type is event_type)


def _current_label() -> str:
    with profile_storage_session(_BUCKET_ID):
        return ProfileRepository().load(_BUCKET_ID).record.display_name


def _poison_the_maintenance_event() -> None:
    """Seed the catalogue so the rename's BUCKET_RENAMED append must refuse.

    The rename derives its event id from the bucket, verb, instant, actor and
    payload. Pre-seeding an event that will collide on id but carry a
    different payload_version makes the append refuse mid-transaction, which
    is the real production refusal rather than an injected exception.
    """
    with profile_storage_session(_BUCKET_ID):
        repository = _event_repository()
        colliding = build_bucket_event(
            bucket_id=_BUCKET_ID,
            event_type=BucketEventType.BUCKET_RENAMED,
            occurred_at=_INSTANT,
            actor="bucket-maintenance",
            object_type=BucketEventObjectType.BUCKET,
            object_id=_BUCKET_ID,
            payload={"previous_label": _ORIGINAL_LABEL, "new_label": _NEW_LABEL},
            payload_version=99,
        )
        repository.save(append_bucket_event(repository.load(), colliding))


def test_a_successful_rename_commits_the_label_and_both_events() -> None:
    BucketMaintenanceService().rename(
        RenameBucketCommand(bucket_id=_BUCKET_ID, new_label=_NEW_LABEL),
    )

    assert _current_label() == _NEW_LABEL
    assert len(_events_of(BucketEventType.BUCKET_RENAMED)) == 1
    assert len(_events_of(BucketEventType.PROFILE_RENAMED)) == 1


def test_a_failed_maintenance_event_leaves_the_label_unchanged() -> None:
    """The seam this closes: the label must not move without its audit event."""
    _poison_the_maintenance_event()

    with pytest.raises(BucketEventValidationError), frozen_clock(_INSTANT):
        BucketMaintenanceService().rename(
            RenameBucketCommand(bucket_id=_BUCKET_ID, new_label=_NEW_LABEL),
        )

    assert _current_label() == _ORIGINAL_LABEL


def test_a_failed_maintenance_event_leaves_no_lifecycle_event_either() -> None:
    """Both events ride the record write, so neither survives a refused batch."""
    _poison_the_maintenance_event()

    with pytest.raises(BucketEventValidationError), frozen_clock(_INSTANT):
        BucketMaintenanceService().rename(
            RenameBucketCommand(bucket_id=_BUCKET_ID, new_label=_NEW_LABEL),
        )

    assert _events_of(BucketEventType.PROFILE_RENAMED) == ()


def test_the_two_events_remain_distinct_records() -> None:
    """Co-emission must not collapse the data change and the verb invocation."""
    BucketMaintenanceService().rename(
        RenameBucketCommand(bucket_id=_BUCKET_ID, new_label=_NEW_LABEL),
    )

    bucket_events = _events_of(BucketEventType.BUCKET_RENAMED)
    profile_events = _events_of(BucketEventType.PROFILE_RENAMED)

    assert len(bucket_events) == 1
    assert len(profile_events) == 1
    assert bucket_events[0].event_id != profile_events[0].event_id


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id=_BUCKET_ID,
                display_name=_ORIGINAL_LABEL,
                overrides={"identity.tax_id": _TAX_ID},
            ),
        )
        yield
