"""File-fallback master-key provider tests."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......core.config import SecretStoreBackend, override_settings
from ......core.errors import build_error_envelope
from ......core.external_constants import UTF_8_ENCODING
from ...bucket._manifest import BucketKeySchedule
from ...crypto import KEY_SIZE
from ...errors import (
    DecryptionError,
    MasterKeyMaterialMissingError,
    MasterKeyPassphraseMismatchError,
    MasterKeyUnavailableError,
    SecretStoreError,
)
from .. import FileFallbackMasterKeyProvider, MasterKeyProvider, activate_master_key_provider
from .._active_session import get_active_master_key
from .._master_key import _b64decode, _KdfParameters
from ._master_key_support import _settings_with_store, _write_registered_bucket

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class TestFileFallbackProvider:
    """The file backend mints, persists, and unwraps the master key."""

    def test_get_master_key_refuses_unprovisioned_store(self, tmp_path: Path) -> None:
        provider = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "correct horse battery staple",
        )
        with pytest.raises(MasterKeyMaterialMissingError, match="not provisioned"):
            provider.get_master_key()
        assert not (tmp_path / "secrets" / "master.key").exists()

    def test_explicit_provision_mints_and_persists(self, tmp_path: Path) -> None:
        provider = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "correct horse battery staple",
        )
        key = provider.provision_master_key()
        assert len(key) == KEY_SIZE
        assert (tmp_path / "secrets" / "master.key").exists()
        assert (tmp_path / "secrets" / "master.kdf").exists()
        # The salt is carried inside master.kdf (salt_b64); no standalone
        # salt artefact is written.
        assert not (tmp_path / "secrets" / "salt").exists()

    def test_below_floor_kdf_cost_is_refused_on_read(self, tmp_path: Path) -> None:
        """A tampered master.kdf declaring a below-floor Argon2 cost fails closed.

        The file-fallback KDF parameters carry the same OWASP-baseline validation
        window as the bucket-manifest params, so an attacker (or a buggy writer)
        that lowers ``memory_cost`` below the floor is refused on read rather than
        silently deriving a weakened KEK.
        """
        store_dir = tmp_path / "secrets"
        provider = FileFallbackMasterKeyProvider(
            store_dir=store_dir,
            passphrase_callback=lambda: "correct horse battery staple",
        )
        provider.provision_master_key()

        kdf_path = store_dir / "master.kdf"
        document = json.loads(kdf_path.read_text(encoding=UTF_8_ENCODING))
        document["memory_cost"] = 8  # far below the 19 MiB OWASP floor
        kdf_path.write_text(json.dumps(document), encoding=UTF_8_ENCODING)

        reopened = FileFallbackMasterKeyProvider(
            store_dir=store_dir,
            passphrase_callback=lambda: "correct horse battery staple",
        )
        with pytest.raises(MasterKeyUnavailableError, match="KDF parameters"):
            reopened.get_master_key()

    def test_bootstrap_activation_mints_distinct_persisted_bucket_dek(self, tmp_path: Path) -> None:
        settings = _settings_with_store(tmp_path, SecretStoreBackend.FILE)
        provider = FileFallbackMasterKeyProvider(
            store_dir=settings.aeat_secret_store_dir,
            passphrase_callback=lambda: "correct horse battery staple",
        )
        master_key = provider.provision_master_key()
        bucket_dek_path = settings.aeat_local_storage_root / "keystore" / "alpha" / "bucket.dek.json"

        with (
            override_settings(
                aeat_local_storage_root=settings.aeat_local_storage_root,
                aeat_secret_store_dir=settings.aeat_secret_store_dir,
                aeat_secret_store_backend=SecretStoreBackend.FILE,
            ),
            activate_master_key_provider(
                provider,
                fallback_bucket_id="alpha",
                allow_bucket_dek_enrollment=True,
            ),
        ):
            first_dek = get_active_master_key()

        assert bucket_dek_path.is_file()
        assert first_dek != master_key
        _write_registered_bucket(
            settings.aeat_local_storage_root,
            "alpha",
            key_schedule=BucketKeySchedule.BUCKET_DEK_V1,
        )

        second = FileFallbackMasterKeyProvider(
            store_dir=settings.aeat_secret_store_dir,
            passphrase_callback=lambda: "correct horse battery staple",
        )
        with (
            override_settings(
                aeat_local_storage_root=settings.aeat_local_storage_root,
                aeat_secret_store_dir=settings.aeat_secret_store_dir,
                aeat_secret_store_backend=SecretStoreBackend.FILE,
            ),
            activate_master_key_provider(second, fallback_bucket_id="alpha"),
        ):
            assert get_active_master_key() == first_dek

    def test_tampered_bucket_dek_raises_localized_master_key_unavailable_without_path(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_with_store(tmp_path, SecretStoreBackend.FILE)
        provider = FileFallbackMasterKeyProvider(
            store_dir=settings.aeat_secret_store_dir,
            passphrase_callback=lambda: "correct horse battery staple",
        )
        provider.provision_master_key()
        bucket_dek_path = settings.aeat_local_storage_root / "keystore" / "alpha" / "bucket.dek.json"

        with (
            override_settings(
                aeat_local_storage_root=settings.aeat_local_storage_root,
                aeat_secret_store_dir=settings.aeat_secret_store_dir,
                aeat_secret_store_backend=SecretStoreBackend.FILE,
            ),
            activate_master_key_provider(
                provider,
                fallback_bucket_id="alpha",
                allow_bucket_dek_enrollment=True,
            ),
        ):
            assert len(get_active_master_key()) == KEY_SIZE

        _write_registered_bucket(
            settings.aeat_local_storage_root,
            "alpha",
            key_schedule=BucketKeySchedule.BUCKET_DEK_V1,
        )
        document = json.loads(bucket_dek_path.read_text(encoding=UTF_8_ENCODING))
        document["tag_b64"] = base64.b64encode(b"\x00" * 16).decode("ascii")
        bucket_dek_path.write_text(json.dumps(document), encoding=UTF_8_ENCODING)

        second = FileFallbackMasterKeyProvider(
            store_dir=settings.aeat_secret_store_dir,
            passphrase_callback=lambda: "correct horse battery staple",
        )
        with (
            override_settings(
                aeat_local_storage_root=settings.aeat_local_storage_root,
                aeat_secret_store_dir=settings.aeat_secret_store_dir,
                aeat_secret_store_backend=SecretStoreBackend.FILE,
            ),
            pytest.raises(MasterKeyUnavailableError) as excinfo,
            activate_master_key_provider(second, fallback_bucket_id="alpha"),
        ):
            pass

        assert isinstance(excinfo.value.__cause__, DecryptionError)
        assert excinfo.value.translated_message == "errors.auth.auth_storage_master_key_unavailable"
        assert str(tmp_path) not in str(excinfo.value)
        envelope = build_error_envelope(excinfo.value)
        assert str(tmp_path) not in envelope.model_dump_json()

    def test_bucket_dek_manifest_without_dek_fails_closed(self, tmp_path: Path) -> None:
        settings = _settings_with_store(tmp_path, SecretStoreBackend.FILE)
        settings.aeat_local_storage_root.mkdir(parents=True, exist_ok=True)
        _write_registered_bucket(
            settings.aeat_local_storage_root,
            "current",
            key_schedule=BucketKeySchedule.BUCKET_DEK_V1,
        )
        provider = FileFallbackMasterKeyProvider(
            store_dir=settings.aeat_secret_store_dir,
            passphrase_callback=lambda: "correct horse battery staple",
        )
        provider.provision_master_key()
        bucket_dek_path = settings.aeat_local_storage_root / "keystore" / "current" / "bucket.dek.json"

        with (
            override_settings(
                aeat_local_storage_root=settings.aeat_local_storage_root,
                aeat_secret_store_dir=settings.aeat_secret_store_dir,
                aeat_secret_store_backend=SecretStoreBackend.FILE,
            ),
            pytest.raises(MasterKeyMaterialMissingError, match="bucket-dek-v1"),
            activate_master_key_provider(provider, fallback_bucket_id="current"),
        ):
            pass

        assert not bucket_dek_path.exists()

    def test_fallback_bucket_id_does_not_authorize_dek_enrollment(self, tmp_path: Path) -> None:
        settings = _settings_with_store(tmp_path, SecretStoreBackend.FILE)
        provider = FileFallbackMasterKeyProvider(
            store_dir=settings.aeat_secret_store_dir,
            passphrase_callback=lambda: "correct horse battery staple",
        )
        provider.provision_master_key()
        bucket_dek_path = settings.aeat_local_storage_root / "keystore" / "missing" / "bucket.dek.json"

        with (
            override_settings(
                aeat_local_storage_root=settings.aeat_local_storage_root,
                aeat_secret_store_dir=settings.aeat_secret_store_dir,
                aeat_secret_store_backend=SecretStoreBackend.FILE,
            ),
            pytest.raises(MasterKeyMaterialMissingError, match="no manifest"),
            activate_master_key_provider(provider, fallback_bucket_id="missing"),
        ):
            pass

        assert not bucket_dek_path.exists()

    def test_existing_dek_without_manifest_does_not_authorize_activation(self, tmp_path: Path) -> None:
        settings = _settings_with_store(tmp_path, SecretStoreBackend.FILE)
        provider = FileFallbackMasterKeyProvider(
            store_dir=settings.aeat_secret_store_dir,
            passphrase_callback=lambda: "correct horse battery staple",
        )
        provider.provision_master_key()
        with (
            override_settings(
                aeat_local_storage_root=settings.aeat_local_storage_root,
                aeat_secret_store_dir=settings.aeat_secret_store_dir,
                aeat_secret_store_backend=SecretStoreBackend.FILE,
            ),
            activate_master_key_provider(
                provider,
                fallback_bucket_id="orphaned",
                allow_bucket_dek_enrollment=True,
            ),
        ):
            assert len(get_active_master_key()) == KEY_SIZE
        assert (settings.aeat_local_storage_root / "keystore" / "orphaned" / "bucket.dek.json").is_file()

        second = FileFallbackMasterKeyProvider(
            store_dir=settings.aeat_secret_store_dir,
            passphrase_callback=lambda: "correct horse battery staple",
        )
        with (
            override_settings(
                aeat_local_storage_root=settings.aeat_local_storage_root,
                aeat_secret_store_dir=settings.aeat_secret_store_dir,
                aeat_secret_store_backend=SecretStoreBackend.FILE,
            ),
            pytest.raises(MasterKeyMaterialMissingError, match="no manifest"),
            activate_master_key_provider(second, fallback_bucket_id="orphaned"),
        ):
            pass
        assert (settings.aeat_local_storage_root / "keystore" / "orphaned" / "bucket.dek.json").is_file()

    def test_bucket_manifest_idle_lock_overrides_settings_default(self, tmp_path: Path) -> None:
        settings = _settings_with_store(tmp_path, SecretStoreBackend.FILE)
        settings.aeat_local_storage_root.mkdir(parents=True, exist_ok=True)
        provider = FileFallbackMasterKeyProvider(
            store_dir=settings.aeat_secret_store_dir,
            passphrase_callback=lambda: "correct horse battery staple",
        )
        provider.provision_master_key()

        # Mint the per-bucket DEK first (the BUCKET_DEK_V1 schedule requires a
        # wrapped DEK on disk), then register the idle-lock manifest.
        with (
            override_settings(
                aeat_local_storage_root=settings.aeat_local_storage_root,
                aeat_secret_store_dir=settings.aeat_secret_store_dir,
                aeat_secret_store_backend=SecretStoreBackend.FILE,
            ),
            activate_master_key_provider(
                provider,
                fallback_bucket_id="short-idle",
                allow_bucket_dek_enrollment=True,
            ),
        ):
            assert get_active_master_key() != provider.get_master_key()
        _write_registered_bucket(settings.aeat_local_storage_root, "short-idle", idle_lock_minutes=3)

        with (
            override_settings(
                aeat_local_storage_root=settings.aeat_local_storage_root,
                aeat_secret_store_dir=settings.aeat_secret_store_dir,
                aeat_secret_store_backend=SecretStoreBackend.FILE,
                aeat_bucket_default_idle_lock_minutes=15,
            ),
            activate_master_key_provider(provider, fallback_bucket_id="short-idle"),
        ):
            assert provider._session is not None
            remaining = provider._session.idle_deadline - datetime.now(UTC)
            assert 120 <= remaining.total_seconds() <= 181

    def test_round_trip_across_provider_instances(self, tmp_path: Path) -> None:
        """A second provider over the same dir + passphrase recovers the same key."""
        first = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "correct horse battery staple",
        )
        first_key = first.provision_master_key()

        second = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "correct horse battery staple",
        )
        second_key = second.get_master_key()
        assert first_key == second_key

    def test_wrong_passphrase_raises_typed_subclass_of_master_key_unavailable(self, tmp_path: Path) -> None:
        FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "right-passphrase",
        ).provision_master_key()

        # Distinguish passphrase-mismatch from material-missing. Both
        # inherit from MasterKeyUnavailableError so legacy catchers
        # still work, but the typed subclass lets the CLI render a
        # class-specific actionable hint.
        with pytest.raises(MasterKeyUnavailableError) as excinfo:
            FileFallbackMasterKeyProvider(
                store_dir=tmp_path / "secrets",
                passphrase_callback=lambda: "wrong-passphrase",
            ).get_master_key()
        assert isinstance(excinfo.value, MasterKeyPassphraseMismatchError)
        assert excinfo.value.translated_message == "errors.auth.auth_storage_master_key_passphrase_mismatch"

    def test_passphrase_via_settings(self, tmp_path: Path) -> None:
        with override_settings(aeat_secret_passphrase="from-env-var"):
            provider = FileFallbackMasterKeyProvider(store_dir=tmp_path / "secrets")
            key = provider.provision_master_key()
            assert len(key) == KEY_SIZE

    def test_empty_passphrase_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(SecretStoreError):
            FileFallbackMasterKeyProvider(
                store_dir=tmp_path / "secrets",
                passphrase_callback=lambda: "",
            ).get_master_key()

    def test_kdf_params_are_human_readable(self, tmp_path: Path) -> None:
        provider = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "test-passphrase",
        )
        provider.provision_master_key()
        params_text = (tmp_path / "secrets" / "master.kdf").read_text(encoding=UTF_8_ENCODING)
        params = _KdfParameters.model_validate_json(params_text)
        assert params.version == 2
        assert params.algorithm == "argon2id"
        assert params.memory_cost == 19 * 1024
        assert params.time_cost == 2
        assert params.parallelism == 1
        assert len(_b64decode(params.salt_b64)) == 16

    def test_master_key_file_is_ciphertext_not_plaintext(self, tmp_path: Path) -> None:
        """The persisted master.key MUST not contain the plaintext key bytes."""
        provider = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "test-passphrase",
        )
        plaintext_key = provider.provision_master_key()
        wrapped = base64.b64decode(
            (tmp_path / "secrets" / "master.key").read_bytes(),
            validate=True,
        )
        assert plaintext_key not in wrapped

    def test_tampered_master_key_file_raises_localized_without_path(self, tmp_path: Path) -> None:
        provider = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "test-passphrase",
        )
        provider.provision_master_key()
        master_key_path = tmp_path / "secrets" / "master.key"
        contents = base64.b64decode(master_key_path.read_bytes(), validate=True)
        tampered = bytes([contents[0] ^ 0x01]) + contents[1:]
        master_key_path.write_bytes(base64.b64encode(tampered))

        with pytest.raises(MasterKeyUnavailableError) as excinfo:
            FileFallbackMasterKeyProvider(
                store_dir=tmp_path / "secrets",
                passphrase_callback=lambda: "test-passphrase",
            ).get_master_key()

        assert excinfo.value.translated_message == "errors.auth.auth_storage_master_key_passphrase_mismatch"
        assert str(tmp_path) not in str(excinfo.value)
        envelope = build_error_envelope(excinfo.value)
        assert str(tmp_path) not in envelope.model_dump_json()

    def test_malformed_kdf_file_raises_localized_without_path(self, tmp_path: Path) -> None:
        provider = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "test-passphrase",
        )
        provider.provision_master_key()
        (tmp_path / "secrets" / "master.kdf").write_text("not-json", encoding=UTF_8_ENCODING)

        with pytest.raises(MasterKeyUnavailableError) as excinfo:
            FileFallbackMasterKeyProvider(
                store_dir=tmp_path / "secrets",
                passphrase_callback=lambda: "test-passphrase",
            ).get_master_key()

        assert excinfo.value.translated_message == "errors.auth.auth_storage_master_key_unavailable"
        assert str(tmp_path) not in str(excinfo.value)
        envelope = build_error_envelope(excinfo.value)
        assert str(tmp_path) not in envelope.model_dump_json()

    def test_satisfies_protocol(self, tmp_path: Path) -> None:
        provider = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "test-passphrase",
        )
        assert isinstance(provider, MasterKeyProvider)
