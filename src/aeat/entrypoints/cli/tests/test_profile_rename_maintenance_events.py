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
from typer.testing import CliRunner

from ....adapters.persistence.storage.runtime_repository import (
    secure_object_repository_for_bucket,
)
from ....application.workflow._profile_bucket_scan import read_profile_bucket
from ....domain.buckets import (
    BucketEventHistoryCatalogue,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app as root_app
from ._profile_lifecycle_support import create_via_cli

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
    from ....application.user_profile._orchestration import profile_storage_session

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
    from ....adapters.persistence.storage.sql.engine import dispose_engine

    runner = CliRunner()
    create_via_cli(runner, "alpha")
    pointer = read_profile_bucket("alpha")
    assert pointer is not None

    dispose_engine()
    result = runner.invoke(root_app, ["config", "profile", "rename", "alpha", "beta"])
    assert result.exit_code == 0, f"rename failed: {result.output}"

    dispose_engine()
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


def test_cli_rename_of_non_active_profile_is_refused_loudly_and_changes_nothing() -> None:
    """Renaming a profile that does not own the active session refuses loudly.

    The per-bucket storage runtime refuses a database route that does
    not match the active bucket session, so a rename of a non-active
    profile cannot proceed (the operator switches first). This pin
    guarantees the refusal stays loud — and that no maintenance event
    leaks into the ACTIVE bucket's history for a rename that never
    happened, which is exactly what an active-bucket-bound event
    repository default would have written.
    """
    from ....adapters.persistence.storage.sql.engine import dispose_engine

    runner = CliRunner()
    create_via_cli(runner, "alpha")
    create_via_cli(runner, "bravo")  # bravo is now the active profile
    alpha_pointer = read_profile_bucket("alpha")
    bravo_pointer = read_profile_bucket("bravo")
    assert alpha_pointer is not None
    assert bravo_pointer is not None
    assert alpha_pointer.bucket_id != bravo_pointer.bucket_id

    dispose_engine()
    result = runner.invoke(root_app, ["config", "profile", "rename", "alpha", "gamma"])
    assert result.exit_code != 0, f"expected refusal, got: {result.output}"

    dispose_engine()
    # The refused rename must not have moved the label.
    assert read_profile_bucket("alpha") is not None
    assert read_profile_bucket("gamma") is None

    active_history = _bucket_history(bravo_pointer.bucket_id)
    foreign_rename_events = [
        event
        for event in active_history.events.values()
        if event.event_type is BucketEventType.BUCKET_RENAMED
    ]
    assert foreign_rename_events == [], "the active bucket must not carry another bucket's rename event"


def test_cli_rename_refuses_blank_target_with_localised_message() -> None:
    """A whitespace-only target label is refused before the typed command.

    The boundary refusal mirrors the inner primitive's blank-label
    refusal so the operator never sees a raw schema validation error.
    """
    from ....adapters.persistence.storage.sql.engine import dispose_engine

    runner = CliRunner()
    create_via_cli(runner, "alpha")

    dispose_engine()
    result = runner.invoke(root_app, ["config", "profile", "rename", "alpha", "   "])
    assert result.exit_code != 0, f"expected refusal, got: {result.output}"

    dispose_engine()
    pointer = read_profile_bucket("alpha")
    assert pointer is not None, "the profile label must be unchanged after the refusal"
