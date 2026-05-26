"""Tests for the materialisation helpers."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from .....core.classification import SensitivityClass
from ..errors import SecretNotFoundError
from ..master_key import EphemeralMasterKeyProvider
from ..secret_store import SecretRecord, SecretStore
from . import EncryptedBlobStore
from ._materialisation import (
    export_to_temp_path,
    materialise_secret,
    override_secret_store,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _expiry() -> datetime:
    return datetime.now(UTC) + timedelta(hours=1)


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


def _put_secret(store: SecretStore, key: str, value: bytes) -> None:
    store.put(
        SecretRecord(
            key=key,
            value=value,
            classification=SensitivityClass.SECRET,
            created_at=datetime.now(UTC),
            expires_at=_expiry(),
        )
    )


class TestMaterialiseSecret:
    """Context-managed secure tempfile holding the plaintext secret."""

    def test_yields_path_with_plaintext(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:m1", b"google-service-account-bytes")
        with materialise_secret("aeat:test:m1") as path:
            assert path.exists()
            assert path.read_bytes() == b"google-service-account-bytes"

    def test_unlinks_on_exit(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:m2", b"x")
        with materialise_secret("aeat:test:m2") as path:
            captured = path
        assert not captured.exists()

    def test_unlinks_on_exception(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:m3", b"y")
        captured: Path | None = None

        class _BoomError(Exception):
            pass

        with pytest.raises(_BoomError), materialise_secret("aeat:test:m3") as path:
            captured = path
            raise _BoomError
        assert captured is not None
        assert not captured.exists()

    def test_missing_key_raises(self, secret_store: SecretStore) -> None:
        with pytest.raises(SecretNotFoundError), materialise_secret("never-stored") as _:
            pytest.fail("should have raised")

    def test_explicit_store_arg(self, secret_store: SecretStore, tmp_path: Path) -> None:
        """Passing a store explicitly bypasses the singleton."""
        provider = EphemeralMasterKeyProvider()
        blob_store = EncryptedBlobStore(
            root_dir=tmp_path / "alt-blobs",
            master_key_provider=provider,
        )
        alt_store = SecretStore(
            store_dir=tmp_path / "alt-secrets",
            blob_store=blob_store,
            master_key_provider=provider,
        )
        _put_secret(alt_store, "aeat:test:alt", b"alternate-payload")
        with materialise_secret("aeat:test:alt", store=alt_store) as path:
            assert path.read_bytes() == b"alternate-payload"

    def test_tempfile_is_mode_0o600(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:perm", b"mode-check")
        with materialise_secret("aeat:test:perm") as path:
            assert path.read_bytes() == b"mode-check"
            if os.name != "posix":
                assert path.exists()
                return
            mode = path.stat().st_mode & 0o777
            assert mode == 0o600

    def test_suffix_passes_through(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:json", b'{"k":"v"}')
        with materialise_secret("aeat:test:json", suffix=".json") as path:
            assert path.suffix == ".json"


class TestExportToTempPath:
    """Explicit-cleanup variant for non-context-managed consumers."""

    def test_returns_path_and_cleanup(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:e1", b"explicit-cleanup")
        path, cleanup = export_to_temp_path("aeat:test:e1")
        try:
            assert path.exists()
            assert path.read_bytes() == b"explicit-cleanup"
        finally:
            cleanup()
        assert not path.exists()

    def test_cleanup_is_idempotent(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:e2", b"x")
        path, cleanup = export_to_temp_path("aeat:test:e2")
        cleanup()
        cleanup()  # second call must not raise
        assert not path.exists()

    def test_missing_key_raises(self, secret_store: SecretStore) -> None:
        with pytest.raises(SecretNotFoundError):
            export_to_temp_path("never-stored")
