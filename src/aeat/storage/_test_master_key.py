"""Tests for the master-key provider trio."""

from __future__ import annotations

import base64
import os
import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest

from ..config import SecretStoreBackend, Settings
from . import (
    KEY_SIZE,
    EphemeralMasterKeyProvider,
    FileFallbackMasterKeyProvider,
    KeyringMasterKeyProvider,
    KeyringUnavailableError,
    MasterKeyKdfVersionError,
    MasterKeyProvider,
    MasterKeyUnavailableError,
    SecretStoreError,
    get_master_key_provider,
    migrate_master_key_kdf,
)
from ._crypto import encrypt_record
from ._master_key import (
    PASSPHRASE_ENV_VAR,
    _b64decode,
    _b64encode,
    _derive_legacy_scrypt_kek,
    _KdfParameters,
    _LegacyKdfParameters,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _settings_with_store(tmp_path: Path, backend: SecretStoreBackend) -> Settings:
    return Settings(
        aeat_secret_store_dir=tmp_path / "secrets",
        aeat_secret_store_backend=backend,
    )


@pytest.fixture(autouse=True)
def _reset_caches() -> Iterator[None]:
    """Clear in-process caches between tests so providers behave deterministically."""
    KeyringMasterKeyProvider._reset_for_tests()
    FileFallbackMasterKeyProvider._reset_for_tests()
    yield
    KeyringMasterKeyProvider._reset_for_tests()
    FileFallbackMasterKeyProvider._reset_for_tests()


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

    def test_mint_and_persist(self, tmp_path: Path) -> None:
        provider = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "correct horse battery staple",
        )
        key = provider.get_master_key()
        assert len(key) == KEY_SIZE
        assert (tmp_path / "secrets" / "salt").exists()
        assert (tmp_path / "secrets" / "master.key").exists()
        assert (tmp_path / "secrets" / "master.kdf").exists()

    def test_round_trip_across_provider_instances(self, tmp_path: Path) -> None:
        """A second provider over the same dir + passphrase recovers the same key."""
        first = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "correct horse battery staple",
        )
        first_key = first.get_master_key()

        FileFallbackMasterKeyProvider._reset_for_tests()

        second = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "correct horse battery staple",
        )
        second_key = second.get_master_key()
        assert first_key == second_key

    def test_wrong_passphrase_raises(self, tmp_path: Path) -> None:
        FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "right",
        ).get_master_key()

        FileFallbackMasterKeyProvider._reset_for_tests()

        with pytest.raises(MasterKeyUnavailableError):
            FileFallbackMasterKeyProvider(
                store_dir=tmp_path / "secrets",
                passphrase_callback=lambda: "wrong",
            ).get_master_key()

    def test_passphrase_via_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(PASSPHRASE_ENV_VAR, "from-env-var")
        provider = FileFallbackMasterKeyProvider(store_dir=tmp_path / "secrets")
        key = provider.get_master_key()
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
            passphrase_callback=lambda: "x",
        )
        provider.get_master_key()
        params_text = (tmp_path / "secrets" / "master.kdf").read_text(encoding="utf-8")
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
            passphrase_callback=lambda: "x",
        )
        plaintext_key = provider.get_master_key()
        wrapped = base64.b64decode(
            (tmp_path / "secrets" / "master.key").read_bytes(),
            validate=True,
        )
        assert plaintext_key not in wrapped

    def test_tampered_master_key_file_raises(self, tmp_path: Path) -> None:
        provider = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "x",
        )
        provider.get_master_key()
        master_key_path = tmp_path / "secrets" / "master.key"
        contents = base64.b64decode(master_key_path.read_bytes(), validate=True)
        tampered = bytes([contents[0] ^ 0x01]) + contents[1:]
        master_key_path.write_bytes(base64.b64encode(tampered))

        FileFallbackMasterKeyProvider._reset_for_tests()

        with pytest.raises(MasterKeyUnavailableError):
            FileFallbackMasterKeyProvider(
                store_dir=tmp_path / "secrets",
                passphrase_callback=lambda: "x",
            ).get_master_key()

    def test_satisfies_protocol(self, tmp_path: Path) -> None:
        provider = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "x",
        )
        assert isinstance(provider, MasterKeyProvider)


