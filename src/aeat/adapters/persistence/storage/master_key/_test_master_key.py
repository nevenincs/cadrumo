"""Tests for the master-key provider trio."""

from __future__ import annotations

import base64
import os
import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest

from .....core.config import SecretStoreBackend, Settings
from ..crypto import KEY_SIZE
from ..errors import (
    KeyringUnavailableError,
    MasterKeyUnavailableError,
    SecretStoreError,
    UnsecuredModeRefusedError,
)
from . import (
    EphemeralMasterKeyProvider,
    FileFallbackMasterKeyProvider,
    KeyringMasterKeyProvider,
    MasterKeyProvider,
    UnsecuredMasterKeyProvider,
    get_master_key_provider,
    looks_like_real_tax_id,
    refuse_unsecured_with_real_nif,
)
from ._master_key import (
    PASSPHRASE_ENV_VAR,
    _b64decode,
    _KdfParameters,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


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

        # Distinguish passphrase-mismatch from material-missing. Both
        # inherit from MasterKeyUnavailableError so legacy catchers
        # still work, but the typed subclass lets the CLI render a
        # class-specific actionable hint.
        from ..errors import MasterKeyPassphraseMismatchError

        with pytest.raises(MasterKeyPassphraseMismatchError):
            FileFallbackMasterKeyProvider(
                store_dir=tmp_path / "secrets",
                passphrase_callback=lambda: "wrong",
            ).get_master_key()

    def test_wrong_passphrase_inherits_from_master_key_unavailable(self, tmp_path: Path) -> None:
        """Pre-existing `pytest.raises(MasterKeyUnavailableError)` catchers continue to work via inheritance."""
        FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "right",
        ).get_master_key()

        FileFallbackMasterKeyProvider._reset_for_tests()

        # The narrowed subclass still satisfies the parent type.
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


class TestTornStateGate:
    """get_master_key must refuse on torn install state.

    The ``complete_recovery`` write order is master.key →
    master.kdf → salt; a crash between writes used to silently re-mint
    over the partial state via ``_mint_new``, destroying the recovered
    master.key bytes. The new gate raises
    ``MasterKeyMaterialMissingError`` instead.
    """

    @pytest.fixture
    def store_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        store = tmp_path / "secrets"
        store.mkdir()
        monkeypatch.setenv(PASSPHRASE_ENV_VAR, "torn-state-passphrase")
        return store

    def test_torn_state_master_key_only_raises(
        self,
        store_dir: Path,
    ) -> None:
        # Crash after master.key, before master.kdf and salt.
        (store_dir / "master.key").write_bytes(b"orphan-master-key")

        from ..errors import MasterKeyMaterialMissingError
        from . import FileFallbackMasterKeyProvider

        FileFallbackMasterKeyProvider._reset_for_tests()
        provider = FileFallbackMasterKeyProvider(store_dir=store_dir)
        with pytest.raises(MasterKeyMaterialMissingError, match="torn state") as excinfo:
            provider.get_master_key()
        # The runbook hints both options.
        msg = str(excinfo.value)
        assert "aeat security recover" in msg
        assert "aeat security provision --force" in msg

    def test_torn_state_master_key_plus_kdf_raises(
        self,
        store_dir: Path,
    ) -> None:
        # Crash after master.kdf, before salt.
        (store_dir / "master.key").write_bytes(b"orphan-master-key")
        (store_dir / "master.kdf").write_text(
            '{"version": 2, "algorithm": "argon2id"}',
            encoding="utf-8",
        )

        from ..errors import MasterKeyMaterialMissingError
        from . import FileFallbackMasterKeyProvider

        FileFallbackMasterKeyProvider._reset_for_tests()
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
            encoding="utf-8",
        )
        (store_dir / "salt").write_bytes(b"\x00" * 16)

        from ..errors import MasterKeyMaterialMissingError
        from . import FileFallbackMasterKeyProvider

        FileFallbackMasterKeyProvider._reset_for_tests()
        provider = FileFallbackMasterKeyProvider(store_dir=store_dir)
        with pytest.raises(MasterKeyMaterialMissingError, match="torn state"):
            provider.get_master_key()

    def test_no_install_mints_normally(
        self,
        store_dir: Path,
    ) -> None:
        # No artefacts at all → cold start mint is allowed (the
        # silent-first-run-mint contract).
        from . import FileFallbackMasterKeyProvider

        FileFallbackMasterKeyProvider._reset_for_tests()
        provider = FileFallbackMasterKeyProvider(store_dir=store_dir)
        key = provider.get_master_key()
        assert len(key) == KEY_SIZE
        # All three artefacts now present after the mint.
        for name in ("master.key", "master.kdf", "salt"):
            assert (store_dir / name).exists()


