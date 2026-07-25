"""Real-behaviour proof that a portable-bundle import records its own event.

Restoring a bundle and recording ``profile.imported`` are one operator action.
They used to be two: an entrypoint called the deserialiser and then appended the
bucket event itself, so the audit record lived outside the application layer and
any second caller of the deserialiser was free to omit it.
:func:`register_imported_profile_bundle` owns the pair, and these tests drive it
against a real bucket runtime, real encrypted SQLite, and the real bucket-event
history catalogue. No mocks, stubs, monkeypatches, skips, or expected-fail
markers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....core.resources import resources
from ....domain.buckets import BucketEvent, BucketEventObjectType, BucketEventType
from ....domain.user_profile import UserProfileStatus
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    ProfileLifecycleService,
    ProfileValidationService,
    RegisterProfileCommand,
    UserProfileLifecycleRepository,
    register_imported_profile_bundle,
    serialize_profile_bundle,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "3f6c1a94-2d7b-4f05-9e18-8a41b7c6d052"
_DISPLAY_NAME = "Imported bundle profile"
_SOURCE_PATH = "bundles/portable-profile.json"


def _imported_events() -> tuple[BucketEvent, ...]:
    """Return every persisted ``profile.imported`` event in the active bucket."""
    catalogue = BucketEventHistoryRepository().load()
    return tuple(event for event in catalogue.events.values() if event.event_type is BucketEventType.PROFILE_IMPORTED)


def _register_source_profile() -> None:
    """Register a real profile record so the bucket has a serialisable bundle."""
    service = ProfileLifecycleService(
        repository=UserProfileLifecycleRepository(bucket_id=_BUCKET_ID),
        validator=ProfileValidationService(schema=resources().user_profile_schema.singleton),
    )
    service.register(
        RegisterProfileCommand(
            profile_id=_BUCKET_ID,
            display_name=_DISPLAY_NAME,
            status=UserProfileStatus.SETUP_INCOMPLETE,
            facts=(),
        ),
    )


def test_importing_a_bundle_records_one_grounded_profile_imported_event(tmp_path: Path) -> None:
    """The composition emits exactly one event carrying the import's provenance."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _register_source_profile()
        bundle = serialize_profile_bundle(bucket_id=_BUCKET_ID)

        assert _imported_events() == (), "no import event may exist before the import runs"

        event = register_imported_profile_bundle(
            bundle,
            target_bucket_id=_BUCKET_ID,
            display_name=_DISPLAY_NAME,
            source_path=_SOURCE_PATH,
        )

        persisted = _imported_events()
        assert len(persisted) == 1, f"expected exactly one import event, got {len(persisted)}"
        assert persisted[0] == event, "the returned event is not the one that was persisted"
        assert event.bucket_id == _BUCKET_ID
        assert event.object_type is BucketEventObjectType.PROFILE
        assert event.object_id == _BUCKET_ID
        assert event.actor == "operator", "an operator-driven import must not be attributed to a module"
        assert dict(event.payload) == {
            "display_name": _DISPLAY_NAME,
            "source_path": _SOURCE_PATH,
            "schema_version": str(bundle.bundle_schema_version),
        }
        assert event.payload_version == 1, (
            "the import event's payload contract is v1; the shared emitter's modelo default must not leak in"
        )


def test_a_refused_bundle_leaves_no_import_event(tmp_path: Path) -> None:
    """An unsupported bundle version refuses the restore and records nothing.

    Anti-tautology guard for the test above: it proves the event is emitted by
    the import actually succeeding, not appended unconditionally by the wrapper.
    """
    from ....domain.user_profile import UserProfilePortableExport

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _register_source_profile()
        bundle = serialize_profile_bundle(bucket_id=_BUCKET_ID)
        stale = bundle.model_copy(update={"bundle_schema_version": bundle.bundle_schema_version - 1})
        assert isinstance(stale, UserProfilePortableExport)

        from .._bundle import UnsupportedBundleSchemaVersionError

        with pytest.raises(UnsupportedBundleSchemaVersionError):
            register_imported_profile_bundle(
                stale,
                target_bucket_id=_BUCKET_ID,
                display_name=_DISPLAY_NAME,
                source_path=_SOURCE_PATH,
            )

        assert _imported_events() == (), "a refused restore must not leave an import event behind"
