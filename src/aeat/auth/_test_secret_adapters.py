"""Tests for the read-through secret-store adapter."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ..storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_secret_store,
)
from ..storage.errors import SecretAlreadyExistsError, SecretNotFoundError
from ._secret_adapters import (
    KEY_GOOGLE_OAUTH_CLIENT,
    google_oauth_token_key,
    load_google_oauth_client,
    load_google_oauth_token,
    load_google_service_account,
    load_secret_or_legacy,
    migrate_google_oauth_client_to_secret_store,
    migrate_google_oauth_token_to_secret_store,
    migrate_google_service_account_to_secret_store,
    migrate_legacy_to_secret_store,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


@pytest.fixture
def secret_store(tmp_path: Path) -> Iterator[SecretStore]:
    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_secret_store(store)
    try:
        yield store
    finally:
        override_secret_store(None)


class TestReadThroughBehaviour:
    """``load_secret_or_legacy`` prefers the secret store, falls back gracefully."""

    def test_secret_store_hit_does_not_touch_legacy(
        self,
        secret_store: SecretStore,
        tmp_path: Path,
    ) -> None:
        legacy = tmp_path / "legacy.json"
        legacy.write_text('{"never": "read"}', encoding="utf-8")
        migrate_legacy_to_secret_store(
            key="aeat:test:read-through",
            legacy_path=tmp_path / "source.json",  # source for migration; create below
            # ... actually use the legacy path for migration
        ) if False else None
        from datetime import UTC, datetime, timedelta

        from ..storage import SecretRecord, SensitivityClass

        secret_store.put(
            SecretRecord(
                key="aeat:test:read-through",
                value=b'{"from": "store"}',
                classification=SensitivityClass.SECRET,
                created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        loaded = load_secret_or_legacy(
            key="aeat:test:read-through",
            legacy_path=legacy,
            parser=lambda data: json.loads(data.decode("utf-8")),
        )
        assert loaded == {"from": "store"}

    def test_falls_back_to_legacy_when_store_misses(
        self,
        secret_store: SecretStore,
        tmp_path: Path,
    ) -> None:
        legacy = tmp_path / "legacy.json"
        legacy.write_text('{"from": "legacy"}', encoding="utf-8")
        loaded = load_secret_or_legacy(
            key="aeat:test:miss",
            legacy_path=legacy,
            parser=lambda data: json.loads(data.decode("utf-8")),
        )
        assert loaded == {"from": "legacy"}

    def test_missing_both_raises(self, secret_store: SecretStore, tmp_path: Path) -> None:
        with pytest.raises(SecretNotFoundError):
            load_secret_or_legacy(
                key="aeat:test:absent",
                legacy_path=tmp_path / "does-not-exist.json",
                parser=bytes,
            )


class TestMigrationHelper:
    def test_round_trip(self, secret_store: SecretStore, tmp_path: Path) -> None:
        legacy = tmp_path / "client.json"
        legacy.write_bytes(b'{"client_id": "abc", "client_secret": "xyz"}')
        migrate_legacy_to_secret_store(
            key="aeat:test:mig",
            legacy_path=legacy,
        )
        record = secret_store.get("aeat:test:mig")
        assert record.value == legacy.read_bytes()
        assert record.metadata["migrated_from"] == str(legacy)

    def test_delete_legacy_unlinks_file(self, secret_store: SecretStore, tmp_path: Path) -> None:
        legacy = tmp_path / "delete-me.json"
        legacy.write_bytes(b"{}")
        migrate_legacy_to_secret_store(
            key="aeat:test:del",
            legacy_path=legacy,
            delete_legacy=True,
        )
        assert not legacy.exists()

    def test_collision_without_overwrite_raises(
        self,
        secret_store: SecretStore,
        tmp_path: Path,
    ) -> None:
        legacy = tmp_path / "dup.json"
        legacy.write_bytes(b"{}")
        migrate_legacy_to_secret_store(key="aeat:test:dup", legacy_path=legacy)
        with pytest.raises(SecretAlreadyExistsError):
            migrate_legacy_to_secret_store(key="aeat:test:dup", legacy_path=legacy)

    def test_overwrite_replaces(self, secret_store: SecretStore, tmp_path: Path) -> None:
        legacy = tmp_path / "v.json"
        legacy.write_bytes(b'{"v": 1}')
        migrate_legacy_to_secret_store(key="aeat:test:upd", legacy_path=legacy)
        legacy.write_bytes(b'{"v": 2}')
        migrate_legacy_to_secret_store(
            key="aeat:test:upd",
            legacy_path=legacy,
            overwrite=True,
        )
        assert secret_store.get("aeat:test:upd").value == b'{"v": 2}'

    def test_missing_source_raises(self, secret_store: SecretStore, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            migrate_legacy_to_secret_store(
                key="aeat:test:404",
                legacy_path=tmp_path / "never-existed.json",
            )


class TestNamedHelpers:
    def test_oauth_client_round_trip(self, secret_store: SecretStore, tmp_path: Path) -> None:
        legacy = tmp_path / "oauth-client.json"
        legacy.write_text('{"client_id": "id", "client_secret": "shh"}', encoding="utf-8")
        migrate_google_oauth_client_to_secret_store(legacy)
        loaded = load_google_oauth_client(legacy)
        assert loaded == {"client_id": "id", "client_secret": "shh"}
        # Verify it now lives in the secret store under the canonical key.
        assert secret_store.get(KEY_GOOGLE_OAUTH_CLIENT).value == legacy.read_bytes()

    def test_service_account_round_trip(self, secret_store: SecretStore, tmp_path: Path) -> None:
        legacy = tmp_path / "service-account.json"
        legacy.write_text('{"type": "service_account"}', encoding="utf-8")
        migrate_google_service_account_to_secret_store(legacy)
        assert load_google_service_account(legacy) == {"type": "service_account"}

    def test_oauth_token_round_trip(self, secret_store: SecretStore, tmp_path: Path) -> None:
        legacy = tmp_path / "google_oauth_token.json"
        legacy.write_bytes(b'{"refresh_token": "rt"}')
        migrate_google_oauth_token_to_secret_store(legacy, account="kent@example.com")
        # The per-account key is consulted; default account resolves
        # to the migrated value.
        loaded = load_google_oauth_token(legacy, account="kent@example.com")
        assert loaded == legacy.read_bytes()

    def test_oauth_token_key_namespace(self) -> None:
        assert google_oauth_token_key("alice") == "aeat:google:oauth-token:alice"
        assert google_oauth_token_key("bob@example.com") == "aeat:google:oauth-token:bob@example.com"
