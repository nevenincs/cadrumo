"""Tests for the materialisation helpers."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......core.classification import SensitivityClass
from ......core.config import Settings
from ......tests.master_key import EphemeralMasterKeyProvider
from ...errors import SecretNotFoundError, StorageValidationError
from ...secret_store import SecretRecord, SecretStore
from .. import EncryptedBlobStore
from .._materialisation import (
    export_to_temp_path,
    get_secret_store,
    materialise_secret,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_SECRET_CREATED_AT = datetime(2026, 5, 28, 11, 50, 0, tzinfo=UTC)
_SECRET_EXPIRES_AT = datetime(2099, 5, 28, 11, 50, 0, tzinfo=UTC)
_UNSAFE_TEMPFILE_AFFIX_CASES: tuple[tuple[str, str, str, str], ...] = (
    ("parent-prefix", "../cadrumo-secret", "", "prefix"),
    ("backslash-prefix", "cadrumo\\secret", "", "prefix"),
    ("dot-prefix", ".", "", "prefix"),
    ("parent-suffix", "cadrumo-secret", "../secret", "suffix"),
    ("backslash-suffix", "cadrumo-secret", "secret\\json", "suffix"),
    ("dotdot-suffix", "cadrumo-secret", "..", "suffix"),
)


@pytest.fixture
def secret_store(tmp_path: Path) -> SecretStore:
    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    return SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )


def _put_secret(store: SecretStore, key: str, value: bytes) -> None:
    store.put(
        SecretRecord(
            key=key,
            value=value,
            classification=SensitivityClass.SECRET,
            created_at=_SECRET_CREATED_AT,
            expires_at=_SECRET_EXPIRES_AT,
        ),
    )


def test_secret_store_factory_caches_each_explicit_route_independently(tmp_path: Path) -> None:
    """A second Settings route never inherits the first route's cached store."""
    settings_a = Settings(
        cadrumo_secret_store_dir=tmp_path / "root-a" / "secrets",
        cadrumo_blob_store_dir=tmp_path / "root-a" / "blobs",
    )
    settings_b = Settings(
        cadrumo_secret_store_dir=tmp_path / "root-b" / "secrets",
        cadrumo_blob_store_dir=tmp_path / "root-b" / "blobs",
    )
    settings_c = Settings(
        cadrumo_secret_store_dir=settings_a.cadrumo_secret_store_dir,
        cadrumo_blob_store_dir=tmp_path / "root-c" / "blobs",
    )
    store_a = get_secret_store(settings=settings_a)
    store_b = get_secret_store(settings=settings_b)
    store_c = get_secret_store(settings=settings_c)

    assert store_a is get_secret_store(settings=settings_a)
    assert store_b is get_secret_store(settings=settings_b)
    assert store_a is not store_b
    assert store_a is not store_c
    assert store_a.store_dir == settings_a.cadrumo_secret_store_dir
    assert store_b.store_dir == settings_b.cadrumo_secret_store_dir
    assert store_c.store_dir == settings_c.cadrumo_secret_store_dir


def test_rejects_path_bearing_tempfile_affixes(secret_store: SecretStore) -> None:
    for api_name in ("context", "export"):
        for case_id, prefix, suffix, field_name in _UNSAFE_TEMPFILE_AFFIX_CASES:
            secret_key = f"aeat:test:{api_name}:{case_id}"
            _put_secret(secret_store, secret_key, b"payload")

            if api_name == "context":
                with (
                    pytest.raises(StorageValidationError) as excinfo,
                    materialise_secret(secret_key, store=secret_store, prefix=prefix, suffix=suffix),
                ):
                    raise AssertionError("materialisation should reject unsafe affix before yielding")
            else:
                with pytest.raises(StorageValidationError) as excinfo:
                    export_to_temp_path(secret_key, store=secret_store, prefix=prefix, suffix=suffix)

            assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation", case_id
            assert excinfo.value.context == {
                "field": field_name,
                "surface": "secret_materialisation",
            }, case_id


