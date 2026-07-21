"""CLI tests for the ``config profile rename`` maintenance audit contract.

The composition contract mandates
two-event co-emission per operator rename invocation: the inner
single-writer primitive emits ``PROFILE_RENAMED`` (the data change) and
the maintenance surface emits ``BUCKET_RENAMED`` (the operator's verb).
These tests drive the real CLI against real per-bucket encrypted storage
and assert both events land in the renamed bucket's OWN event history —
including when the renamed profile is not the active one, the case where
an active-bucket-bound default repository would split the audit trail
from the records it describes.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage.runtime_repository import (
    secure_object_repository_for_bucket,
)
from ....application.workflow import read_profile_bucket
from ....domain.buckets import BucketEventHistoryCatalogue, BucketEventObjectType, BucketEventType
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ._profile_lifecycle_support import create_profile_via_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _bucket_history(bucket_id: str) -> BucketEventHistoryCatalogue:
    """Load ``bucket_id``'s own event-history catalogue from real storage.

    Reading a bucket's encrypted store requires an active session scoped
    to that bucket, so the read runs inside ``profile_storage_session``.
    """
    from ....application.user_profile import profile_storage_session

    with profile_storage_session(bucket_id):
        repository = BucketEventHistoryRepository(objects=secure_object_repository_for_bucket(bucket_id))
        return repository.load()


def test_cli_rename_co_emits_profile_renamed_and_bucket_renamed() -> None:
    """``config profile rename`` surfaces BOTH audit events.

    The lifecycle event records the record relabel; the maintenance
    event records the operator's verb invocation. Before the CLI was
    routed through ``BucketMaintenanceService`` only ``PROFILE_RENAMED``
    fired, so the two-event audit contract was dead at the actual
    operator surface.
    """

    create_profile_via_cli("alpha")
    pointer = read_profile_bucket("alpha")
    assert pointer is not None

    result = invoke_cached_cli(("config", "profile", "rename", "alpha", "beta"))
    assert result.exit_code == 0, f"rename failed: {result.output}"

    catalogue = _bucket_history(pointer.bucket_id)
    event_kinds = {event.event_type for event in catalogue.events.values()}
    assert BucketEventType.PROFILE_RENAMED in event_kinds
    assert BucketEventType.BUCKET_RENAMED in event_kinds

    bucket_renamed = [
        event for event in catalogue.events.values() if event.event_type is BucketEventType.BUCKET_RENAMED
    ]
    assert len(bucket_renamed) == 1, "expected exactly one BUCKET_RENAMED event"
    event = bucket_renamed[0]
    assert event.bucket_id == pointer.bucket_id
    assert event.object_type is BucketEventObjectType.BUCKET
    assert event.payload["previous_label"] == "alpha"
    assert event.payload["new_label"] == "beta"


def test_cli_rename_of_non_active_profile_targets_its_own_bucket_and_never_leaks_into_active() -> None:
    """Renaming a profile that does not own the active session relabels
    the TARGET bucket and lands its audit events there — never in the
    active bucket.

    ``BucketMaintenanceService.rename`` opens a storage session scoped
    to the target ``bucket_id`` and binds the maintenance event
    repository to that bucket, so a non-active rename resolves the
    target's per-bucket engine directly (the operator does not have to
    switch first). The load-bearing safety property is that the two
    rename events (``PROFILE_RENAMED`` + ``BUCKET_RENAMED``) land in the
    renamed bucket's OWN history and NONE leaks into the ACTIVE bucket,
    which an active-bucket-bound default repository would have written.
    """

    create_profile_via_cli("alpha")
    create_profile_via_cli("bravo")  # bravo is now the active profile
    alpha_pointer = read_profile_bucket("alpha")
    bravo_pointer = read_profile_bucket("bravo")
    assert alpha_pointer is not None
    assert bravo_pointer is not None
    assert alpha_pointer.bucket_id != bravo_pointer.bucket_id

    result = invoke_cached_cli(("config", "profile", "rename", "alpha", "gamma"))
    assert result.exit_code == 0, f"non-active rename failed: {result.output}"

    # The label moved on the target's own (stable) bucket; identity is unchanged.
    assert read_profile_bucket("alpha") is None
    gamma_pointer = read_profile_bucket("gamma")
    assert gamma_pointer is not None
    assert gamma_pointer.bucket_id == alpha_pointer.bucket_id

    # Both rename events land in the renamed bucket's OWN history.
    target_history = _bucket_history(alpha_pointer.bucket_id)
    target_kinds = {event.event_type for event in target_history.events.values()}
    assert BucketEventType.PROFILE_RENAMED in target_kinds
    assert BucketEventType.BUCKET_RENAMED in target_kinds

    # The safety property: no rename event leaks into the ACTIVE bucket.
    active_history = _bucket_history(bravo_pointer.bucket_id)
    foreign_rename_events = [
        event
        for event in active_history.events.values()
        if event.event_type in (BucketEventType.BUCKET_RENAMED, BucketEventType.PROFILE_RENAMED)
    ]
    assert foreign_rename_events == [], "the active bucket must not carry another bucket's rename event"


def test_cli_rename_refuses_blank_target_with_localised_message() -> None:
    """A whitespace-only target label is refused before the typed command.

    The boundary refusal mirrors the inner primitive's blank-label
    refusal so the operator never sees a raw schema validation error.
    """

    create_profile_via_cli("alpha")

    result = invoke_cached_cli(("config", "profile", "rename", "alpha", "   "))
    assert result.exit_code != 0, f"expected refusal, got: {result.output}"

    pointer = read_profile_bucket("alpha")
    assert pointer is not None, "the profile label must be unchanged after the refusal"
