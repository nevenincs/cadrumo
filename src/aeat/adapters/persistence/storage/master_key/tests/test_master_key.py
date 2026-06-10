"""Tests for the master-key provider trio."""

from __future__ import annotations

import base64
import json
import os
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......core.config import SecretStoreBackend, Settings, override_settings
from ......core.errors import build_error_envelope
from ......core.external_constants import UTF_8_ENCODING
from ...bucket._layout import provision_bucket_directory
from ...bucket._manifest import (
    BucketKeySchedule,
    BucketLifecycleStatus,
    BucketManifest,
    ManifestKdfParams,
)
from ...bucket._manifest_io import write_manifest
from ...crypto import KEY_SIZE
from ...errors import (
    DecryptionError,
    KeyringUnavailableError,
    MasterKeyMaterialMissingError,
    MasterKeyUnavailableError,
    SecretStoreError,
    UnsecuredModeRefusedError,
)
from .. import (
    EphemeralMasterKeyProvider,
    FileFallbackMasterKeyProvider,
    KeyringMasterKeyProvider,
    MasterKeyProvider,
    UnsecuredMasterKeyProvider,
    activate_master_key_provider,
    get_master_key_provider,
    looks_like_real_tax_id,
    refuse_unsecured_with_real_nif,
)
from .._active_session import get_active_master_key
from .._master_key import (
    _b64decode,
    _KdfParameters,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class _InMemoryKeyringClient:
    """In-process :class:`KeyringClient` backed by a dict.

    A real implementation of the KeyringClient protocol whose store
    lives in process memory instead of the host's OS keychain. Used
    so the keyring-provider contract (probe / get / set / round-trip)
    can be exercised end-to-end without touching the developer's real
    keychain. Constructor hooks let individual tests inject probe /
    get / set behaviours that cover every failure mode the production
    provider must handle.
    """

    def __init__(
        self,
        *,
        probe: Callable[[], None] | None = None,
        get: Callable[[str, str], str | None] | None = None,
        set_: Callable[[str, str, str], None] | None = None,
        seeded: dict[tuple[str, str], str] | None = None,
    ) -> None:
        self._probe = probe or (lambda: None)
        self._store: dict[tuple[str, str], str] = dict(seeded or {})
        self._get_override = get
        self._set_override = set_

    def probe_backend(self) -> None:
        self._probe()

    def get_password(self, service: str, username: str) -> str | None:
        if self._get_override is not None:
            return self._get_override(service, username)
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        if self._set_override is not None:
            self._set_override(service, username, password)
            return
        self._store[(service, username)] = password


def _settings_with_store(tmp_path: Path, backend: SecretStoreBackend) -> Settings:
    return Settings(
        aeat_local_storage_root=tmp_path / "state",
        aeat_secret_store_dir=tmp_path / "secrets",
        aeat_secret_store_backend=backend,
    )


def _write_registered_bucket(
    root: Path,
    bucket_id: str,
    *,
    idle_lock_minutes: int | None = None,
    key_schedule: BucketKeySchedule = BucketKeySchedule.BUCKET_DEK_V1,
) -> None:
    paths = provision_bucket_directory(root, bucket_id)
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=bucket_id,
            label=bucket_id,
            created_at=datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC),
            last_unlocked_at=None,
            kdf_params=ManifestKdfParams(
                algorithm="argon2id",
                version=19,
                memory_cost=19_456,
                time_cost=2,
                parallelism=1,
                salt=b"0123456789abcdef",
                output_length=32,
            ),
            recovery_enrolled=False,
            idle_lock_minutes=idle_lock_minutes,
            key_schedule=key_schedule,
            schema_version=1,
            status=BucketLifecycleStatus.ACTIVE,
        ),
    )


