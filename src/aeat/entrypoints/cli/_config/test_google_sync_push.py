"""Real-behavior coverage for Google sync push mirror semantics."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.adapters.outbound.storage import (
    REMOTE_MIRROR_MANIFEST_NAMESPACE,
    RemoteMirrorNamespaceManifest,
    remote_mirror_object_key_hmac,
)
from aeat.adapters.outbound.storage._local import LocalFileSystemProvider
from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.adapters.persistence.storage.sql.engine import create_engine_from_settings
from aeat.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from aeat.core.classification import SensitivityClass
from aeat.core.config import Settings
from aeat.entrypoints.cli._config._google import _push_secure_object_mirror_rows

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def test_google_sync_push_persists_manifest_matching_uploaded_ciphertext_objects(tmp_path: Path) -> None:
    key_provider = EphemeralMasterKeyProvider()
    with key_provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'push.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            repository = SecureObjectRepository(engine=engine)
            namespace = "aeat.google.sync.push.fixture"
            repository.save(
                namespace=namespace,
                object_key="natural-key",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
                payload=b"push-path-plaintext",
            )
            raw_row = next(repository.iter_all_records_raw())
            provider = LocalFileSystemProvider(tmp_path / "mirror")

            result = _push_secure_object_mirror_rows(
                provider=provider,
                repository=repository,
                namespace_filter=None,
                limit=None,
                dry_run=False,
            )

            hmac_hex = remote_mirror_object_key_hmac(namespace, raw_row.object_key)
            ciphertext_payload, ciphertext_metadata = provider.get(namespace, hmac_hex)
            manifest_payload, _ = provider.get(
                REMOTE_MIRROR_MANIFEST_NAMESPACE,
                next(iter(provider.iter_objects(REMOTE_MIRROR_MANIFEST_NAMESPACE))).object_key_hmac,
            )
            manifest = RemoteMirrorNamespaceManifest.model_validate_json(manifest_payload)

            assert result["pushed_by_namespace"] == {namespace: 1}
            assert result["manifest_pushed_by_namespace"] == {namespace: 1}
            assert result["failed_objects"] == []
            assert result["failed_manifests"] == []
            assert ciphertext_payload == raw_row.payload
            assert ciphertext_metadata.object_key_hmac == hmac_hex
            assert b"push-path-plaintext" not in manifest_payload
            assert manifest.objects[0].object_key_hmac == hmac_hex
            assert manifest.objects[0].ciphertext_hash == raw_row.ciphertext_hash
            assert manifest.latest_revision_id == raw_row.revision_id
        finally:
            engine.dispose()
