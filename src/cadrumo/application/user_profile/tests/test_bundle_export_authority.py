"""Real-runtime coverage for the canonical portable profile export authority."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from pydantic import SecretStr

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....domain.buckets import BucketEvent, BucketEventType
from ....domain.user_profile import ProfileExportError, UserProfilePortableExport
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


def test_both_export_intents_share_one_serializer_and_one_event_authority(tmp_path: Path) -> None:
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
        assert portable.profile_id == subject_access.profile_id == bucket_id
        assert portable.data_categories == subject_access.data_categories
        assert "profile_identity_and_facts" in portable.data_categories

        events = _export_events(bucket_id)
        assert len(events) == 2
        assert {event.payload["purpose"] for event in events} == {
            ProfileBundleExportPurpose.PORTABLE_TRANSFER.value,
            ProfileBundleExportPurpose.SUBJECT_ACCESS.value,
        }


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


def test_event_failure_removes_new_target_and_restores_preexisting_target(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        bucket_id = _create_profile()
        seed_path = tmp_path / "seed.json"
        export_profile_bundle(
            _request(seed_path, purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER),
        )
        event_count_before = len(_export_events(bucket_id))
        database_path = storage_root / "buckets" / bucket_id / "db" / "cadrumo.db"

        new_target = tmp_path / "new-target.json"
        existing_target = tmp_path / "existing-target.json"
        previous_bytes = b"operator-owned previous export bytes\n"
        existing_target.write_bytes(previous_bytes)

        with _reject_event_history_updates(database_path):
            with pytest.raises(ProfileExportError, match="destination was restored"):
                export_profile_bundle(
                    _request(new_target, purpose=ProfileBundleExportPurpose.SUBJECT_ACCESS),
                )
            with pytest.raises(ProfileExportError, match="destination was restored"):
                export_profile_bundle(
                    _request(existing_target, purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER),
                )

        assert not new_target.exists()
        assert existing_target.read_bytes() == previous_bytes
        assert len(_export_events(bucket_id)) == event_count_before
