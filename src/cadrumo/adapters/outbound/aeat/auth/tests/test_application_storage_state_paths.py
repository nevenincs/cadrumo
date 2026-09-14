"""Cross-bucket proofs for encrypted auth session storage ownership.

These tests exercise the application auth operations against real profile
buckets and the outbound encrypted session store.  They therefore live with
the adapter integration tests rather than the inward application path-model
tests.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cadrumo.adapters.outbound.aeat.auth import session_store
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.operator import configure_operator_auth, logout_operator_auth, reset_operator_auth
from cadrumo.application.auth.sessions import storage_state_paths
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import override_settings
from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

_PROFILE_A = "11111111-1111-4111-8111-111111111111"
_PROFILE_B = "22222222-2222-4222-8222-222222222222"


def _hash_bucket_tree(storage_root: Path, bucket_id: str) -> str:
    """Return a stable fingerprint of every on-disk byte under one bucket's directory."""
    bucket_dir = storage_root / "buckets" / bucket_id
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
        configure_operator_auth("certificate", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
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
            result = logout_operator_auth(provider="certificate", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
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
            result = reset_operator_auth(all_providers=True, operator_scope_ports=_OPERATOR_SCOPE_PORTS)
            assert session_store.exists(session_a) is False

        unrelated_after = _hash_bucket_tree(storage_root, _PROFILE_B)

        assert result.removed_sessions >= 1
        assert unrelated_after == unrelated_before

        with open_test_profile_session(_PROFILE_B):
            assert session_store.exists(storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state)
