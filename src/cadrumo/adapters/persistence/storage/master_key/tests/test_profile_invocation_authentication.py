"""Explicit profile password proof preserves the selected profile and shared sign-in."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import profile_session_path
from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyRecordError
from cadrumo.adapters.persistence.storage.custody.sentinel import PROFILE_CUSTODY_SENTINEL_FILENAME
from cadrumo.adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from cadrumo.adapters.persistence.storage.master_key.login_throttle import evaluate_login_throttle
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.authentication import ProfileAuthenticationRefusedError
from cadrumo.application.user_profile.lifecycle import ProfileCapsuleLifecycle
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_record_repository import (
    close_active_profile_record_session,
    require_profile_record_session,
)
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.bucket_pointer import read_pointer
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location
from cadrumo.core.time.clock import now as _now

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]
_CREDENTIAL_A = "invocation-password-a"
_CREDENTIAL_B = "invocation-password-b"


def _register_two_profiles(storage_root: Path) -> tuple[str, str]:
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    first = register_profile_with_credentials(
        label="Handover A",
        passphrase=_CREDENTIAL_A,
        profile_create_context=_profile_create_context_for_test,
        profile_decode_context=_profile_decode_context_for_test,
    )
    second = register_profile_with_credentials(
        label="Handover B",
        passphrase=_CREDENTIAL_B,
        profile_create_context=_profile_create_context_for_test,
        profile_decode_context=_profile_decode_context_for_test,
    )
    return first.profile_id, second.profile_id


def _close_live_login() -> None:

    close_active_profile_record_session()
    close_active_bucket_session()


@pytest.mark.parametrize("candidate", ("wrong-password-for-b", "short"))
def test_rejected_b_password_is_non_oracular_and_leaves_active_a_intact(tmp_path: Path, candidate: str) -> None:
    """Rejected target credentials leave the existing local custody intact."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_a, profile_b = _register_two_profiles(storage_root)
        ProfileCapsuleLifecycle().select(profile_a)
        try:
            authenticate_profile_for_invocation(
                name=profile_a,
                passphrase_callback=lambda: _CREDENTIAL_A,
                profile_decode_context=_profile_decode_context_for_test,
            )
            active_a = current_active_bucket_session()
            record_a = require_profile_record_session(
                profile_a, profile_decode_context=_profile_decode_context_for_test
            )
            pointer_a = read_pointer(storage_root)

            with pytest.raises(ProfileAuthenticationRefusedError) as refused:
                authenticate_profile_for_invocation(
                    name=profile_b,
                    passphrase_callback=lambda: candidate,
                    profile_decode_context=_profile_decode_context_for_test,
                )

            assert refused.value.translated_message == "application.user_profile.errors.profile_authentication_refused"
            assert refused.value.context is None
            assert candidate not in repr(refused.value)
            assert evaluate_login_throttle(
                storage_root=storage_root,
                bucket_id=profile_b,
                now=_now(),
            ).throttled

            assert read_pointer(storage_root) == pointer_a
            assert current_active_bucket_session() is active_a
            assert (
                require_profile_record_session(profile_a, profile_decode_context=_profile_decode_context_for_test)
                is record_a
            )
            assert not profile_session_path(storage_root=storage_root, profile_id=UUID(profile_b)).exists()
        finally:
            _close_live_login()


def test_invalid_b_candidate_material_leaves_active_a_and_pointer_bytes_intact(tmp_path: Path) -> None:
    """A malformed B custody artifact is refused before any A replacement."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_a, profile_b = _register_two_profiles(storage_root)
        ProfileCapsuleLifecycle().select(profile_a)
        instant = datetime.now(UTC)
        try:
            authenticate_profile_for_invocation(
                name=profile_a,
                now=instant,
                passphrase_callback=lambda: _CREDENTIAL_A,
                profile_decode_context=_profile_decode_context_for_test,
            )
            active_a = current_active_bucket_session()
            record_a = require_profile_record_session(
                profile_a, profile_decode_context=_profile_decode_context_for_test
            )
            pointer_a = read_pointer(storage_root)
            sentinel_path = (
                storage_root
                / storage_location(StorageCategory.BUCKETS).relative_path()
                / profile_b
                / storage_location(StorageCategory.PROFILE_CAPSULE_DATA).relative_path()
                / PROFILE_CUSTODY_SENTINEL_FILENAME
            )
            sentinel_path.write_bytes(b"not-a-current-custody-sentinel")

            with pytest.raises(ProfileCustodyRecordError):
                authenticate_profile_for_invocation(
                    name=profile_b,
                    now=instant + timedelta(seconds=3),
                    passphrase_callback=lambda: _CREDENTIAL_B,
                    profile_decode_context=_profile_decode_context_for_test,
                )

            assert read_pointer(storage_root) == pointer_a
            assert current_active_bucket_session() is active_a
            assert (
                require_profile_record_session(profile_a, profile_decode_context=_profile_decode_context_for_test)
                is record_a
            )
            assert not profile_session_path(storage_root=storage_root, profile_id=UUID(profile_b)).exists()
        finally:
            _close_live_login()


def test_invocation_authentication_preserves_selection_and_other_runtime_receipt(tmp_path: Path) -> None:
    """Proof binds the named profile locally and leaves the shared sign-in untouched."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        profile_a, profile_b = _register_two_profiles(storage_root)
        ProfileCapsuleLifecycle().select(profile_a)
        try:
            authenticate_profile_for_invocation(
                name=profile_a,
                passphrase_callback=lambda: _CREDENTIAL_A,
                profile_decode_context=_profile_decode_context_for_test,
            )
            active_a = current_active_bucket_session()
            receipt = profile_session_path(storage_root=storage_root, profile_id=UUID(profile_a))
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_bytes(b"runtime-owned-receipt-witness")

            result = authenticate_profile_for_invocation(
                name=profile_b,
                passphrase_callback=lambda: _CREDENTIAL_B,
                profile_decode_context=_profile_decode_context_for_test,
            )

            assert result.bucket_id == profile_b
            assert result.session_persisted is False
            assert current_active_bucket_session() is not active_a
            assert current_active_bucket_session() is not None
            active_b = current_active_bucket_session()
            assert active_b is not None
            assert active_b.bucket_id == profile_b
            assert require_profile_record_session(
                profile_b, profile_decode_context=_profile_decode_context_for_test
            ).profile_id.hex == profile_b.replace("-", "")
            assert read_pointer(storage_root).bucket_id == profile_a
            assert active_a is not None and active_a.sealed
            assert receipt.read_bytes() == b"runtime-owned-receipt-witness"
        finally:
            _close_live_login()
