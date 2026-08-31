"""Focused unit tests for application.auth.sessions.storage_state_paths.

`storage_state_paths` composes the active profile + AuthProviderKind into the
encrypted storage-state logical key. Three branches:

1. ``kind=AuthProviderKind.CERTIFICATE`` → certificate stem (``storage``).
2. ``kind=AuthProviderKind.CLAVE_MOVIL`` → clave-movil stem
   (``clave-movil-storage``).
3. ``kind=None`` → defaults to AuthProviderKind.CERTIFICATE.

Previously no direct unit-test coverage. The helper is consumed by
``load_persisted_session``, ``delete_persisted_session``, and the
broader auth-session lifecycle. The returned path is not a plaintext
filesystem destination. A regression in the stem mapping (swapping cert
<-> clave-movil) would silently route session reads and writes to the
wrong encrypted object.

Tests pin the path composition contract; assertions are
structural / composition-contract assertions, not calculation
tautologies.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.outbound.aeat.auth import session_store
from ....adapters.persistence.storage.bucket.directory_layout import bucket_paths
from ....core.auth_provider import AuthProviderKind
from ....core.config import override_settings
from ....core.directory_scan import DirectoryEntryKind, scan_directory
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...wizard import compiler as _wizard  # noqa: F401  (compiler import seeds the ProfileKey registry)
from ..operator import configure_operator_auth, logout_operator_auth, reset_operator_auth
from ..sessions import storage_state_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_A = "11111111-1111-4111-8111-111111111111"
_PROFILE_B = "22222222-2222-4222-8222-222222222222"


@pytest.fixture(autouse=True, name="_active_profile")
def active_profile(tmp_path: Path) -> Iterator[None]:
    """Set the active-profile setting so the precedence chain resolves.

    Routes through :func:`cadrumo.core.config.override_settings`, the
    canonical Settings injection mechanism. Tests that exercise a
    different profile name nest a further `override_settings` block
    in their body.

    The package-level `_isolated_aeat_root` conftest fixture handles
    `cadrumo_local_storage_root` redirection separately.
    """

    from ....core.config import override_settings

    with override_settings(cadrumo_active_profile="operator"):
        yield


def test_storage_state_paths_certificate_uses_storage_stem() -> None:
    result = storage_state_paths(AuthProviderKind.CERTIFICATE)

    assert result.storage_state == Path(".cadrumo/auth/sessions/operator-storage.json")


def test_storage_state_paths_clave_movil_uses_clave_movil_storage_stem() -> None:
    result = storage_state_paths(AuthProviderKind.CLAVE_MOVIL)

    assert result.storage_state == Path(".cadrumo/auth/sessions/operator-clave-movil-storage.json")


def test_storage_state_paths_none_defaults_to_certificate() -> None:
    """The default kind is CERTIFICATE; explicit None and unsupplied
    kwarg return the same path as explicit CERTIFICATE."""
    default_result = storage_state_paths()
    explicit_result = storage_state_paths(AuthProviderKind.CERTIFICATE)

    assert default_result.storage_state == explicit_result.storage_state


def test_storage_state_paths_composes_profile_name_into_filename(tmp_path: Path) -> None:
    """The active profile name is interpolated into the filename so
    two operator profiles do not share session state. The active
    profile resolves through the operator-facing precedence chain
    (env var > pointer file); switching it between calls changes the
    target path."""

    from ....core.config import override_settings

    with override_settings(cadrumo_active_profile="operator"):
        result_a = storage_state_paths(AuthProviderKind.CERTIFICATE)

    with override_settings(cadrumo_active_profile="other-profile"):
        result_b = storage_state_paths(AuthProviderKind.CERTIFICATE)

    assert result_a.storage_state == Path(".cadrumo/auth/sessions/operator-storage.json")
    assert result_b.storage_state == Path(".cadrumo/auth/sessions/other-profile-storage.json")
    assert result_a.storage_state != result_b.storage_state


def test_storage_state_paths_is_independent_of_plaintext_token_dir(tmp_path: Path) -> None:
    """Encrypted session object keys must not depend on the plaintext token dir."""
    from ....core.config import Settings, override_settings

    with override_settings(cadrumo_token_dir=tmp_path / "tokens-a"):
        Settings()
        result_a = storage_state_paths(AuthProviderKind.CERTIFICATE)
    with override_settings(cadrumo_token_dir=tmp_path / "tokens-b"):
        Settings()
        result_b = storage_state_paths(AuthProviderKind.CERTIFICATE)

    assert result_a.storage_state == result_b.storage_state
    assert result_a.storage_state == Path(".cadrumo/auth/sessions/operator-storage.json")


def test_storage_state_paths_returns_strict_frozen_model(tmp_path: Path) -> None:
    """The returned StorageStatePaths is a strict/frozen pydantic
    model; attempting to mutate the storage_state field raises."""
    result = storage_state_paths(AuthProviderKind.CERTIFICATE)

    attr = "storage_state"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(result, attr, tmp_path / "other.json")


# ---------------------------------------------------------------------------
# Cross-bucket byte-identity: a provider or all-provider auth deletion in one
# bucket must never touch the on-disk encrypted session state of an unrelated
# bucket. Sessions are encrypted secure objects in each bucket's own storage,
# so the durable proof is that the unrelated bucket's on-disk tree stays
# byte-for-byte identical across the operation.
# ---------------------------------------------------------------------------


def _hash_bucket_tree(storage_root: Path, bucket_id: str) -> str:
    """Return a stable fingerprint of every on-disk byte under one bucket's directory."""
    bucket_dir = bucket_paths(storage_root, bucket_id).bucket_dir
    digest = hashlib.sha256()
    for file in scan_directory(bucket_dir, recursive=True, select=DirectoryEntryKind.FILES):
        digest.update(file.relative_to(bucket_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _create_profile_with_certificate_session(bucket_id: str) -> None:
    """Register a bucket, configure the certificate provider, and persist a real session."""
    with open_test_profile_session(bucket_id):
        register_minimal_profile(profile_id=bucket_id)
        configure_operator_auth("certificate")
        session_path = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
        session_store.save(
            session_path,
            storage_state={"cookies": [], "origins": []},
            metadata={"provider_kind": "certificate"},
        )
        assert session_store.exists(session_path)


def test_provider_logout_leaves_unrelated_bucket_session_bytes_identical(tmp_path: Path) -> None:
    """A provider-scoped logout in bucket A leaves bucket B's session storage byte-identical."""
    with (
        isolated_profile_storage_root(tmp_path=tmp_path) as storage_root,
        override_settings(cadrumo_active_profile=None),
    ):
        _create_profile_with_certificate_session(_PROFILE_A)
        _create_profile_with_certificate_session(_PROFILE_B)
        unrelated_before = _hash_bucket_tree(storage_root, _PROFILE_B)

        with open_test_profile_session(_PROFILE_A):
            session_a = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
            assert session_store.exists(session_a)
            result = logout_operator_auth(provider="certificate")
            assert session_store.exists(session_a) is False

        unrelated_after = _hash_bucket_tree(storage_root, _PROFILE_B)

        assert result.removed_sessions == 1
        assert unrelated_after == unrelated_before

        with open_test_profile_session(_PROFILE_B):
            assert session_store.exists(storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state)


def test_all_provider_reset_leaves_unrelated_bucket_session_bytes_identical(tmp_path: Path) -> None:
    """An all-provider reset in bucket A leaves bucket B's session storage byte-identical."""
    with (
        isolated_profile_storage_root(tmp_path=tmp_path) as storage_root,
        override_settings(cadrumo_active_profile=None),
    ):
        _create_profile_with_certificate_session(_PROFILE_A)
        _create_profile_with_certificate_session(_PROFILE_B)
        unrelated_before = _hash_bucket_tree(storage_root, _PROFILE_B)

        with open_test_profile_session(_PROFILE_A):
            session_a = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
            assert session_store.exists(session_a)
            result = reset_operator_auth(all_providers=True)
            assert session_store.exists(session_a) is False

        unrelated_after = _hash_bucket_tree(storage_root, _PROFILE_B)

        assert result.removed_sessions >= 1
        assert unrelated_after == unrelated_before

        with open_test_profile_session(_PROFILE_B):
            assert session_store.exists(storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state)