class TestEphemeralProvider:
    """The ephemeral provider gives tests a deterministic master key."""

    def test_returns_supplied_key(self) -> None:
        key = secrets.token_bytes(KEY_SIZE)
        provider = EphemeralMasterKeyProvider(key=key)
        assert provider.get_master_key() == key

    def test_mints_random_key_when_none(self) -> None:
        a = EphemeralMasterKeyProvider().get_master_key()
        b = EphemeralMasterKeyProvider().get_master_key()
        assert len(a) == KEY_SIZE
        assert a != b

    def test_rejects_wrong_size_key(self) -> None:
        with pytest.raises(SecretStoreError):
            EphemeralMasterKeyProvider(key=b"too-short")

    def test_satisfies_protocol(self) -> None:
        provider = EphemeralMasterKeyProvider()
        assert isinstance(provider, MasterKeyProvider)


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
        assert (tmp_path / "secrets" / "salt").exists()
        assert (tmp_path / "secrets" / "master.key").exists()
        assert (tmp_path / "secrets" / "master.kdf").exists()

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

    def test_wrong_passphrase_raises(self, tmp_path: Path) -> None:
        FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "right-passphrase",
        ).provision_master_key()

        # Distinguish passphrase-mismatch from material-missing. Both
        # inherit from MasterKeyUnavailableError so legacy catchers
        # still work, but the typed subclass lets the CLI render a
        # class-specific actionable hint.
        from ...errors import MasterKeyPassphraseMismatchError

        with pytest.raises(MasterKeyPassphraseMismatchError) as excinfo:
            FileFallbackMasterKeyProvider(
                store_dir=tmp_path / "secrets",
                passphrase_callback=lambda: "wrong-passphrase",
            ).get_master_key()
        assert excinfo.value.translated_message == "errors.auth.auth_storage_master_key_passphrase_mismatch"

    def test_wrong_passphrase_inherits_from_master_key_unavailable(self, tmp_path: Path) -> None:
        """Pre-existing `pytest.raises(MasterKeyUnavailableError)` catchers continue to work via inheritance."""
        FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "right-passphrase",
        ).provision_master_key()

        # The narrowed subclass still satisfies the parent type.
        with pytest.raises(MasterKeyUnavailableError):
            FileFallbackMasterKeyProvider(
                store_dir=tmp_path / "secrets",
                passphrase_callback=lambda: "wrong-passphrase",
            ).get_master_key()

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


class TestKeyringProvider:
    """Keyring provider tests using a protocol-compatible in-process backend."""

    def test_get_after_explicit_provision_round_trip(self) -> None:
        service = f"aeat:test:{secrets.token_hex(8)}"
        client = _InMemoryKeyringClient()
        provider = KeyringMasterKeyProvider(service=service, client=client)

        first = provider.provision_master_key()
        second = KeyringMasterKeyProvider(service=service, client=client).get_master_key()

        assert len(first) == KEY_SIZE
        assert first == second

    def test_satisfies_protocol(self) -> None:
        assert isinstance(KeyringMasterKeyProvider(), MasterKeyProvider)


class TestKeyringFailureSurfaces:
    """The keyring provider surfaces failures via ``KeyringUnavailableError``."""

    def test_malformed_stored_value_raises(self) -> None:
        from .._master_key import KEYRING_USERNAME

        service = f"aeat:test:{secrets.token_hex(8)}"
        client = _InMemoryKeyringClient(seeded={(service, KEYRING_USERNAME): "not!base64!"})
        provider = KeyringMasterKeyProvider(service=service, client=client)
        with pytest.raises(KeyringUnavailableError):
            provider.get_master_key()

    def test_wrong_size_stored_value_raises(self) -> None:
        from .._master_key import KEYRING_USERNAME

        service = f"aeat:test:{secrets.token_hex(8)}"
        too_short = base64.b64encode(b"short").decode("ascii")
        client = _InMemoryKeyringClient(seeded={(service, KEYRING_USERNAME): too_short})
        provider = KeyringMasterKeyProvider(service=service, client=client)
        with pytest.raises(KeyringUnavailableError):
            provider.get_master_key()

    def test_set_password_failure_raises(self) -> None:
        from keyring.errors import KeyringError

        def _fail_set(service: str, username: str, password: str) -> None:
            raise KeyringError("simulated backend failure")

        service = f"aeat:test:{secrets.token_hex(8)}"
        client = _InMemoryKeyringClient(set_=_fail_set)
        provider = KeyringMasterKeyProvider(service=service, client=client)
        with pytest.raises(KeyringUnavailableError):
            provider.provision_master_key()


