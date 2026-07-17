"""Tests for the master-key provider trio."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

import pytest

from ......core.config import SecretStoreBackend, Settings, override_settings
from ......tests.master_key import EphemeralMasterKeyProvider
from ...crypto import KEY_SIZE
from ...errors import (
    MasterKeyMaterialMissingError,
    SecretStoreError,
    UnsecuredModeRefusedError,
)
from .. import (
    FileFallbackMasterKeyProvider,
    KeyringMasterKeyProvider,
    MasterKeyProvider,
    UnsecuredMasterKeyProvider,
    atomic_write_secure_bytes,
    get_master_key_provider,
    looks_like_real_tax_id,
    refuse_unsecured_with_real_nif,
)
from ._master_key_support import _settings_with_store

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


class TestMasterKeyProviderProtocol:
    """Concrete providers implement the master-key provider protocol."""

    def test_providers_satisfy_protocol(self) -> None:
        providers = [
            EphemeralMasterKeyProvider(),
            KeyringMasterKeyProvider(),
            UnsecuredMasterKeyProvider(),
        ]
        for provider in providers:
            assert isinstance(provider, MasterKeyProvider)


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
        with override_settings(cadrumo_secret_passphrase="torn-state-passphrase"):
            yield store

    def test_single_artifact_torn_states_raise(
        self,
        store_dir: Path,
    ) -> None:
        from ...errors import MasterKeyMaterialMissingError
        from .. import FileFallbackMasterKeyProvider

        torn_artifacts = {
            "master-key-only": ("master.key", b"orphan-master-key"),
            "kdf-only": ("master.kdf", b'{"version": 2, "algorithm": "argon2id"}'),
        }
        for label, (filename, content) in torn_artifacts.items():
            case_dir = store_dir / label
            case_dir.mkdir()
            (case_dir / filename).write_bytes(content)

            provider = FileFallbackMasterKeyProvider(store_dir=case_dir)
            with pytest.raises(MasterKeyMaterialMissingError, match="torn state") as excinfo:
                provider.get_master_key()
            msg = str(excinfo.value)
            assert "aeat config recover --recovery-key" in msg
            assert "aeat config profile create NAME" in msg

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

        with override_settings(cadrumo_secret_passphrase="smoke-passphrase"):
            assert _default_passphrase_callback() == "smoke-passphrase"
            # The Settings entry must survive — subsequent callbacks
            # resolve consistently against the same value.
            stored = load_settings().cadrumo_secret_passphrase
            assert stored is not None
            assert stored.get_secret_value() == "smoke-passphrase"
            assert _default_passphrase_callback() == "smoke-passphrase"

    def test_passphrase_callback_sanitizes_settings_value(self) -> None:
        from .._master_key import _default_passphrase_callback

        with override_settings(cadrumo_secret_passphrase="value-with-newline\n"):
            assert _default_passphrase_callback() == "value-with-newline"

        with override_settings(cadrumo_secret_passphrase="\r\n"), pytest.raises(SecretStoreError):
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

    def test_factory_unsecured_backend_requires_explicit_gate(self, tmp_path: Path) -> None:
        # CADRUMO_ALLOW_UNENCRYPTED=1 is the hostile-named opt-out gate.
        refused_settings = Settings(
            cadrumo_secret_store_dir=tmp_path / "secrets",
            cadrumo_secret_store_backend=SecretStoreBackend.UNSECURED,
            cadrumo_allow_unencrypted="",  # not "1": kill-switch refuses
        )
        with pytest.raises(UnsecuredModeRefusedError, match="CADRUMO_ALLOW_UNENCRYPTED"):
            get_master_key_provider(settings_override=refused_settings)

        allowed_settings = Settings(
            cadrumo_secret_store_dir=tmp_path / "secrets",
            cadrumo_secret_store_backend=SecretStoreBackend.UNSECURED,
            cadrumo_allow_unencrypted="1",  # literal "1" enables the unsecured backend
        )
        provider = get_master_key_provider(settings_override=allowed_settings)
        assert isinstance(provider, UnsecuredMasterKeyProvider)


class TestUnsecuredNifCanary:
    """The unsecured-mode NIF-canary fences off real tax data."""

    def test_tax_id_classification(self) -> None:
        # Random non-tax-id strings are not real — the canary's failure
        # mode is "let the unsecured backend through" rather than refuse;
        # the substrate's other validators reject malformed ids.
        cases = {
            "00000000T": False,
            "X0000000T": False,
            "Z0000000T": False,
            "Y0000000Z": False,
            "B00000000": False,
            "12345678Z": True,
            "X1234567L": True,
            "not-a-tax-id": False,
            "": False,
        }
        for tax_id, expected in cases.items():
            assert looks_like_real_tax_id(tax_id) is expected

    def test_refuse_unsecured_with_real_nif_only_blocks_real_tax_ids_on_unsecured_provider(self) -> None:
        # A keyring or file-fallback provider passes the canary even
        # with a real tax id (the canary gates only the unsecured path).
        refuse_unsecured_with_real_nif("12345678Z", provider=EphemeralMasterKeyProvider())
        # Synthetic placeholders are explicitly allowed.
        refuse_unsecured_with_real_nif("00000000T", provider=UnsecuredMasterKeyProvider())
        with pytest.raises(UnsecuredModeRefusedError, match="real tax id"):
            refuse_unsecured_with_real_nif("12345678Z", provider=UnsecuredMasterKeyProvider())


class TestAtomicWriteSecureBytes:
    def test_roundtrip_preserves_newline_bytes(self, tmp_path: Path) -> None:
        """A 0x0A byte in the master-key payload must survive verbatim.

        The secure-write fd must be opened O_BINARY: on Windows a text-mode fd
        makes os.write translate every 0x0A to 0x0D0A, lengthening the file and
        corrupting the encrypted master-key bytes unrecoverably whenever the
        payload contains a newline byte. This pins the byte-exact contract on
        every platform.
        """
        payload = b"key-head\nkey\r\nmid\x00\x0a\xff-tail\n"
        target = tmp_path / "master.key"
        atomic_write_secure_bytes(target, payload)
        written = target.read_bytes()
        assert written == payload
        assert len(written) == len(payload)

    def test_roundtrip_preserves_random_binary_payload(self, tmp_path: Path) -> None:
        """A full-range random binary payload (key-sized) survives byte-exact."""
        payload = secrets.token_bytes(KEY_SIZE) + b"\x0a" * 4 + secrets.token_bytes(KEY_SIZE)
        target = tmp_path / "master.key"
        atomic_write_secure_bytes(target, payload)
        assert target.read_bytes() == payload
