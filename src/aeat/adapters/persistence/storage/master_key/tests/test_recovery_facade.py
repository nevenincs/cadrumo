"""Tests for the typed BIP-39 recovery facade.

The known-answer vectors are the BIP-39 specification's own 256-bit
reference vectors (Trezor's `english.json` test set):

- Entropy `0x00..00` (32 bytes) → 24-word mnemonic starting `abandon`
  and ending with the checksum word `art`.
- Entropy `0xff..ff` (32 bytes) → 24-word mnemonic starting `zoo` and
  ending with the checksum word `vote`.

These vectors come from the BIP-39 specification itself, not from
re-running the substrate's encoder against itself.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import pytest

from ......core.errors import ERROR_REGISTRY, build_error_envelope
from ...bucket._errors import RecoveryVerificationError
from .._recovery import (
    decode_mnemonic,
    encode_mnemonic,
)
from .._recovery_facade import (
    MintedRecovery,
    mint_recovery_envelope,
    open_session_from_recovery,
    unwrap_recovery_envelope,
    verify_recovery_mnemonic,
)
from .._recovery_record import RecoveryRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)

_BIP39_ALL_ZERO_ENTROPY = bytes(32)
_BIP39_ALL_ZERO_MNEMONIC = (
    "abandon abandon abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon abandon abandon art"
)

_BIP39_ALL_ONES_ENTROPY = bytes([0xFF] * 32)
_BIP39_ALL_ONES_MNEMONIC = (
    "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo vote"
)


def test_bip39_spec_vector_all_zero_entropy_encodes_to_canonical_mnemonic() -> None:
    """BIP-39 specification reference vector for 256-bit all-zero entropy."""

    assert encode_mnemonic(_BIP39_ALL_ZERO_ENTROPY) == _BIP39_ALL_ZERO_MNEMONIC


def test_bip39_spec_vector_all_zero_mnemonic_decodes_to_canonical_entropy() -> None:
    """BIP-39 specification reference vector decode-path."""

    assert decode_mnemonic(_BIP39_ALL_ZERO_MNEMONIC) == _BIP39_ALL_ZERO_ENTROPY


def test_bip39_spec_vector_all_ones_entropy_encodes_to_canonical_mnemonic() -> None:
    """BIP-39 specification reference vector for 256-bit all-ones entropy."""

    assert encode_mnemonic(_BIP39_ALL_ONES_ENTROPY) == _BIP39_ALL_ONES_MNEMONIC


def test_bip39_spec_vector_all_ones_mnemonic_decodes_to_canonical_entropy() -> None:
    assert decode_mnemonic(_BIP39_ALL_ONES_MNEMONIC) == _BIP39_ALL_ONES_ENTROPY


def test_mint_recovery_envelope_round_trips_dek() -> None:
    """The minted envelope plus the minted mnemonic recover the DEK."""

    dek = bytes(range(32))
    minted: MintedRecovery = mint_recovery_envelope(dek=dek, created_at=_NOW)

    recovered = unwrap_recovery_envelope(envelope=minted.envelope, mnemonic=minted.mnemonic)
    assert recovered == dek


def test_minted_envelope_is_strict_recovery_record() -> None:
    """The facade emits the canonical strict pydantic record."""

    minted = mint_recovery_envelope(dek=bytes(range(32)), created_at=_NOW)

    assert isinstance(minted.envelope, RecoveryRecord)
    assert minted.envelope.mnemonic_word_count == 24
    assert minted.envelope.hkdf_info == "aeat.recovery-key.master-wrap.v1"
    assert minted.envelope.created_at == _NOW
    # 24-word BIP-39 English mnemonic
    assert len(minted.mnemonic.split()) == 24


def test_unwrap_with_wrong_mnemonic_raises_recovery_verification_error() -> None:
    minted = mint_recovery_envelope(dek=bytes(range(32)), created_at=_NOW)

    # Use a different valid 24-word mnemonic; AEAD tag check fails.
    other = encode_mnemonic(bytes([0x01] * 32))
    with pytest.raises(RecoveryVerificationError):
        unwrap_recovery_envelope(envelope=minted.envelope, mnemonic=other)


def test_unwrap_with_malformed_mnemonic_raises_recovery_verification_error() -> None:
    minted = mint_recovery_envelope(dek=bytes(range(32)), created_at=_NOW)

    with pytest.raises(RecoveryVerificationError):
        unwrap_recovery_envelope(envelope=minted.envelope, mnemonic="not-a-mnemonic")


def test_unwrap_with_malformed_envelope_raises_recovery_verification_error() -> None:
    minted = mint_recovery_envelope(dek=bytes(range(32)), created_at=_NOW)
    malformed = RecoveryRecord(
        wrapped_dek_b64=minted.envelope.wrapped_dek_b64,
        nonce_b64=base64.b64encode(b"short").decode("ascii"),
        tag_b64=minted.envelope.tag_b64,
        mnemonic_word_count=24,
        hkdf_info="aeat.recovery-key.master-wrap.v1",
        created_at=_NOW,
    )

    with pytest.raises(RecoveryVerificationError) as excinfo:
        unwrap_recovery_envelope(envelope=malformed, mnemonic=minted.mnemonic)

    assert excinfo.value.translated_message == "errors.auth.auth_storage_bucket_recovery_verification"
    envelope = build_error_envelope(excinfo.value)
    assert envelope.code == "AUTH_STORAGE_BUCKET_RECOVERY_VERIFICATION"
    assert "short" not in envelope.model_dump_json()


def test_verify_recovery_mnemonic_returns_true_on_match_false_on_mismatch() -> None:
    minted = mint_recovery_envelope(dek=bytes(range(32)), created_at=_NOW)

    assert verify_recovery_mnemonic(envelope=minted.envelope, mnemonic=minted.mnemonic) is True
    other = encode_mnemonic(bytes([0x02] * 32))
    assert verify_recovery_mnemonic(envelope=minted.envelope, mnemonic=other) is False


def test_open_session_from_recovery_returns_unlocked_session_bound_to_bucket() -> None:
    dek = bytes(range(32))
    minted = mint_recovery_envelope(dek=dek, created_at=_NOW)
    new_kek = bytes([0xAA] * 32)

    session = open_session_from_recovery(
        bucket_id="bucket-recovered",
        envelope=minted.envelope,
        mnemonic=minted.mnemonic,
        kek=new_kek,
        idle_minutes=15,
        opened_at=_NOW,
    )

    assert session.bucket_id == "bucket-recovered"
    assert session.kek == new_kek
    assert session.dek == dek
    session.close()


# ---------------------------------------------------------------------------
# contract: ErrorCode registry binding + narrowed-except contract tests
# ---------------------------------------------------------------------------


def test_recovery_verification_error_is_in_error_registry() -> None:
    """RecoveryVerificationError is bound to AUTH_STORAGE_BUCKET_RECOVERY_VERIFICATION."""

    assert "AUTH_STORAGE_BUCKET_RECOVERY_VERIFICATION" in ERROR_REGISTRY
    code = ERROR_REGISTRY["AUTH_STORAGE_BUCKET_RECOVERY_VERIFICATION"]
    assert code.category.value == "AUTH"
    assert code.message_key == "errors.auth.auth_storage_bucket_recovery_verification"


def test_recovery_verification_error_round_trips_through_build_error_envelope() -> None:
    """build_error_envelope produces a typed envelope for RecoveryVerificationError."""

    exc = RecoveryVerificationError("mnemonic decode failed")
    envelope = build_error_envelope(exc)

    assert envelope.code == "AUTH_STORAGE_BUCKET_RECOVERY_VERIFICATION"
    assert envelope.category == "AUTH"
    assert envelope.suggestion == "aeat config recover --recovery-key <WORDS>"
    assert not envelope.retryable


def test_storage_validation_error_from_decode_mnemonic_is_reclassified() -> None:
    """StorageValidationError raised by decode_mnemonic re-raises as RecoveryVerificationError."""

    minted = mint_recovery_envelope(dek=bytes(range(32)), created_at=_NOW)

    # Wrong-word-count path (triggers StorageValidationError inside decode_mnemonic).
    with pytest.raises(RecoveryVerificationError):
        unwrap_recovery_envelope(envelope=minted.envelope, mnemonic="abandon")

    # Unknown-word path.
    bad_word_mnemonic = "notaword " + " ".join(["abandon"] * 23)
    with pytest.raises(RecoveryVerificationError):
        unwrap_recovery_envelope(envelope=minted.envelope, mnemonic=bad_word_mnemonic)

    # Checksum-failure path: tamper one word in a valid 24-word mnemonic.
    # "zoo zoo ... zoo vote" → replace the last word with a different valid word
    # that produces a checksum mismatch.
    tampered = _BIP39_ALL_ONES_MNEMONIC.rsplit(" ", 1)[0] + " abandon"
    with pytest.raises(RecoveryVerificationError):
        unwrap_recovery_envelope(envelope=minted.envelope, mnemonic=tampered)


def test_unexpected_exception_from_decode_mnemonic_propagates_unchanged() -> None:
    """An exception NOT in the documented set propagates as-is, not as RecoveryVerificationError.

    This guards the narrowed ``except StorageValidationError`` clause: a
    ``KeyError`` raised by a decoder passed via the production ``decoder``
    DI parameter must surface unchanged so the top-level CLI error
    handler sees a real unexpected exception rather than a silently
    reclassified recovery-verification failure.
    """

    minted = mint_recovery_envelope(dek=bytes(range(32)), created_at=_NOW)

    def _raise_key_error(_mnemonic: str) -> bytes:
        raise KeyError("unexpected internal error")

    with pytest.raises(KeyError):
        unwrap_recovery_envelope(
            envelope=minted.envelope,
            mnemonic=minted.mnemonic,
            decoder=_raise_key_error,
        )
