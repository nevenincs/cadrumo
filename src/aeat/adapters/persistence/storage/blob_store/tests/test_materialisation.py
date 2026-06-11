"""Tests for the materialisation helpers."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ......core.classification import SensitivityClass
from ...errors import SecretNotFoundError, StorageValidationError
from ...master_key import EphemeralMasterKeyProvider
from ...secret_store import SecretRecord, SecretStore
from .. import EncryptedBlobStore
from .._materialisation import (
    export_to_temp_path,
    materialise_secret,
    override_secret_store,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


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
        ),
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

    def test_large_secret_payload_is_fully_written(self, secret_store: SecretStore) -> None:
        payload = (b"large-secret-materialisation" * 8192) + b"tail"
        _put_secret(secret_store, "aeat:test:large", payload)

        with materialise_secret("aeat:test:large") as path:
            assert path.read_bytes() == payload

    @pytest.mark.parametrize(
        ("prefix", "suffix"),
        (
            ("../aeat-secret", ""),
            ("aeat\\secret", ""),
            (".", ""),
            ("aeat-secret", "../secret"),
            ("aeat-secret", "secret\\json"),
            ("aeat-secret", ".."),
        ),
    )
    def test_rejects_path_bearing_tempfile_affixes(
        self,
        secret_store: SecretStore,
        prefix: str,
        suffix: str,
    ) -> None:
        _put_secret(secret_store, "aeat:test:affix", b"payload")

        with (
            pytest.raises(StorageValidationError) as excinfo,
            materialise_secret("aeat:test:affix", prefix=prefix, suffix=suffix),
        ):
            raise AssertionError("materialisation should reject unsafe affix before yielding")

        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"
        assert excinfo.value.context == {
            "field": "prefix" if prefix in {"../aeat-secret", "aeat\\secret", "."} else "suffix",
            "surface": "secret_materialisation",
        }

    def test_context_cleanup_missing_path_is_logged_at_debug(
        self,
        secret_store: SecretStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        _put_secret(secret_store, "aeat:test:context-cleanup", b"payload")

        with caplog.at_level("DEBUG"), materialise_secret("aeat:test:context-cleanup") as path:
            path.unlink()

        assert "secret materialisation cleanup skipped missing temp path" in caplog.text


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

    @pytest.mark.parametrize(
        ("prefix", "suffix"),
        (
            ("../aeat-secret", ""),
            ("aeat\\secret", ""),
            (".", ""),
            ("aeat-secret", "../secret"),
            ("aeat-secret", "secret\\json"),
            ("aeat-secret", ".."),
        ),
    )
    def test_rejects_path_bearing_tempfile_affixes(
        self,
        secret_store: SecretStore,
        prefix: str,
        suffix: str,
    ) -> None:
        _put_secret(secret_store, "aeat:test:export-affix", b"payload")

        with pytest.raises(StorageValidationError) as excinfo:
            export_to_temp_path("aeat:test:export-affix", prefix=prefix, suffix=suffix)

        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"
        assert excinfo.value.context == {
            "field": "prefix" if prefix in {"../aeat-secret", "aeat\\secret", "."} else "suffix",
            "surface": "secret_materialisation",
        }

    def test_cleanup_missing_path_is_logged_at_debug(
        self,
        secret_store: SecretStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        _put_secret(secret_store, "aeat:test:cleanup-log", b"payload")
        path, cleanup = export_to_temp_path("aeat:test:cleanup-log")
        path.unlink()

        with caplog.at_level("DEBUG"):
            cleanup()

        assert "secret materialisation cleanup skipped missing temp path" in caplog.text

    def test_cleanup_retries_after_unlink_failure(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:cleanup-retry", b"payload")
        path, cleanup = export_to_temp_path("aeat:test:cleanup-retry")
        path.unlink()
        path.mkdir()

        with pytest.raises(OSError):
            cleanup()

        assert path.is_dir()
        path.rmdir()
        cleanup()
        cleanup()
        assert not path.exists()
