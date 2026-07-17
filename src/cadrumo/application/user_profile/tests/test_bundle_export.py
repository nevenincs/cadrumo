"""Real-runtime proofs for the single portable profile export authority.

Both operator purposes -- portable transfer and the subject-access request --
must resolve through one :func:`export_profile_bundle` service and one bundle
schema, deriving their data categories from the serialized bundle fields and the
registry namespaces the bundle carries, while keeping their distinct purpose
metadata.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from pydantic import SecretStr

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....domain.buckets import BucketEvent, BucketEventType
from ....domain.user_profile import (
    CoverageManifest,
    ProfileExportError,
    UserProfilePortableExport,
    UserProfileRecord,
)
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .. import (
    EncryptedProfileBundleExport,
    ProfileBundleExportPurpose,
    ProfileBundleExportRequest,
    ProfileBundleExportTransport,
    decrypt_profile_bundle_with_passphrase,
    export_profile_bundle,
    profile_storage_session,
)
from .._bundle_export_contracts import _CATEGORY_BY_BUNDLE_FIELD, bundle_data_categories

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_EVENT_HISTORY_NAMESPACE = "cadrumo.domain.buckets.event_history"
_PASSPHRASE = "profile-export-authority-test-passphrase"  # noqa: S105 - synthetic test fixture


def _create_profile() -> str:
    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "subject",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--activity",
            "design",
            "--entity-type",
            "natural_person",
            "--name",
            "Subject",
            "--surnames",
            "Access",
        ],
    )
    assert result.exit_code == 0, result.output

    from ....core import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    return bucket_id


def _request(
    destination: Path,
    *,
    purpose: ProfileBundleExportPurpose,
    transport: ProfileBundleExportTransport = ProfileBundleExportTransport.CLEARTEXT_LOCAL,
) -> ProfileBundleExportRequest:
    return ProfileBundleExportRequest(
        profile_name="subject",
        destination=destination,
        purpose=purpose,
        transport=transport,
        passphrase=SecretStr(_PASSPHRASE) if transport is ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED else None,
    )


def _export_events(bucket_id: str) -> tuple[BucketEvent, ...]:
    with profile_storage_session(bucket_id):
        catalogue = BucketEventHistoryRepository().load()
    return tuple(event for event in catalogue.events.values() if event.event_type is BucketEventType.PROFILE_EXPORTED)


@contextmanager
def _reject_event_history_updates(database_path: Path) -> Iterator[None]:
    """Install a real SQLite constraint that rejects event-catalogue updates."""
    trigger_name = "reject_profile_export_event_update"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            f"""
            CREATE TRIGGER {trigger_name}
            BEFORE UPDATE ON secure_objects
            WHEN OLD.namespace = '{_EVENT_HISTORY_NAMESPACE}'
            BEGIN
                SELECT RAISE(ABORT, 'profile export event update rejected');
            END
            """,
        )
        connection.commit()
    try:
        yield
    finally:
        with sqlite3.connect(database_path) as connection:
            connection.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
            connection.commit()


def test_both_export_purposes_share_one_service_and_one_bundle_schema(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        bucket_id = _create_profile()
        portable_path = tmp_path / "portable.json"
        subject_access_path = tmp_path / "subject-access.json"

        portable = export_profile_bundle(
            _request(portable_path, purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER),
        )
        subject_access = export_profile_bundle(
            _request(subject_access_path, purpose=ProfileBundleExportPurpose.SUBJECT_ACCESS),
        )

        portable_bundle = UserProfilePortableExport.model_validate_json(portable_path.read_text(encoding="utf-8"))
        subject_access_bundle = UserProfilePortableExport.model_validate_json(
            subject_access_path.read_text(encoding="utf-8"),
        )
        assert subject_access_bundle.model_copy(update={"exported_at": portable_bundle.exported_at}) == portable_bundle
        assert portable_bundle.bundle_schema_version == subject_access_bundle.bundle_schema_version
        assert portable.profile_id == subject_access.profile_id == bucket_id
        assert portable.bundle_schema_version == subject_access.bundle_schema_version


def test_distinct_purpose_metadata_is_retained_across_the_shared_service(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        bucket_id = _create_profile()
        portable = export_profile_bundle(
            _request(tmp_path / "portable.json", purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER),
        )
        subject_access = export_profile_bundle(
            _request(tmp_path / "subject-access.json", purpose=ProfileBundleExportPurpose.SUBJECT_ACCESS),
        )

        assert portable.purpose is ProfileBundleExportPurpose.PORTABLE_TRANSFER
        assert subject_access.purpose is ProfileBundleExportPurpose.SUBJECT_ACCESS
        # Categories and schema are shared; only the purpose differs.
        assert portable.data_categories == subject_access.data_categories

        events = _export_events(bucket_id)
        assert {event.payload["purpose"] for event in events} == {
            ProfileBundleExportPurpose.PORTABLE_TRANSFER.value,
            ProfileBundleExportPurpose.SUBJECT_ACCESS.value,
        }


def test_data_categories_are_derived_from_serialized_bundle_fields(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        destination = tmp_path / "portable.json"
        result = export_profile_bundle(
            _request(destination, purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER),
        )
        bundle = UserProfilePortableExport.model_validate_json(destination.read_text(encoding="utf-8"))

        expected = bundle_data_categories(bundle)
        assert result.data_categories == expected
        # Every category traces to a serialized field or a carried namespace, never a static list.
        schema_categories = {
            _CATEGORY_BY_BUNDLE_FIELD[field]
            for field in type(bundle).model_fields
            if field in _CATEGORY_BY_BUNDLE_FIELD
        }
        assert schema_categories <= set(result.data_categories)
        assert "profile_identity_and_facts" in result.data_categories


def test_carried_registry_namespaces_surface_as_derived_categories() -> None:
    # Pure-logic derivation over a real bundle whose coverage manifest declares
    # carried registry namespaces; no static category list is consulted.
    record = UserProfileRecord.model_construct(profile_id="p", display_name="P", facts=())
    bundle = UserProfilePortableExport.model_construct(
        bundle_schema_version=3,
        profile=record,
        coverage_manifest=CoverageManifest(carried_namespaces=("cadrumo.evidence.attachments",)),
    )
    categories = bundle_data_categories(bundle)
    assert "secure_object_namespace:cadrumo.evidence.attachments" in categories
    assert "profile_identity_and_facts" in categories


def test_encrypted_transport_decrypts_to_the_canonical_cleartext_bundle(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        cleartext_path = tmp_path / "profile.json"
        encrypted_path = tmp_path / "profile.aeat-profile"

        export_profile_bundle(
            _request(cleartext_path, purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER),
        )
        export_profile_bundle(
            _request(
                encrypted_path,
                purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
                transport=ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED,
            ),
        )

        cleartext = UserProfilePortableExport.model_validate_json(cleartext_path.read_text(encoding="utf-8"))
        envelope = EncryptedProfileBundleExport.model_validate_json(encrypted_path.read_text(encoding="utf-8"))
        decrypted = decrypt_profile_bundle_with_passphrase(envelope, passphrase=_PASSPHRASE)
        assert decrypted.model_copy(update={"exported_at": cleartext.exported_at}) == cleartext
        assert b"12345678Z" not in encrypted_path.read_bytes()


def test_event_failure_keeps_target_published_and_reconcile_emits_pending_event(tmp_path: Path) -> None:
    # Contract: a durably-published bundle is NEVER un-published. If the
    # completion event write fails after a successful atomic replace, the target
    # stays published, the operation journal stays COMPLETED, and a later
    # reconcile emits the still-owed PROFILE_EXPORTED event exactly once. This
    # replaces the earlier restore-on-event-failure contract, which could
    # un-publish a durably-written bundle.
    from .. import reconcile_prepared_exports
    from .._bundle_export_operation import (
        ProfileBundleExportJournalRepository,
        ProfileBundleExportOperationStatus,
    )

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        bucket_id = _create_profile()
        seed_path = tmp_path / "seed.json"
        export_profile_bundle(
            _request(seed_path, purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER),
        )
        event_count_before = len(_export_events(bucket_id))
        database_path = storage_root / "buckets" / bucket_id / "db" / "cadrumo.db"

        existing_target = tmp_path / "existing-target.json"
        previous_bytes = b"operator-owned previous export bytes\n"
        existing_target.write_bytes(previous_bytes)

        with (
            _reject_event_history_updates(database_path),
            pytest.raises(ProfileExportError, match="audit event could not be recorded"),
        ):
            export_profile_bundle(
                _request(existing_target, purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER),
            )

        # Published: the new bundle overwrote the preexisting bytes (not restored).
        published = UserProfilePortableExport.model_validate_json(existing_target.read_text(encoding="utf-8"))
        assert published.profile.profile_id == bucket_id
        assert existing_target.read_bytes() != previous_bytes
        # The audit event is still owed; the journal is COMPLETED.
        repository = ProfileBundleExportJournalRepository()
        completed = repository.list()
        assert len(completed) == 1
        assert completed[0].status is ProfileBundleExportOperationStatus.COMPLETED
        assert len(_export_events(bucket_id)) == event_count_before

        # With the event store healthy again, reconcile emits the pending event.
        reconciled = reconcile_prepared_exports()
        assert len(reconciled) == 1
        assert repository.list() == ()
        assert len(_export_events(bucket_id)) == event_count_before + 1