def test_missing_key_raises_for_materialisation_apis(secret_store: SecretStore) -> None:
    with pytest.raises(SecretNotFoundError), materialise_secret("never-stored", store=secret_store):
        raise AssertionError("materialisation should fail before yielding")

    with pytest.raises(SecretNotFoundError):
        export_to_temp_path("never-stored", store=secret_store)


def test_cleanup_missing_path_is_logged_at_debug_for_materialisation_apis(
    secret_store: SecretStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _put_secret(secret_store, "aeat:test:context-cleanup", b"payload")
    with caplog.at_level("DEBUG"), materialise_secret("aeat:test:context-cleanup", store=secret_store) as path:
        path.unlink()
    assert "secret materialisation cleanup skipped missing temp path" in caplog.text

    caplog.clear()
    _put_secret(secret_store, "aeat:test:cleanup-log", b"payload")
    path, cleanup = export_to_temp_path("aeat:test:cleanup-log", store=secret_store)
    path.unlink()
    with caplog.at_level("DEBUG"):
        cleanup()
    assert "secret materialisation cleanup skipped missing temp path" in caplog.text


class TestMaterialiseSecret:
    """Context-managed secure tempfile holding the plaintext secret."""

    def test_yields_path_with_plaintext(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:m1", b"google-service-account-bytes")
        with materialise_secret("aeat:test:m1", store=secret_store) as path:
            assert path.exists()
            assert path.read_bytes() == b"google-service-account-bytes"

    def test_unlinks_on_exit(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:m2", b"x")
        with materialise_secret("aeat:test:m2", store=secret_store) as path:
            captured = path
        assert not captured.exists()

    def test_unlinks_on_exception(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:m3", b"y")
        captured: Path | None = None

        class _BoomError(Exception):
            pass

        with pytest.raises(_BoomError), materialise_secret("aeat:test:m3", store=secret_store) as path:
            captured = path
            raise _BoomError
        assert captured is not None
        assert not captured.exists()

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
        with materialise_secret("aeat:test:perm", store=secret_store) as path:
            assert path.read_bytes() == b"mode-check"
            if os.name != "posix":
                assert path.exists()
                return
            mode = path.stat().st_mode & 0o777
            assert mode == 0o600

    def test_suffix_passes_through(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:json", b'{"k":"v"}')
        with materialise_secret("aeat:test:json", store=secret_store, suffix=".json") as path:
            assert path.suffix == ".json"

    def test_large_secret_payload_is_fully_written(self, secret_store: SecretStore) -> None:
        payload = (b"large-secret-materialisation" * 8192) + b"tail"
        _put_secret(secret_store, "aeat:test:large", payload)

        with materialise_secret("aeat:test:large", store=secret_store) as path:
            assert path.read_bytes() == payload


class TestExportToTempPath:
    """Explicit-cleanup variant for non-context-managed consumers."""

    def test_returns_path_and_cleanup(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:e1", b"explicit-cleanup")
        path, cleanup = export_to_temp_path("aeat:test:e1", store=secret_store)
        try:
            assert path.exists()
            assert path.read_bytes() == b"explicit-cleanup"
        finally:
            cleanup()
        assert not path.exists()

    def test_cleanup_is_idempotent(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:e2", b"x")
        path, cleanup = export_to_temp_path("aeat:test:e2", store=secret_store)
        cleanup()
        cleanup()  # second call must not raise
        assert not path.exists()

    def test_cleanup_retries_after_unlink_failure(self, secret_store: SecretStore) -> None:
        _put_secret(secret_store, "aeat:test:cleanup-retry", b"payload")
        path, cleanup = export_to_temp_path("aeat:test:cleanup-retry", store=secret_store)
        path.unlink()
        path.mkdir()

        with pytest.raises(OSError):
            cleanup()

        assert path.is_dir()
        path.rmdir()
        cleanup()
        cleanup()
        assert not path.exists()
