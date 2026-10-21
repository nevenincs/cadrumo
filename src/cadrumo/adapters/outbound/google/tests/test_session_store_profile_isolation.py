"""A profile's Google sign-in lives only in that profile's folder, and only that profile can open it.

Two real profiles share one storage root, as an installation holds them: each
has its own published capsule, its own folder and its own data-encryption key.
The sign-in records are synthetic; custody, encryption and SQL are the
production ones.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....core.bucket_pointer import BucketPointer, read_pointer_selection, write_pointer
from .....core.profile_root_environment import PROFILE_ROOT_VARIABLE
from .....core.storage_environment import ChildEnvironmentProfile, child_environment
from ....persistence.storage.crypto.encrypted_columns import (
    decrypt_secure_object_payload,
    secure_object_payload_aad,
)
from ....persistence.storage.errors import DecryptionError, StorageValidationError
from ....persistence.storage.secure_object_namespaces import (
    GOOGLE_OAUTH_METADATA_NAMESPACE,
    GOOGLE_OAUTH_TOKEN_NAMESPACE,
)
from ....persistence.storage.tests.secure_sql import isolated_two_bucket_runtime
from .. import session_store
from ..records import REQUIRED_SCOPES, DriveConfig, OAuthMetadata, OAuthToken

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_REFRESH_MARKER = "synthetic-refresh-profile-isolation"
_TOKEN = GOOGLE_OAUTH_TOKEN_NAMESPACE.namespace
_METADATA = GOOGLE_OAUTH_METADATA_NAMESPACE.namespace


def _sign_in() -> tuple[OAuthToken, OAuthMetadata, DriveConfig]:
    return (
        OAuthToken(
            refresh_token=_REFRESH_MARKER,
            client_id="synthetic.apps.googleusercontent.com",
            token_uri="https://oauth2.googleapis.com/token",
        ),
        OAuthMetadata(
            account_email="profile-a@example.invalid",
            granted_scopes=REQUIRED_SCOPES,
            issued_at=datetime(2026, 10, 19, tzinfo=UTC),
        ),
        DriveConfig(root_folder_id="synthetic-root-folder"),
    )


def _files(root: Path) -> dict[Path, tuple[int, int]]:
    return {path: (path.stat().st_size, path.stat().st_mtime_ns) for path in root.rglob("*") if path.is_file()}


def test_signing_in_writes_token_material_only_under_that_profiles_folder(tmp_path: Path) -> None:
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        root = runtime.primary.storage_root
        folder = runtime.primary.paths.bucket_dir
        before = _files(root)

        session_store.save_session(runtime.primary.bucket_id, *_sign_in())

        changed = sorted(path for path, state in _files(root).items() if before.get(path) != state)
        assert changed
        outside = [str(path.relative_to(root)) for path in changed if not path.is_relative_to(folder)]
        assert outside == []
        readable_anywhere = [
            str(path.relative_to(root)) for path in _files(root) if _REFRESH_MARKER.encode() in path.read_bytes()
        ]
        assert readable_anywhere == []
        assert len(list(runtime.primary.repository.iter_all_records_raw(namespace=_TOKEN))) == 1
        with runtime.switch_to_secondary():
            assert list(runtime.secondary.repository.iter_all_records_raw(namespace=_TOKEN)) == []
            assert list(runtime.secondary.repository.iter_all_records_raw(namespace=_METADATA)) == []


def test_another_profile_can_neither_load_nor_decrypt_the_token(tmp_path: Path) -> None:
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        profile_a = runtime.primary.bucket_id
        session_store.save_session(profile_a, *_sign_in())
        (row,) = runtime.primary.repository.iter_all_records_raw(namespace=_TOKEN)
        associated = secure_object_payload_aad(row.namespace, row.object_key, row.schema_version)
        assert _REFRESH_MARKER.encode() in decrypt_secure_object_payload(row.payload, associated_data=associated)

        with runtime.switch_to_secondary():
            assert session_store.load_token(runtime.secondary.bucket_id) is None
            with pytest.raises(StorageValidationError):
                session_store.load_token(profile_a)
            with pytest.raises(StorageValidationError):
                session_store.load_metadata(profile_a)
            # Even holding the ciphertext, profile B's key fails the tag.
            with pytest.raises(DecryptionError):
                decrypt_secure_object_payload(row.payload, associated_data=associated)


def test_a_sign_in_for_one_profile_never_lands_in_the_profile_unlocked_now(tmp_path: Path) -> None:
    # A consent can outlive a profile switch; its records must not follow the switch.
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        profile_a = runtime.primary.bucket_id
        with runtime.switch_to_secondary():
            with pytest.raises(StorageValidationError):
                session_store.save_session(profile_a, *_sign_in())
            assert list(runtime.secondary.repository.iter_all_records_raw(namespace=_TOKEN)) == []
        assert session_store.load_token(profile_a) is None


def test_switching_profile_changes_the_folder_the_environment_names(tmp_path: Path) -> None:
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        root = runtime.primary.storage_root
        session_store.save_session(runtime.primary.bucket_id, *_sign_in())
        named: list[Path] = []
        for revision, profile in enumerate((runtime.primary, runtime.secondary), start=1):
            write_pointer(root, BucketPointer.selected(bucket_id=profile.bucket_id, transition_revision=revision))
            selected = read_pointer_selection(root).bucket_id
            environment = child_environment(ChildEnvironmentProfile.STRICT, root, base={}, profile_id=selected)
            named.append(Path(environment[PROFILE_ROOT_VARIABLE]).resolve())

        assert named == [runtime.primary.paths.bucket_dir.resolve(), runtime.secondary.paths.bucket_dir.resolve()]
        # The folder named for profile A is the one that holds A's sign-in.
        assert runtime.primary.paths.database_file.resolve().is_relative_to(named[0])
        assert not runtime.primary.paths.database_file.resolve().is_relative_to(named[1])