class TestTornStateGate:
    """get_master_key must refuse on torn install state.

    The ``complete_recovery`` write order is master.key →
    master.kdf → salt; a crash between writes used to silently re-mint
    over the partial state via ``_mint_new``, destroying the recovered
    master.key bytes. The new gate raises
    ``MasterKeyMaterialMissingError`` instead.
    """

    @pytest.fixture
    def store_dir(self, tmp_path: Path):
        store = tmp_path / "secrets"
        store.mkdir()
        with override_settings(aeat_secret_passphrase="torn-state-passphrase"):
            yield store

    def test_torn_state_master_key_only_raises(
        self,
        store_dir: Path,
    ) -> None:
        # Crash after master.key, before master.kdf and salt.
        (store_dir / "master.key").write_bytes(b"orphan-master-key")

        from ...errors import MasterKeyMaterialMissingError
        from .. import FileFallbackMasterKeyProvider

        provider = FileFallbackMasterKeyProvider(store_dir=store_dir)
        with pytest.raises(MasterKeyMaterialMissingError, match="torn state") as excinfo:
            provider.get_master_key()
        # The runbook hints both options.
        msg = str(excinfo.value)
        assert "aeat config recover --recovery-key" in msg
        assert "aeat config profile create NAME" in msg

    def test_torn_state_master_key_plus_kdf_raises(
        self,
        store_dir: Path,
    ) -> None:
        # Crash after master.kdf, before salt.
        (store_dir / "master.key").write_bytes(b"orphan-master-key")
        (store_dir / "master.kdf").write_text(
            '{"version": 2, "algorithm": "argon2id"}',
            encoding=UTF_8_ENCODING,
        )

        from ...errors import MasterKeyMaterialMissingError
        from .. import FileFallbackMasterKeyProvider

        provider = FileFallbackMasterKeyProvider(store_dir=store_dir)
        with pytest.raises(MasterKeyMaterialMissingError, match="torn state"):
            provider.get_master_key()

    def test_torn_state_kdf_plus_salt_only_raises(
        self,
        store_dir: Path,
    ) -> None:
        # Inverted-order torn state (master.kdf + salt without
        # master.key). The gate refuses regardless of which subset.
        (store_dir / "master.kdf").write_text(
            '{"version": 2, "algorithm": "argon2id"}',
            encoding=UTF_8_ENCODING,
        )
        (store_dir / "salt").write_bytes(b"\x00" * 16)

        from ...errors import MasterKeyMaterialMissingError
        from .. import FileFallbackMasterKeyProvider

        provider = FileFallbackMasterKeyProvider(store_dir=store_dir)
        with pytest.raises(MasterKeyMaterialMissingError, match="torn state"):
            provider.get_master_key()

    def test_no_install_refuses_implicit_mint(
        self,
        store_dir: Path,
    ) -> None:
        # No artefacts at all require explicit enrollment; the read path
        # must not silently create key material.
        from .. import FileFallbackMasterKeyProvider

        provider = FileFallbackMasterKeyProvider(store_dir=store_dir)
        with pytest.raises(MasterKeyMaterialMissingError, match="not provisioned"):
            provider.get_master_key()
        for name in ("master.key", "master.kdf", "salt"):
            assert not (store_dir / name).exists()