class TestSecurityHardening:
    """Audit-driven hardening fixes."""

    def test_passphrase_env_var_persists_across_callbacks(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The callback must NOT pop the env var.

        The cache in ``FileFallbackMasterKeyProvider`` is reset under
        legitimate flows (recover re-mints, test sessions cycle the
        cache between sub-tests), and a popped env var blocks the
        second cache-miss read on ``getpass`` in non-TTY contexts.
        """
        from ._master_key import _default_passphrase_callback

        monkeypatch.setenv(PASSPHRASE_ENV_VAR, "smoke-passphrase")
        assert _default_passphrase_callback() == "smoke-passphrase"
        # The env var must survive — subsequent callbacks resolve
        # consistently against the same value.
        assert os.environ.get(PASSPHRASE_ENV_VAR) == "smoke-passphrase"
        assert _default_passphrase_callback() == "smoke-passphrase"

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

        # Replace the live backend so the test does not depend on the host's keychain.
        store: dict[tuple[str, str], str] = {}

        def _get(service: str, username: str) -> str | None:
            return store.get((service, username))

        def _set(service: str, username: str, password: str) -> None:
            store[(service, username)] = password

        # Replace the backend probe so it does not trip on the host's
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
        # Either error class is acceptable — the explicit ``keyring``
        # backend rejects the operation rather than silently routing
        # through file. ``MasterKeyKeychainLockedError`` is the
        # narrow class for "backend works but get_password refused"
        # (the keychain-locked taxonomy);
        # ``KeyringUnavailableError`` covers no-backend / package-
        # missing failures. Both extend the substrate's
        # ``SecretStoreError`` parent — accept either so the test
        # is robust across CI runners that DO have a working
        # keyring backend (Windows / macOS / libsecret-installed
        # Linux: get_password path → MasterKeyKeychainLockedError)
        # and runners that don't (no-op fail.Keyring backend
        # surfaced by _probe_backend → KeyringUnavailableError).
        with pytest.raises(SecretStoreError):
            get_master_key_provider(settings_override=settings)

    def test_auto_backend_falls_back_when_keyring_unavailable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # When the keyring backend is genuinely unusable (no usable
        # backend, package missing, ``fail.Keyring`` no-op installed),
        # auto falls back to file unconditionally — there is no
        # keychain-backed master key that a file-fallback could
        # diverge from.
        from ..errors import KeyringUnavailableError
        from . import KeyringMasterKeyProvider

        def _probe_fail() -> None:
            raise KeyringUnavailableError("simulated no-op fail.Keyring backend")

        monkeypatch.setattr(KeyringMasterKeyProvider, "_probe_backend", staticmethod(_probe_fail))
        KeyringMasterKeyProvider._reset_for_tests()
        settings = _settings_with_store(tmp_path, SecretStoreBackend.AUTO)
        provider = get_master_key_provider(
            settings_override=settings,
            passphrase_callback=lambda: "x",
        )
        assert isinstance(provider, FileFallbackMasterKeyProvider)
        assert len(provider.get_master_key()) == KEY_SIZE

    def test_auto_backend_refuses_locked_keychain_without_file_state(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # When the keychain is LOCKED (backend works, get_password
        # refused — Touch ID cancelled, libsecret locked, etc.) AND no
        # file-fallback artefacts exist, auto must NOT silently mint a
        # fresh file-fallback master key that would diverge from
        # whatever the keychain holds. Refuse and surface the lock
        # state so the operator unlocks-and-retries OR explicitly
        # switches to ``AEAT_SECRET_STORE_BACKEND=file``.
        from ..errors import MasterKeyKeychainLockedError
        from . import KeyringMasterKeyProvider

        keyring = pytest.importorskip("keyring")
        from keyring.errors import KeyringError

        def _locked(*_args: object, **_kwargs: object) -> None:
            raise KeyringError("simulated locked keychain")

        monkeypatch.setattr(keyring, "get_password", _locked)
        monkeypatch.setattr(keyring, "set_password", _locked)
        # Pretend the backend probe succeeds — only get_password fails.
        monkeypatch.setattr(KeyringMasterKeyProvider, "_probe_backend", staticmethod(lambda: None))
        KeyringMasterKeyProvider._reset_for_tests()
        settings = _settings_with_store(tmp_path, SecretStoreBackend.AUTO)
        with pytest.raises(MasterKeyKeychainLockedError, match="auto-mode refuses"):
            get_master_key_provider(
                settings_override=settings,
                passphrase_callback=lambda: "x",
            )

    def test_auto_backend_falls_back_when_locked_but_file_exists(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # When the keychain is LOCKED AND file-fallback artefacts
        # already exist, auto routes through file safely — the
        # operator has previously chosen the file backend (or
        # already provisioned both).
        from . import FileFallbackMasterKeyProvider, KeyringMasterKeyProvider

        keyring = pytest.importorskip("keyring")
        from keyring.errors import KeyringError

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
        seed_provider.get_master_key()
        FileFallbackMasterKeyProvider._reset_for_tests()

        monkeypatch.setattr(keyring, "get_password", _locked)
        monkeypatch.setattr(keyring, "set_password", _locked)
        monkeypatch.setattr(KeyringMasterKeyProvider, "_probe_backend", staticmethod(lambda: None))
        KeyringMasterKeyProvider._reset_for_tests()
        settings = _settings_with_store(tmp_path, SecretStoreBackend.AUTO)
        provider = get_master_key_provider(
            settings_override=settings,
            passphrase_callback=lambda: "seed-passphrase",
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
            aeat_allow_unencrypted=False,
        )
        with pytest.raises(UnsecuredModeRefusedError, match="AEAT_ALLOW_UNENCRYPTED"):
            get_master_key_provider(settings_override=settings)

    def test_factory_returns_unsecured_provider_when_gated(self, tmp_path: Path) -> None:
        settings = Settings(
            aeat_secret_store_dir=tmp_path / "secrets",
            aeat_secret_store_backend=SecretStoreBackend.UNSECURED,
            aeat_allow_unencrypted=True,
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
