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

from datetime import UTC, datetime

import pytest

from aeat.adapters.persistence.storage.bucket._errors import RecoveryVerificationError
from aeat.adapters.persistence.storage.master_key._recovery import (
    decode_mnemonic,
    encode_mnemonic,
)
from aeat.adapters.persistence.storage.master_key._recovery_facade import (
    MintedRecovery,
    mint_recovery_envelope,
    open_session_from_recovery,
    unwrap_recovery_envelope,
    verify_recovery_mnemonic,
)
from aeat.adapters.persistence.storage.master_key._recovery_record import RecoveryRecord

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]

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
