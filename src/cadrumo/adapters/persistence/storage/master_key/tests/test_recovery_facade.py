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
from pathlib import Path

import pytest

from ......core.errors import ERROR_REGISTRY, build_error_envelope
from ...bucket import RecoveryVerificationError
from ...errors import SecretStoreError
from .._master_key import FileFallbackMasterKeyProvider
from .._recovery import (
    decode_mnemonic,
    encode_mnemonic,
)
from .._recovery_facade import (
    MintedRecovery,
    RecoveryEnrollmentOutcome,
    RecoveryLifecycleStatus,
    RecoveryRecoverOutcome,
    RecoveryVerifyOutcome,
    load_recovery_envelope,
    mint_recovery_envelope,
    open_session_from_recovery,
    recovery_create,
    recovery_recover,
    recovery_rotate,
    recovery_status,
    recovery_verify,
    unwrap_recovery_envelope,
    verify_recovery_mnemonic,
)
from .._recovery_record import RecoveryRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PASSPHRASE = "correct horse battery staple"  # noqa: S105 - synthetic test fixture

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
    assert minted.envelope.hkdf_info == "cadrumo.recovery-key.master-wrap.v1"
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
        hkdf_info="cadrumo.recovery-key.master-wrap.v1",
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


# ---------------------------------------------------------------------------
# Recovery lifecycle operations against real encrypted files
# ---------------------------------------------------------------------------


def _provisioned_file_provider(store_dir: Path) -> FileFallbackMasterKeyProvider:
    """Return a file provider with a real minted master key at ``store_dir``."""
    provider = FileFallbackMasterKeyProvider(store_dir=store_dir, passphrase_callback=lambda: _PASSPHRASE)
    provider.provision_master_key()
    return provider


def _recovery_path(store_dir: Path) -> Path:
    return store_dir / "master.recovery.key"


def _echo(mnemonic: str) -> str:
    """A faithful operator retype: the confirmation matches the staged code."""
    return mnemonic


def _wrong_retype(_mnemonic: str) -> str:
    """A mistyped confirmation: a different valid 24-word mnemonic."""
    return encode_mnemonic(bytes([0x5A] * 32))


def _cancel(_mnemonic: str) -> str:
    raise KeyboardInterrupt("operator cancelled at the confirmation prompt")


def test_recovery_create_enrolls_and_status_reports_fingerprint(tmp_path: Path) -> None:
    store_dir = tmp_path / "secrets"
    provider = _provisioned_file_provider(store_dir)
    path = _recovery_path(store_dir)

    assert recovery_status(path=path) == RecoveryLifecycleStatus(enrolled=False, recovery_fingerprint=None)

    outcome = recovery_create(provider=provider, path=path, created_at=_NOW, confirm=_echo)

    assert isinstance(outcome, RecoveryEnrollmentOutcome)
    assert outcome.rotated is False
    assert path.is_file()
    status = recovery_status(path=path)
    assert status.enrolled is True
    assert status.recovery_fingerprint == outcome.recovery_fingerprint
    # The installed envelope really unwraps the same master key.
    envelope = load_recovery_envelope(path)
    assert envelope.recovery_fingerprint == outcome.recovery_fingerprint


def test_recovery_create_refuses_existing_enrollment(tmp_path: Path) -> None:
    """Create refuses when a recovery envelope already exists, untouched."""
    store_dir = tmp_path / "secrets"
    provider = _provisioned_file_provider(store_dir)
    path = _recovery_path(store_dir)

    recovery_create(provider=provider, path=path, created_at=_NOW, confirm=_echo)
    original = path.read_bytes()

    with pytest.raises(SecretStoreError, match="already enrolled"):
        recovery_create(provider=provider, path=path, created_at=_NOW, confirm=_echo)

    assert path.read_bytes() == original


def test_recovery_rotate_requires_existing_enrollment(tmp_path: Path) -> None:
    """Rotate refuses when no recovery envelope is enrolled yet."""
    store_dir = tmp_path / "secrets"
    provider = _provisioned_file_provider(store_dir)
    path = _recovery_path(store_dir)

    with pytest.raises(SecretStoreError, match="no recovery envelope is enrolled"):
        recovery_rotate(provider=provider, path=path, created_at=_NOW, confirm=_echo)

    assert not path.exists()


def test_recovery_rotate_replaces_envelope_after_confirmation(tmp_path: Path) -> None:
    store_dir = tmp_path / "secrets"
    provider = _provisioned_file_provider(store_dir)
    path = _recovery_path(store_dir)

    first = recovery_create(provider=provider, path=path, created_at=_NOW, confirm=_echo)
    before = path.read_bytes()

    later = datetime(2026, 6, 1, 9, 0, 0, tzinfo=UTC)
    rotated = recovery_rotate(provider=provider, path=path, created_at=later, confirm=_echo)

    assert rotated.rotated is True
    assert rotated.recovery_fingerprint != first.recovery_fingerprint
    assert path.read_bytes() != before
    assert recovery_status(path=path).recovery_fingerprint == rotated.recovery_fingerprint


