"""Pin the fail-closed contract on the master-key passphrase resolver.

The passphrase resolver is part of the live-write security perimeter.
The Settings DI migration MUST preserve the existing failure modes:

- ``cadrumo_secret_passphrase=None`` refuses in non-interactive sessions
  instead of hanging on the interactive prompt.
- A SecretStr containing only trailing CRLF strips to empty and
  raises ``SecretStoreError``, matching the historic "env-var set to
  raw newline" failure mode.
- A non-empty SecretStr is returned with trailing CRLF stripped.

Tests exercise the real Settings override path; no env-var
manipulation, no patching of the resolver itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from ......core.config import override_settings
from ...crypto import decrypt_record, encrypt_record
from ...errors import (
    MasterKeyPassphraseMismatchError,
    PassphraseTooShortError,
    SecretStoreError,
)
from .._master_key import FileFallbackMasterKeyProvider, _default_passphrase_callback

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_AAD = b"cadrumo.test.record.aad"


def test_passphrase_present_in_settings_is_returned_with_crlf_stripped() -> None:
    with override_settings(cadrumo_secret_passphrase=SecretStr("super-secret\r\n")):
        assert _default_passphrase_callback() == "super-secret"


def test_crlf_only_passphrase_raises_secret_store_error() -> None:
    with (
        override_settings(cadrumo_secret_passphrase=SecretStr("\r\n")),
        pytest.raises(SecretStoreError, match="whitespace-only"),
    ):
        _default_passphrase_callback()


def test_unset_passphrase_refuses_noninteractive_prompt() -> None:
    """Unset settings fail closed under pytest's non-interactive stdin capture."""
    with (
        override_settings(cadrumo_secret_passphrase=None),
        pytest.raises(SecretStoreError, match="CADRUMO_SECRET_PASSPHRASE"),
    ):
        _default_passphrase_callback()


# ---------------------------------------------------------------------------
# Passphrase change preserves encrypted data and fails closed on a
# rejected candidate. A passphrase change is the file provider's
# ``complete_recovery`` rewrap: the master key (hence every record encrypted
# under it) is preserved, and an invalid candidate passphrase is refused before
# any artefact is rewritten, so the established custody survives untouched.
# ---------------------------------------------------------------------------


def _provider(store_dir: Path, passphrase: str) -> FileFallbackMasterKeyProvider:
    return FileFallbackMasterKeyProvider(store_dir=store_dir, passphrase_callback=lambda: passphrase)


def test_passphrase_change_preserves_master_key_and_encrypted_data(tmp_path: Path) -> None:
    store_dir = tmp_path / "secrets"
    old_passphrase = "correct horse battery staple"  # noqa: S105 - synthetic test fixture
    new_passphrase = "brand new operator passphrase"  # noqa: S105 - synthetic test fixture

    original = _provider(store_dir, old_passphrase)
    master_key = original.provision_master_key()
    # A record encrypted under the master key before the passphrase change.
    blob = encrypt_record(b"a sensitive financial record", key=master_key, associated_data=_AAD)

    # Passphrase change: rewrap the same master key under the new passphrase.
    _provider(store_dir, new_passphrase).complete_recovery(master_key)

    reopened = _provider(store_dir, new_passphrase)
    assert reopened.get_master_key() == master_key
    # The pre-change ciphertext still decrypts under the preserved master key.
    assert decrypt_record(blob, key=reopened.get_master_key(), associated_data=_AAD) == b"a sensitive financial record"
    # The old passphrase no longer opens the store.
    with pytest.raises(MasterKeyPassphraseMismatchError):
        _provider(store_dir, old_passphrase).get_master_key()


def test_rejected_candidate_passphrase_leaves_store_openable_and_data_intact(tmp_path: Path) -> None:
    store_dir = tmp_path / "secrets"
    established = "correct horse battery staple"

    provider = _provider(store_dir, established)
    master_key = provider.provision_master_key()
    blob = encrypt_record(b"a sensitive financial record", key=master_key, associated_data=_AAD)
    key_bytes_before = (store_dir / "master.key").read_bytes()

    # A too-short candidate passphrase is refused before any artefact is written.
    with pytest.raises(PassphraseTooShortError):
        _provider(store_dir, "short").complete_recovery(master_key)

    # The established custody is untouched: same on-disk key artefact, the store
    # still opens under the established passphrase, and the record still decrypts.
    assert (store_dir / "master.key").read_bytes() == key_bytes_before
    reopened = _provider(store_dir, established)
    assert reopened.get_master_key() == master_key
    assert decrypt_record(blob, key=reopened.get_master_key(), associated_data=_AAD) == b"a sensitive financial record"