class TestSecurityHardening:
    """Audit-driven hardening fixes."""

    def test_passphrase_persists_across_callbacks(
        self,
        tmp_path: Path,
    ) -> None:
        """The callback must NOT clear the resolved passphrase.

        The cache in ``FileFallbackMasterKeyProvider`` is reset under
        legitimate flows (recover re-mints, test sessions cycle the
        cache between sub-tests), and a popped source would block the
        second cache-miss read on ``getpass`` in non-TTY contexts.
        """
        from ......core.config import load_settings
        from .._master_key import _default_passphrase_callback

        with override_settings(aeat_secret_passphrase="smoke-passphrase"):
            assert _default_passphrase_callback() == "smoke-passphrase"
            # The Settings entry must survive — subsequent callbacks
            # resolve consistently against the same value.
            stored = load_settings().aeat_secret_passphrase
            assert stored is not None
            assert stored.get_secret_value() == "smoke-passphrase"
            assert _default_passphrase_callback() == "smoke-passphrase"

    def test_passphrase_strips_trailing_crlf(self) -> None:
        from .._master_key import _default_passphrase_callback

        with override_settings(aeat_secret_passphrase="value-with-newline\n"):
            assert _default_passphrase_callback() == "value-with-newline"

    def test_passphrase_whitespace_only_rejected(self) -> None:
        from .._master_key import _default_passphrase_callback

        with override_settings(aeat_secret_passphrase="\r\n"), pytest.raises(SecretStoreError):
            _default_passphrase_callback()

    def test_master_key_files_are_mode_0o600(self, tmp_path: Path) -> None:
        """The wrapped master key + KDF params + salt land mode 0o600 on POSIX."""
        provider = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "test-passphrase",
        )
        provider.provision_master_key()
        for name in ("master.key", "master.kdf", "salt"):
            path = tmp_path / "secrets" / name
            assert path.is_file()
            if os.name != "posix":
                continue
            mode = path.stat().st_mode & 0o777
            assert mode == 0o600, f"{name} must be 0o600; got {oct(mode)}"

    def test_keyring_no_op_backend_refused(self) -> None:
        """The fail.Keyring backend MUST be refused so the auto path falls back."""

        def _refuse() -> None:
            raise KeyringUnavailableError("OS keychain backend is the no-op fail.Keyring")

        client = _InMemoryKeyringClient(probe=_refuse)
        provider = KeyringMasterKeyProvider(service=f"aeat:test:{secrets.token_hex(8)}", client=client)
        with pytest.raises(KeyringUnavailableError):
            provider.get_master_key()

    def test_keyring_cache_is_per_service(self) -> None:
        """Two providers bound to distinct services do NOT share cached keys."""

        shared = _InMemoryKeyringClient()
        service_a = f"aeat:test:{secrets.token_hex(8)}"
        service_b = f"aeat:test:{secrets.token_hex(8)}"

        key_a = KeyringMasterKeyProvider(service=service_a, client=shared).provision_master_key()
        key_b = KeyringMasterKeyProvider(service=service_b, client=shared).provision_master_key()
        assert key_a != key_b
        # Re-binding the first service must return the same key (still cached).
        assert KeyringMasterKeyProvider(service=service_a, client=shared).get_master_key() == key_a

    def test_keyring_round_trip_disagreement_raises(self) -> None:
        """Explicit provision detects a backend that drops the stored value."""

        # "Silent dropper": set_password swallows the value; get_password
        # afterwards returns None.
        client = _InMemoryKeyringClient(
            get=lambda service, username: None,
            set_=lambda service, username, password: None,
        )
        provider = KeyringMasterKeyProvider(service=f"aeat:test:{secrets.token_hex(8)}", client=client)
        with pytest.raises(KeyringUnavailableError):
            provider.provision_master_key()