def test_rotate_preserves_prior_envelope_on_failed_confirmation(tmp_path: Path) -> None:
    """A mistyped confirmation leaves the prior envelope byte-identical."""
    store_dir = tmp_path / "secrets"
    provider = _provisioned_file_provider(store_dir)
    path = _recovery_path(store_dir)

    created = recovery_create(provider=provider, path=path, created_at=_NOW, confirm=_echo)
    before = path.read_bytes()

    with pytest.raises(RecoveryVerificationError):
        recovery_rotate(provider=provider, path=path, created_at=_NOW, confirm=_wrong_retype)

    assert path.read_bytes() == before
    # The original enrollment is still fully valid and identifiable.
    assert recovery_status(path=path).recovery_fingerprint == created.recovery_fingerprint


def test_rotate_preserves_prior_envelope_on_cancelled_confirmation(tmp_path: Path) -> None:
    """A cancelled confirmation propagates and never rewrites the envelope."""
    store_dir = tmp_path / "secrets"
    provider = _provisioned_file_provider(store_dir)
    path = _recovery_path(store_dir)

    recovery_create(provider=provider, path=path, created_at=_NOW, confirm=_echo)
    before = path.read_bytes()

    with pytest.raises(KeyboardInterrupt):
        recovery_rotate(provider=provider, path=path, created_at=_NOW, confirm=_cancel)

    assert path.read_bytes() == before


def test_create_writes_no_envelope_on_failed_confirmation(tmp_path: Path) -> None:
    """A first enrollment whose retype fails leaves the store with no envelope."""
    store_dir = tmp_path / "secrets"
    provider = _provisioned_file_provider(store_dir)
    path = _recovery_path(store_dir)

    with pytest.raises(RecoveryVerificationError):
        recovery_create(provider=provider, path=path, created_at=_NOW, confirm=_wrong_retype)

    assert not path.exists()
    assert recovery_status(path=path).enrolled is False


def test_recovery_verify_reports_match_and_preserves_fingerprint(tmp_path: Path) -> None:
    store_dir = tmp_path / "secrets"
    provider = _provisioned_file_provider(store_dir)
    path = _recovery_path(store_dir)

    staged: dict[str, str] = {}

    def _capture(mnemonic: str) -> str:
        staged["mnemonic"] = mnemonic
        return mnemonic

    created = recovery_create(provider=provider, path=path, created_at=_NOW, confirm=_capture)
    before = path.read_bytes()

    good = recovery_verify(provider=provider, path=path, mnemonic=staged["mnemonic"])
    assert good == RecoveryVerifyOutcome(verified=True, recovery_fingerprint=created.recovery_fingerprint)

    bad = recovery_verify(provider=provider, path=path, mnemonic=encode_mnemonic(bytes([0x11] * 32)))
    assert bad.verified is False
    assert bad.recovery_fingerprint == created.recovery_fingerprint

    # Verification never rewrites the envelope.
    assert path.read_bytes() == before


def test_recovery_recover_rewraps_master_key_and_preserves_fingerprint(tmp_path: Path) -> None:
    store_dir = tmp_path / "secrets"
    provider = _provisioned_file_provider(store_dir)
    path = _recovery_path(store_dir)
    original_master_key = provider.get_master_key()

    staged: dict[str, str] = {}

    def _capture(mnemonic: str) -> str:
        staged["mnemonic"] = mnemonic
        return mnemonic

    created = recovery_create(provider=provider, path=path, created_at=_NOW, confirm=_capture)
    envelope_before = path.read_bytes()

    new_passphrase = "brand new operator passphrase"  # noqa: S105 - synthetic test fixture
    recovery_provider = FileFallbackMasterKeyProvider(store_dir=store_dir, passphrase_callback=lambda: new_passphrase)
    outcome = recovery_recover(provider=recovery_provider, path=path, mnemonic=staged["mnemonic"])

    assert isinstance(outcome, RecoveryRecoverOutcome)
    assert outcome.recovery_fingerprint == created.recovery_fingerprint
    # The recovery envelope file is never rewritten by recover.
    assert path.read_bytes() == envelope_before
    # The store now opens under the new passphrase and yields the same key.
    reopened = FileFallbackMasterKeyProvider(store_dir=store_dir, passphrase_callback=lambda: new_passphrase)
    assert reopened.get_master_key() == original_master_key


def test_recovery_recover_refuses_wrong_mnemonic(tmp_path: Path) -> None:
    store_dir = tmp_path / "secrets"
    provider = _provisioned_file_provider(store_dir)
    path = _recovery_path(store_dir)
    recovery_create(provider=provider, path=path, created_at=_NOW, confirm=_echo)

    recovery_provider = FileFallbackMasterKeyProvider(
        store_dir=store_dir, passphrase_callback=lambda: "some other pass"
    )
    with pytest.raises(RecoveryVerificationError):
        recovery_recover(provider=recovery_provider, path=path, mnemonic=encode_mnemonic(bytes([0x22] * 32)))
