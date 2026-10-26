"""A profile's Google sign-in never leaves its folder through the remote mirror, not even as ciphertext."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....adapters.outbound.google import session_store
from .....adapters.outbound.google.records import REQUIRED_SCOPES, DriveConfig, OAuthMetadata, OAuthToken
from .....adapters.outbound.google.tests.installation_client_support import synthetic_installation_client
from .....adapters.outbound.storage.local import LocalFileSystemProvider
from .....adapters.persistence.storage.secure_object_namespaces import (
    GOOGLE_DRIVE_CONFIG_NAMESPACE,
    GOOGLE_OAUTH_METADATA_NAMESPACE,
    GOOGLE_OAUTH_TOKEN_NAMESPACE,
)
from .....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ..mirror_push import push_secure_object_mirror_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PROFILE = "6d2f1c0e-8b7a-4c3d-9e5f-1a2b3c4d5e6f"
_REFRESH_MARKER = "synthetic-refresh-never-mirrored"
_SIGN_IN_NAMESPACES = {GOOGLE_OAUTH_TOKEN_NAMESPACE.namespace, GOOGLE_OAUTH_METADATA_NAMESPACE.namespace}


def test_a_full_push_withholds_the_sign_in_and_still_mirrors_the_drive_root(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE) as profile:
        session_store.save_session(
            _PROFILE,
            OAuthToken(
                refresh_token=_REFRESH_MARKER,
                client_id="synthetic.apps.googleusercontent.com",
                token_uri=synthetic_installation_client().token_uri,
            ),
            OAuthMetadata(
                account_email="mirror@example.invalid",
                granted_scopes=REQUIRED_SCOPES,
                issued_at=datetime(2026, 10, 19, tzinfo=UTC),
            ),
            DriveConfig(root_folder_id="synthetic-root-folder"),
        )
        ciphertexts = [
            row.payload for row in profile.repository.iter_all_records_raw() if row.namespace in _SIGN_IN_NAMESPACES
        ]
        assert len(ciphertexts) == 2
        mirror = LocalFileSystemProvider(tmp_path / "mirror")

        result = push_secure_object_mirror_rows(
            provider=mirror,
            repository=profile.repository,
            namespace_filter=None,
            limit=None,
            dry_run=False,
        )

        assert _SIGN_IN_NAMESPACES.isdisjoint(result["pushed_by_namespace"])
        assert _SIGN_IN_NAMESPACES.isdisjoint(result["manifest_pushed_by_namespace"])
        withheld = {namespace for namespace, reason in result["failed_manifests"] if "remote_mirror_withheld" in reason}
        assert withheld == _SIGN_IN_NAMESPACES
        assert result["pushed_by_namespace"].get(GOOGLE_DRIVE_CONFIG_NAMESPACE.namespace) == 1
        mirrored = [path.read_bytes() for path in (tmp_path / "mirror").rglob("*") if path.is_file()]
        assert not [ciphertext for ciphertext in ciphertexts if any(ciphertext in data for data in mirrored)]