class TestFactory:
    """``get_master_key_provider`` honours the configured backend."""

    def test_explicit_file_backend(self, tmp_path: Path) -> None:
        settings = _settings_with_store(tmp_path, SecretStoreBackend.FILE)
        provider = get_master_key_provider(
            settings_override=settings,
            passphrase_callback=lambda: "test-passphrase",
        )
        assert isinstance(provider, FileFallbackMasterKeyProvider)
        with pytest.raises(MasterKeyMaterialMissingError, match="not provisioned"):
            provider.get_master_key()

    def test_unknown_backend_raises(self, tmp_path: Path) -> None:
        settings = _settings_with_store(tmp_path, SecretStoreBackend.FILE)
        with pytest.raises(SecretStoreError):
            get_master_key_provider(backend="not-a-real-backend", settings_override=settings)

    def test_keyring_backend_propagates_failure(
        self,
        tmp_path: Path,
    ) -> None:
        from keyring.errors import KeyringError

        def _refuse(*_args: object, **_kwargs: object) -> None:
            raise KeyringError("no backend in this test")

        client = _InMemoryKeyringClient(get=_refuse, set_=_refuse)
        settings = _settings_with_store(tmp_path, SecretStoreBackend.KEYRING)
        # The explicit ``keyring`` backend returns the provider without
        # provisioning. The first read still rejects the operation
        # rather than silently routing through file.
        provider = get_master_key_provider(settings_override=settings, keyring_client=client)
        with pytest.raises(SecretStoreError):
            provider.get_master_key()

    def test_auto_backend_falls_back_when_keyring_unavailable(
        self,
        tmp_path: Path,
    ) -> None:
        # When the keyring backend is genuinely unusable (no usable
        # backend, package missing, ``fail.Keyring`` no-op installed),
        # auto falls back to file unconditionally — there is no
        # keychain-backed master key that a file-fallback could
        # diverge from.
        from ...errors import KeyringUnavailableError

        def _probe_fail() -> None:
            raise KeyringUnavailableError("simulated no-op fail.Keyring backend")

        client = _InMemoryKeyringClient(probe=_probe_fail)
        settings = _settings_with_store(tmp_path, SecretStoreBackend.AUTO)
        provider = get_master_key_provider(
            settings_override=settings,
            passphrase_callback=lambda: "test-passphrase",
            keyring_client=client,
        )
        assert isinstance(provider, FileFallbackMasterKeyProvider)
        with pytest.raises(MasterKeyMaterialMissingError, match="not provisioned"):
            provider.get_master_key()

    def test_auto_backend_refuses_locked_keychain_without_file_state(
        self,
        tmp_path: Path,
    ) -> None:
        # When the keychain is LOCKED (backend works, get_password
        # refused — Touch ID cancelled, libsecret locked, etc.) AND no
        # file-fallback artefacts exist, auto must NOT silently mint a
        # fresh file-fallback master key that would diverge from
        # whatever the keychain holds. Refuse and surface the lock
        # state so the operator unlocks-and-retries OR explicitly
        # switches to ``AEAT_SECRET_STORE_BACKEND=file``.
        from keyring.errors import KeyringError

        from ...errors import MasterKeyKeychainLockedError

        def _locked(*_args: object, **_kwargs: object) -> None:
            raise KeyringError("simulated locked keychain")

        client = _InMemoryKeyringClient(get=_locked, set_=_locked)
        settings = _settings_with_store(tmp_path, SecretStoreBackend.AUTO)
        with pytest.raises(MasterKeyKeychainLockedError, match="auto-mode refuses"):
            get_master_key_provider(
                settings_override=settings,
                passphrase_callback=lambda: "test-passphrase",
                keyring_client=client,
            )

    def test_auto_backend_falls_back_when_locked_but_file_exists(
        self,
        tmp_path: Path,
    ) -> None:
        # When the keychain is LOCKED AND file-fallback artefacts
        # already exist, auto routes through file safely — the
        # operator has previously chosen the file backend (or
        # already provisioned both).
        from keyring.errors import KeyringError

        from .. import FileFallbackMasterKeyProvider

        def _locked(*_args: object, **_kwargs: object) -> None:
            raise KeyringError("simulated locked keychain")

        # Seed the file-fallback artefacts via a real
        # FileFallbackMasterKeyProvider mint so the substrate's
        # canonical form lands on disk.
        store_dir = tmp_path / "secrets"
        seed_provider = FileFallbackMasterKeyProvider(
            store_dir=store_dir,
            passphrase_callback=lambda: "seed-passphrase",
        )
        seed_provider.provision_master_key()
        client = _InMemoryKeyringClient(get=_locked, set_=_locked)
        settings = _settings_with_store(tmp_path, SecretStoreBackend.AUTO)
        provider = get_master_key_provider(
            settings_override=settings,
            passphrase_callback=lambda: "seed-passphrase",
            keyring_client=client,
        )
        assert isinstance(provider, FileFallbackMasterKeyProvider)
        assert len(provider.get_master_key()) == KEY_SIZE


