"""Tests for the recovery-key + BIP-39 mnemonic encoding."""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest

from ......core.external_constants import UTF_8_ENCODING
from ...errors import DecryptionError, StorageValidationError
from .._recovery import (
    RecoveryKey,
    WrappedMasterKey,
    decode_mnemonic,
    encode_mnemonic,
    generate_recovery_key,
    load_wrapped_master_key,
    save_wrapped_master_key,
    unwrap_master_key,
    wrap_master_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class TestMnemonicRoundTrip:
    """24-word BIP-39 mnemonic encoding round-trips losslessly."""

    def test_round_trip_random_entropy(self) -> None:
        entropy = secrets.token_bytes(32)
        mnemonic = encode_mnemonic(entropy)
        assert len(mnemonic.split()) == 24
        decoded = decode_mnemonic(mnemonic)
        assert decoded == entropy

    def test_known_test_vector_zeros(self) -> None:
        # The all-zero entropy is BIP-39's canonical "abandon abandon ..."
        # vector — the first word repeats 23 times and the 24th is the
        # word that satisfies the checksum.
        zeros = b"\x00" * 32
        mnemonic = encode_mnemonic(zeros)
        words = mnemonic.split()
        assert words[0] == "abandon"
        assert all(w == "abandon" for w in words[:23])
        # The 24th word is whatever the SHA-256 first byte resolves to;
        # for all-zero entropy that's the BIP-39 spec's "art" word.
        assert words[23] == "art"
        assert decode_mnemonic(mnemonic) == zeros

    def test_rejects_wrong_entropy_length(self) -> None:
        with pytest.raises(StorageValidationError, match="exactly 32 bytes") as excinfo:
            encode_mnemonic(b"\x00" * 16)
        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"

    def test_rejects_wrong_word_count(self) -> None:
        with pytest.raises(StorageValidationError, match="exactly 24 words") as excinfo:
            decode_mnemonic("abandon abandon abandon")
        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"

    def test_rejects_unknown_word(self) -> None:
        words = ["abandon"] * 23 + ["NOT_A_BIP39_WORD"]
        with pytest.raises(StorageValidationError, match="unknown BIP-39 word") as excinfo:
            decode_mnemonic(" ".join(words))
        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"
        message = str(excinfo.value)
        # the failing word must NOT be echoed in
        # the error message. The error reports the position only so
        # operator-visible logs / shell history / session captures
        # do not leak partial recovery-key contents.
        assert "NOT_A_BIP39_WORD" not in message
        assert "not_a_bip39_word" not in message
        assert "position 24" in message

    def test_rejects_unknown_word_does_not_echo_input(self) -> None:
        # Defensive: a typo with a real-looking BIP-39 word also
        # never lands in the error message. Position-only diagnostics.
        unique_typo = "absolutelynotabip39word"
        words = [unique_typo] + ["abandon"] * 23
        with pytest.raises(StorageValidationError) as excinfo:
            decode_mnemonic(" ".join(words))
        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"
        assert unique_typo not in str(excinfo.value)
        assert "position 1" in str(excinfo.value)

    def test_rejects_checksum_failure(self) -> None:
        # Take a valid mnemonic and replace the last word with a
        # different valid BIP-39 word — the checksum then fails.
        zeros = b"\x00" * 32
        mnemonic = encode_mnemonic(zeros)
        words = mnemonic.split()
        # Replace the last word with something else valid in the wordlist.
        words[-1] = "zoo"  # Not the correct checksum word for zero entropy.
        with pytest.raises(StorageValidationError, match="checksum mismatch") as excinfo:
            decode_mnemonic(" ".join(words))
        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"

    def test_case_insensitive_decode(self) -> None:
        zeros = b"\x00" * 32
        mnemonic = encode_mnemonic(zeros).upper()
        # Decoder lowercases before lookup.
        assert decode_mnemonic(mnemonic) == zeros


class TestGenerateRecoveryKey:
    """Recovery-key minting + record shape."""

    def test_returns_record_with_consistent_mnemonic(self) -> None:
        rk = generate_recovery_key()
        assert isinstance(rk, RecoveryKey)
        assert len(rk.raw) == 32
        # Verify the mnemonic decodes back to the raw bytes.
        assert decode_mnemonic(rk.mnemonic) == rk.raw

    def test_generates_unique_keys(self) -> None:
        a = generate_recovery_key()
        b = generate_recovery_key()
        assert a.raw != b.raw
        assert a.mnemonic != b.mnemonic


class TestMasterKeyWrapping:
    """Recovery-key-derived KEK wraps the master key."""

    def test_wrap_unwrap_round_trip(self) -> None:
        master_key = secrets.token_bytes(32)
        rk = generate_recovery_key()
        wrapped = wrap_master_key(master_key=master_key, recovery_key=rk)
        recovered = unwrap_master_key(wrapped=wrapped, recovery_key_bytes=rk.raw)
        assert recovered == master_key

    def test_unwrap_with_wrong_recovery_key_fails(self) -> None:
        master_key = secrets.token_bytes(32)
        wrapped = wrap_master_key(
            master_key=master_key,
            recovery_key=generate_recovery_key(),
        )
        wrong_recovery = secrets.token_bytes(32)
        with pytest.raises(DecryptionError):
            unwrap_master_key(wrapped=wrapped, recovery_key_bytes=wrong_recovery)

    def test_wrap_rejects_wrong_master_key_length(self) -> None:
        rk = generate_recovery_key()
        with pytest.raises(StorageValidationError, match="exactly 32 bytes") as excinfo:
            wrap_master_key(master_key=b"\x00" * 16, recovery_key=rk)
        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"

    def test_unwrap_rejects_wrong_recovery_key_length(self) -> None:
        master_key = secrets.token_bytes(32)
        wrapped = wrap_master_key(
            master_key=master_key,
            recovery_key=generate_recovery_key(),
        )
        with pytest.raises(StorageValidationError, match="exactly 32 bytes") as excinfo:
            unwrap_master_key(wrapped=wrapped, recovery_key_bytes=b"\x00" * 16)
        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"


class TestWrappedMasterKeyPersistence:
    """`master.recovery.key` round-trips through atomic writer + loader."""

    def test_save_then_load(self, tmp_path: Path) -> None:
        master_key = secrets.token_bytes(32)
        rk = generate_recovery_key()
        wrapped = wrap_master_key(master_key=master_key, recovery_key=rk)
        target = tmp_path / "secrets" / "master.recovery.key"
        save_wrapped_master_key(wrapped, target)
        assert target.exists()
        loaded = load_wrapped_master_key(target)
        assert loaded == wrapped
        # Round-trip via the recovery key.
        assert unwrap_master_key(wrapped=loaded, recovery_key_bytes=rk.raw) == master_key

    def test_saved_file_is_strict_json(self, tmp_path: Path) -> None:
        master_key = secrets.token_bytes(32)
        wrapped = wrap_master_key(
            master_key=master_key,
            recovery_key=generate_recovery_key(),
        )
        target = tmp_path / "secrets" / "master.recovery.key"
        save_wrapped_master_key(wrapped, target)
        text = target.read_text(encoding=UTF_8_ENCODING)
        # The persisted file is a single-line JSON object with the
        # expected fields (base64-encoded nonce + ciphertext).
        assert text.startswith("{")
        assert "schema_version" in text
        assert "nonce_b64" in text
        assert "ciphertext_b64" in text

    def test_load_rejects_malformed_json_as_localized_storage_validation(self, tmp_path: Path) -> None:
        target = tmp_path / "secrets" / "master.recovery.key"
        target.parent.mkdir(parents=True)
        target.write_text("not-json", encoding=UTF_8_ENCODING)

        with pytest.raises(StorageValidationError, match="wrapped recovery master key file") as excinfo:
            load_wrapped_master_key(target)

        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"
        assert str(tmp_path) not in str(excinfo.value)

    def test_unwrap_rejects_malformed_base64_as_localized_storage_validation(self) -> None:
        wrapped = WrappedMasterKey(nonce_b64="not-base64", ciphertext_b64="also-not-base64")

        with pytest.raises(StorageValidationError, match="wrapped recovery master key is malformed") as excinfo:
            unwrap_master_key(wrapped=wrapped, recovery_key_bytes=secrets.token_bytes(32))

        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"
