"""Recovery key material is held in buffers the zeroise primitive can reach.

The substrate's wipe primitive only operates on a mutable ``bytearray``; it
refuses anything else by design. Key material held as immutable ``bytes`` or
``str`` is therefore permanently unreachable by any wipe, and survives in
memory entirely at the garbage collector's discretion.

That gap is structurally wider on the recovery surface than on the
steady-state session path, because it opens on every recovery mint, unwrap,
and passphrase change — and an enrollment holds a live plaintext DEK across
the operator's *interactive* confirmation, which lasts as long as it takes a
human to copy down 24 words.

These tests pin the contract that closes it: every secret the recovery
surface mints or recovers comes back in a buffer ``zeroise`` accepts, and the
containers that hold key material across an operation wipe on demand. The
refusal test below is what gives the rest their teeth — it proves ``zeroise``
genuinely rejects the immutable shapes, so a regression back to ``bytes`` or
``str`` fails these tests rather than passing them vacuously.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from .._errors import MasterKeyTypeError
from .._recovery import (
    RecoveryKey,
    decode_mnemonic,
    encode_mnemonic,
    generate_recovery_key,
    unwrap_master_key,
    wrap_master_key,
)
from .._recovery_facade import mint_recovery_envelope, unwrap_recovery_envelope
from .._zeroise import zeroise

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_DEK = bytes(range(32))


def test_zeroise_refuses_immutable_bytes_and_str() -> None:
    """The wipe primitive cannot reach immutable material.

    This is the anti-tautology proof for every other test in this module: it
    establishes that "``zeroise`` accepted this buffer" is a real claim about
    the value's type, not a vacuous one. If the recovery surface regressed to
    handing back ``bytes``, the assertions below would raise rather than pass.
    """
    with pytest.raises(MasterKeyTypeError):
        zeroise(bytes(32))
    with pytest.raises(MasterKeyTypeError):
        zeroise("abandon abandon abandon")


def test_generated_recovery_key_entropy_is_reachable_by_zeroise() -> None:
    """A freshly minted recovery key exposes wipeable entropy."""
    recovery_key = generate_recovery_key()

    assert isinstance(recovery_key.raw, bytearray)
    zeroise(recovery_key.raw)
    assert recovery_key.raw == bytearray(32)


def test_recovery_key_wipe_zeroes_both_entropy_and_mnemonic() -> None:
    """Wiping clears the entropy and the words that encode it.

    The mnemonic is not merely a label for the entropy — it *is* the entropy,
    re-encoded. Zeroing one while leaving the other intact would wipe nothing
    in substance, so both buffers must go.
    """
    recovery_key = generate_recovery_key()
    original_words = recovery_key.mnemonic
    assert len(original_words.split()) == 24

    recovery_key.wipe()

    assert recovery_key.raw == bytearray(32)
    assert recovery_key.mnemonic != original_words
    assert original_words.split()[0] not in recovery_key.mnemonic.split()


def test_recovery_key_wipe_is_idempotent() -> None:
    """Wiping an already-wiped key is a no-op, not an error."""
    recovery_key = generate_recovery_key()

    recovery_key.wipe()
    recovery_key.wipe()

    assert recovery_key.raw == bytearray(32)


def test_recovery_key_context_manager_wipes_on_exit() -> None:
    """The context-manager form wipes even when the body raises."""
    recovery_key = generate_recovery_key()

    with pytest.raises(RuntimeError), recovery_key:
        raise RuntimeError("enrollment cancelled")

    assert recovery_key.raw == bytearray(32)


def test_decode_mnemonic_returns_a_buffer_zeroise_accepts() -> None:
    """The decoded entropy — the recovery key itself — is wipeable."""
    mnemonic = encode_mnemonic(bytes([0x11] * 32))

    entropy = decode_mnemonic(mnemonic)

    assert isinstance(entropy, bytearray)
    assert entropy == bytearray([0x11] * 32)
    zeroise(entropy)
    assert entropy == bytearray(32)


def test_unwrap_master_key_returns_a_buffer_zeroise_accepts() -> None:
    """The unwrapped master key comes back wipeable."""
    recovery_key = generate_recovery_key()
    wrapped = wrap_master_key(master_key=_DEK, recovery_key=recovery_key)

    recovered = unwrap_master_key(wrapped=wrapped, recovery_key_bytes=recovery_key.raw)

    assert isinstance(recovered, bytearray)
    assert recovered == _DEK
    zeroise(recovered)
    assert recovered == bytearray(32)


def test_unwrap_recovery_envelope_returns_a_buffer_zeroise_accepts() -> None:
    """The DEK recovered from a real envelope comes back wipeable."""
    minted = mint_recovery_envelope(dek=_DEK, created_at=_NOW)

    recovered = unwrap_recovery_envelope(envelope=minted.envelope, mnemonic=minted.mnemonic)

    assert isinstance(recovered, bytearray)
    assert recovered == _DEK
    zeroise(recovered)
    assert recovered == bytearray(32)


def test_minted_recovery_wipe_clears_the_mnemonic() -> None:
    """The minted record's mnemonic is wipeable once the operator has copied it."""
    minted = mint_recovery_envelope(dek=_DEK, created_at=_NOW)
    original_words = minted.mnemonic
    assert len(original_words.split()) == 24

    minted.wipe()

    assert minted.mnemonic != original_words


def test_minted_recovery_wipe_leaves_the_public_envelope_intact() -> None:
    """Wiping the secret must not disturb the ciphertext envelope.

    The envelope is public wrap material and the only part meant to reach
    disk; a wipe that damaged it would destroy the enrollment it just
    created.
    """
    minted = mint_recovery_envelope(dek=_DEK, created_at=_NOW)
    fingerprint = minted.envelope.recovery_fingerprint
    wrapped_dek = minted.envelope.wrapped_dek_b64
    mnemonic = minted.mnemonic

    minted.wipe()

    assert minted.envelope.recovery_fingerprint == fingerprint
    assert minted.envelope.wrapped_dek_b64 == wrapped_dek
    # The envelope still unwraps under the words the operator wrote down.
    assert unwrap_recovery_envelope(envelope=minted.envelope, mnemonic=mnemonic) == _DEK


def test_minted_recovery_cannot_serialise_its_mnemonic() -> None:
    """The minted record carries no pydantic serialisation path for the secret.

    ``MintedRecovery`` is deliberately a slotted plain class rather than a
    pydantic model, so there is no ``model_dump_json`` that could write the
    recovery code to the very disk the envelope exists to keep it off.
    """
    minted = mint_recovery_envelope(dek=_DEK, created_at=_NOW)

    assert not hasattr(minted, "model_dump_json")
    assert not hasattr(minted, "model_dump")


def test_recovery_key_cannot_serialise_its_material() -> None:
    """``RecoveryKey`` likewise exposes no serialisation path."""
    recovery_key = generate_recovery_key()

    assert not hasattr(recovery_key, "model_dump_json")
    assert not hasattr(recovery_key, "model_dump")


def test_recovery_key_refuses_wrong_sized_entropy() -> None:
    """Length validation survives the move off pydantic."""
    from ...errors import StorageValidationError

    with pytest.raises(StorageValidationError):
        RecoveryKey(raw=bytes(16), mnemonic="abandon")


def test_recovery_key_refuses_empty_mnemonic() -> None:
    """Non-empty mnemonic validation survives the move off pydantic."""
    from ...errors import StorageValidationError

    with pytest.raises(StorageValidationError):
        RecoveryKey(raw=bytes(32), mnemonic="")