class TestUnsecuredProvider:
    """Hostile-named opt-out backend for testing / throwaway scenarios."""

    def test_returns_published_deterministic_key(self) -> None:
        # The published key is part of the substrate's public contract:
        # anyone with the source can decrypt unsecured-mode ciphertext.
        first = UnsecuredMasterKeyProvider().get_master_key()
        second = UnsecuredMasterKeyProvider().get_master_key()
        assert first == second
        assert len(first) == KEY_SIZE
        # The key's prefix must encode its insecurity in plaintext.
        assert first.startswith(b"AEAT_UNSECURED_TEST_KEY")

    def test_satisfies_master_key_provider_protocol(self) -> None:
        provider = UnsecuredMasterKeyProvider()
        assert isinstance(provider, MasterKeyProvider)

    def test_factory_refuses_without_allow_unencrypted(self, tmp_path: Path) -> None:
        # AEAT_ALLOW_UNENCRYPTED=1 is the hostile-named opt-out gate.
        settings = Settings(
            aeat_secret_store_dir=tmp_path / "secrets",
            aeat_secret_store_backend=SecretStoreBackend.UNSECURED,
            aeat_allow_unencrypted="",  # not "1": kill-switch refuses
        )
        with pytest.raises(UnsecuredModeRefusedError, match="AEAT_ALLOW_UNENCRYPTED"):
            get_master_key_provider(settings_override=settings)

    def test_factory_returns_unsecured_provider_when_gated(self, tmp_path: Path) -> None:
        settings = Settings(
            aeat_secret_store_dir=tmp_path / "secrets",
            aeat_secret_store_backend=SecretStoreBackend.UNSECURED,
            aeat_allow_unencrypted="1",  # literal "1" enables the unsecured backend
        )
        provider = get_master_key_provider(settings_override=settings)
        assert isinstance(provider, UnsecuredMasterKeyProvider)


class TestUnsecuredNifCanary:
    """The unsecured-mode NIF-canary fences off real tax data."""

    @pytest.mark.parametrize(
        "synthetic_id",
        ["00000000T", "X0000000T", "Z0000000T", "Y0000000Z", "B00000000"],
    )
    def test_synthetic_tax_ids_are_not_treated_as_real(self, synthetic_id: str) -> None:
        assert looks_like_real_tax_id(synthetic_id) is False

    @pytest.mark.parametrize(
        "real_id",
        ["12345678Z", "X1234567L"],  # NIF + NIE shapes that validate.
    )
    def test_valid_non_synthetic_tax_ids_are_treated_as_real(self, real_id: str) -> None:
        assert looks_like_real_tax_id(real_id) is True

    def test_invalid_inputs_are_not_treated_as_real(self) -> None:
        # Random non-tax-id strings are not real — the canary's failure
        # mode is "let the unsecured backend through" rather than refuse;
        # the substrate's other validators reject malformed ids.
        assert looks_like_real_tax_id("not-a-tax-id") is False
        assert looks_like_real_tax_id("") is False

    def test_refuse_unsecured_with_real_nif_no_op_for_other_providers(self) -> None:
        # A keyring or file-fallback provider passes the canary even
        # with a real tax id (the canary gates only the unsecured path).
        provider = EphemeralMasterKeyProvider()
        # No raise.
        refuse_unsecured_with_real_nif("12345678Z", provider=provider)

    def test_refuse_unsecured_with_real_nif_raises_for_unsecured_provider(self) -> None:
        provider = UnsecuredMasterKeyProvider()
        with pytest.raises(UnsecuredModeRefusedError, match="real tax id"):
            refuse_unsecured_with_real_nif("12345678Z", provider=provider)

    def test_refuse_unsecured_with_real_nif_passes_for_synthetic(self) -> None:
        provider = UnsecuredMasterKeyProvider()
        # No raise — synthetic placeholders are explicitly allowed.
        refuse_unsecured_with_real_nif("00000000T", provider=provider)
