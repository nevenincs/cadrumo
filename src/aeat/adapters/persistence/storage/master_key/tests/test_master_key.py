"""Tests for the master-key provider trio."""

from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path

import pytest

from ......core.config import SecretStoreBackend, Settings, override_settings
from ......core.external_constants import UTF_8_ENCODING
from ...crypto import KEY_SIZE
from ...errors import (
    KeyringUnavailableError,
    MasterKeyMaterialMissingError,
    SecretStoreError,
    UnsecuredModeRefusedError,
)
from .. import (
    EphemeralMasterKeyProvider,
    FileFallbackMasterKeyProvider,
    KeyringMasterKeyProvider,
    MasterKeyProvider,
    UnsecuredMasterKeyProvider,
    get_master_key_provider,
    looks_like_real_tax_id,
    refuse_unsecured_with_real_nif,
)
from ._master_key_support import _InMemoryKeyringClient, _settings_with_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


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

    def test_torn_state_kdf_only_raises(
        self,
        store_dir: Path,
    ) -> None:
        # Inverted-order torn state: master.kdf present without master.key.
        # The gate refuses regardless of which single artefact survives.
        (store_dir / "master.kdf").write_text(
            '{"version": 2, "algorithm": "argon2id"}',
            encoding=UTF_8_ENCODING,
        )

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
        for name in ("master.key", "master.kdf"):
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
        """The wrapped master key + KDF params land mode 0o600 on POSIX."""
        provider = FileFallbackMasterKeyProvider(
            store_dir=tmp_path / "secrets",
            passphrase_callback=lambda: "test-passphrase",
        )
        provider.provision_master_key()
        for name in ("master.key", "master.kdf"):
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