class TestKeyringProvider:
    """Live keyring tests gated on the platform shipping a usable backend."""

    @pytest.fixture
    def keyring_module(self):
        keyring = pytest.importorskip("keyring")
        from keyring.errors import NoKeyringError

        try:
            keyring.get_password("aeat:test:probe", "probe")
        except NoKeyringError:
            pytest.skip("no usable OS keychain backend on this host")
        return keyring

    def test_get_or_mint_round_trip(self, keyring_module) -> None:
        service = f"aeat:test:{secrets.token_hex(8)}"
        provider = KeyringMasterKeyProvider(service=service)
        try:
            first = provider.get_master_key()
            assert len(first) == KEY_SIZE
            KeyringMasterKeyProvider._reset_for_tests()
            second = KeyringMasterKeyProvider(service=service).get_master_key()
            assert first == second
        finally:
            keyring_module.delete_password(service, "master")

    def test_satisfies_protocol(self) -> None:
        assert isinstance(KeyringMasterKeyProvider(), MasterKeyProvider)


class TestKeyringFailureSurfaces:
    """The keyring provider surfaces failures via ``KeyringUnavailableError``."""

    def test_malformed_stored_value_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        keyring = pytest.importorskip("keyring")

        monkeypatch.setattr(keyring, "get_password", lambda service, username: "not!base64!")
        provider = KeyringMasterKeyProvider(service=f"aeat:test:{secrets.token_hex(8)}")
        with pytest.raises(KeyringUnavailableError):
            provider.get_master_key()

    def test_wrong_size_stored_value_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        keyring = pytest.importorskip("keyring")

        too_short = base64.b64encode(b"short").decode("ascii")
        monkeypatch.setattr(keyring, "get_password", lambda service, username: too_short)
        provider = KeyringMasterKeyProvider(service=f"aeat:test:{secrets.token_hex(8)}")
        with pytest.raises(KeyringUnavailableError):
            provider.get_master_key()

    def test_set_password_failure_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        keyring = pytest.importorskip("keyring")
        from keyring.errors import KeyringError

        def _fail_set(service: str, username: str, password: str) -> None:
            raise KeyringError("simulated backend failure")

        monkeypatch.setattr(keyring, "get_password", lambda service, username: None)
        monkeypatch.setattr(keyring, "set_password", _fail_set)
        provider = KeyringMasterKeyProvider(service=f"aeat:test:{secrets.token_hex(8)}")
        with pytest.raises(KeyringUnavailableError):
            provider.get_master_key()


class TestSecurityHardening:
    """Audit-driven hardening fixes (sec H-1 / H-2, vaultspec H-1 / H-2)."""

    def test_passphrase_env_var_popped_after_use(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The default callback must pop AEAT_SECRET_PASSPHRASE so children do not inherit."""
        from ._master_key import _default_passphrase_callback

        monkeypatch.setenv(PASSPHRASE_ENV_VAR, "smoke-passphrase")
        assert _default_passphrase_callback() == "smoke-passphrase"
        assert PASSPHRASE_ENV_VAR not in os.environ

    def test_passphrase_env_var_strips_trailing_crlf(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from ._master_key import _default_passphrase_callback

        monkeypatch.setenv(PASSPHRASE_ENV_VAR, "value-with-newline\n")
        assert _default_passphrase_callback() == "value-with-newline"

    def test_passphrase_env_var_whitespace_only_rejected(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from ._master_key import _default_passphrase_callback

        monkeypatch.setenv(PASSPHRASE_ENV_VAR, "\r\n")
        with pytest.raises(SecretStoreError):
            _default_passphrase_callback()

    @pytest.mark.skipif(os.name != "posix", reason="POSIX-only file mode bits")
    def test_master_key_files_are_mode_0o600(self, tmp_path: Path) -> None:
        """The wrapped master key + KDF params + salt land mode 0o600 on POSIX."""
        provider = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "x",
        )
        provider.get_master_key()
        for name in ("master.key", "master.kdf", "salt"):
            mode = (tmp_path / "secrets" / name).stat().st_mode & 0o777
            assert mode == 0o600, f"{name} must be 0o600; got {oct(mode)}"

    def test_keyring_no_op_backend_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The fail.Keyring backend MUST be refused so the auto path falls back."""
        keyring = pytest.importorskip("keyring")
        from keyring.backends import fail

        monkeypatch.setattr(keyring, "get_keyring", lambda: fail.Keyring())
        provider = KeyringMasterKeyProvider(service=f"aeat:test:{secrets.token_hex(8)}")
        with pytest.raises(KeyringUnavailableError):
            provider.get_master_key()

    def test_keyring_cache_is_per_service(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two providers bound to distinct services do NOT share cached keys."""
        keyring = pytest.importorskip("keyring")

        # Stub the live backend so the test does not depend on the host's keychain.
        store: dict[tuple[str, str], str] = {}

        def _get(service: str, username: str) -> str | None:
            return store.get((service, username))

        def _set(service: str, username: str, password: str) -> None:
            store[(service, username)] = password

        # Stub the backend probe so it does not trip on the host's
        # actual fail.Keyring detection.
        monkeypatch.setattr(KeyringMasterKeyProvider, "_probe_backend", staticmethod(lambda: None))
        monkeypatch.setattr(keyring, "get_password", _get)
        monkeypatch.setattr(keyring, "set_password", _set)

        service_a = f"aeat:test:{secrets.token_hex(8)}"
        service_b = f"aeat:test:{secrets.token_hex(8)}"

        key_a = KeyringMasterKeyProvider(service=service_a).get_master_key()
        key_b = KeyringMasterKeyProvider(service=service_b).get_master_key()
        assert key_a != key_b
        # Re-binding the first service must return the same key (still cached).
        assert KeyringMasterKeyProvider(service=service_a).get_master_key() == key_a

    def test_keyring_round_trip_disagreement_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A backend that accepts set_password but drops the value MUST be detected."""
        keyring = pytest.importorskip("keyring")

        # The "silent dropper" — set_password succeeds but get_password
        # afterwards returns None.
        monkeypatch.setattr(KeyringMasterKeyProvider, "_probe_backend", staticmethod(lambda: None))
        monkeypatch.setattr(keyring, "get_password", lambda service, username: None)
        monkeypatch.setattr(keyring, "set_password", lambda service, username, password: None)

        provider = KeyringMasterKeyProvider(service=f"aeat:test:{secrets.token_hex(8)}")
        with pytest.raises(KeyringUnavailableError):
            provider.get_master_key()


class TestFactory:
    """``get_master_key_provider`` honours the configured backend."""

    def test_explicit_file_backend(self, tmp_path: Path) -> None:
        settings = _settings_with_store(tmp_path, SecretStoreBackend.FILE)
        provider = get_master_key_provider(
            settings_override=settings,
            passphrase_callback=lambda: "x",
        )
        assert isinstance(provider, FileFallbackMasterKeyProvider)
        assert len(provider.get_master_key()) == KEY_SIZE

    def test_unknown_backend_raises(self, tmp_path: Path) -> None:
        settings = _settings_with_store(tmp_path, SecretStoreBackend.FILE)
        with pytest.raises(SecretStoreError):
            get_master_key_provider(backend="not-a-real-backend", settings_override=settings)

    def test_keyring_backend_propagates_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        keyring = pytest.importorskip("keyring")
        from keyring.errors import KeyringError

        def _refuse(*_args: object, **_kwargs: object) -> None:
            raise KeyringError("no backend in this test")

        monkeypatch.setattr(keyring, "get_password", _refuse)
        monkeypatch.setattr(keyring, "set_password", _refuse)
        settings = _settings_with_store(tmp_path, SecretStoreBackend.KEYRING)
        with pytest.raises(KeyringUnavailableError):
            get_master_key_provider(settings_override=settings)

    def test_auto_backend_falls_back_to_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        keyring = pytest.importorskip("keyring")
        from keyring.errors import KeyringError

        def _refuse(*_args: object, **_kwargs: object) -> None:
            raise KeyringError("simulated unavailable keychain")

        monkeypatch.setattr(keyring, "get_password", _refuse)
        monkeypatch.setattr(keyring, "set_password", _refuse)
        settings = _settings_with_store(tmp_path, SecretStoreBackend.AUTO)
        provider = get_master_key_provider(
            settings_override=settings,
            passphrase_callback=lambda: "x",
        )
        assert isinstance(provider, FileFallbackMasterKeyProvider)
        assert len(provider.get_master_key()) == KEY_SIZE


def _seed_legacy_v1_store(store_dir: Path, *, passphrase: str) -> bytes:
    """Lay down a v1 (scrypt) ``master.key`` + ``master.kdf`` + ``salt`` triplet.

    Returns the plaintext master key so tests can assert that the
    migration preserves the original key bytes.
    """
    store_dir.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_bytes(16)
    legacy_params = _LegacyKdfParameters(
        version=1,
        algorithm="scrypt",
        n=2**14,
        r=8,
        p=1,
        salt_b64=_b64encode(salt),
    )
    passphrase_bytes = passphrase.encode("utf-8")
    legacy_kek = _derive_legacy_scrypt_kek(passphrase_bytes, salt, legacy_params)
    master_key = secrets.token_bytes(KEY_SIZE)
    blob = encrypt_record(master_key, key=legacy_kek, associated_data=b"aeat.master-key.v1")
    (store_dir / "salt").write_bytes(salt)
    (store_dir / "master.kdf").write_text(legacy_params.model_dump_json(), encoding="utf-8")
    (store_dir / "master.key").write_bytes(base64.b64encode(blob.to_wire()))
    return master_key


class TestWave12KdfMigration:
    """scrypt -> Argon2id one-shot migration of the file-fallback master.kdf."""

    def test_v1_store_blocks_load_with_runbook_pointer(self, tmp_path: Path) -> None:
        """A pre-migration v1 store cannot be loaded; the error names the migration tool."""
        store = tmp_path / "secrets"
        _seed_legacy_v1_store(store, passphrase="hunter2")

        with pytest.raises(MasterKeyKdfVersionError) as exc_info:
            FileFallbackMasterKeyProvider(
                store_dir=store,
                passphrase_callback=lambda: "hunter2",
            ).get_master_key()
        assert "migrate-master-key-kdf" in str(exc_info.value)

    def test_migrate_v1_to_v2_preserves_master_key(self, tmp_path: Path) -> None:
        """The migration re-wraps without changing the master-key bytes."""
        store = tmp_path / "secrets"
        plaintext_master_key = _seed_legacy_v1_store(store, passphrase="hunter2")

        result = migrate_master_key_kdf(
            store_dir=store,
            passphrase=b"hunter2",
        )
        assert result.migrated == 1
        assert result.skipped == 0

        # File backend now loads cleanly under v2.
        provider = FileFallbackMasterKeyProvider(
            store_dir=store,
            passphrase_callback=lambda: "hunter2",
        )
        loaded = provider.get_master_key()
        assert loaded == plaintext_master_key

        # master.kdf is on v2 and uses Argon2id.
        params = _KdfParameters.model_validate_json(
            (store / "master.kdf").read_text(encoding="utf-8"),
        )
        assert params.version == 2
        assert params.algorithm == "argon2id"
        assert params.memory_cost == 19 * 1024
        assert params.time_cost == 2
        assert params.parallelism == 1

    def test_migrate_idempotent_on_v2_store(self, tmp_path: Path) -> None:
        """Re-running the migration on an already-v2 store is a no-op."""
        store = tmp_path / "secrets"
        # Provision a fresh v2 store via the regular mint path.
        FileFallbackMasterKeyProvider(
            store_dir=store,
            passphrase_callback=lambda: "hunter2",
        ).get_master_key()

        result = migrate_master_key_kdf(store_dir=store, passphrase=b"hunter2")
        assert result.migrated == 0
        assert result.skipped == 1

    def test_migrate_wrong_passphrase_keeps_v1_intact(self, tmp_path: Path) -> None:
        """Wrong passphrase aborts the migration and leaves the v1 store on disk untouched."""
        store = tmp_path / "secrets"
        _seed_legacy_v1_store(store, passphrase="correct")
        before_kdf = (store / "master.kdf").read_bytes()
        before_key = (store / "master.key").read_bytes()

        with pytest.raises(MasterKeyUnavailableError):
            migrate_master_key_kdf(store_dir=store, passphrase=b"wrong")

        assert (store / "master.kdf").read_bytes() == before_kdf
        assert (store / "master.key").read_bytes() == before_key

    def test_migrate_missing_artefact_raises(self, tmp_path: Path) -> None:
        """A missing master.kdf / master.key / salt aborts the migration."""
        store = tmp_path / "secrets"
        _seed_legacy_v1_store(store, passphrase="hunter2")
        (store / "salt").unlink()

        with pytest.raises(MasterKeyUnavailableError):
            migrate_master_key_kdf(store_dir=store, passphrase=b"hunter2")

    def test_v2_load_round_trip_no_migration_needed(self, tmp_path: Path) -> None:
        """A fresh v2 mint round-trips through unwrap without invoking the migrator."""
        store = tmp_path / "secrets"
        first = FileFallbackMasterKeyProvider(
            store_dir=store,
            passphrase_callback=lambda: "hunter2",
        )
        first_key = first.get_master_key()

        FileFallbackMasterKeyProvider._reset_for_tests()

        second = FileFallbackMasterKeyProvider(
            store_dir=store,
            passphrase_callback=lambda: "hunter2",
        )
        assert second.get_master_key() == first_key
