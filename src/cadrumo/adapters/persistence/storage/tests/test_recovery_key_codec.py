"""Recovery-key material is held in buffers the zeroise primitive can reach.

The substrate's wipe primitive only operates on a mutable ``bytearray``; it
refuses anything else by design. Key material held as immutable ``bytes`` or
``str`` is therefore permanently unreachable by any wipe, and survives in
memory entirely at the garbage collector's discretion.

That gap is structurally wider on the recovery surface than on the
steady-state session path, because it opens on every mint and every decode --
and an enrollment holds a live plaintext key across the operator's
*interactive* confirmation, which lasts as long as it takes a human to copy
down 24 words.

These tests pin the contract that closes it for the BIP-39 primitives: every
secret they mint or recover comes back in a buffer ``zeroise`` accepts, and
the container that holds key material across an operation wipes on demand.
The refusal test below is what gives the rest their teeth -- it proves
``zeroise`` genuinely rejects the immutable shapes, so a regression back to
``bytes`` or ``str`` fails these tests rather than passing them vacuously.
"""

from __future__ import annotations

import pytest

from ..custody.errors import WipeTypeError
from ..custody.zeroise import zeroise
from ..errors import StorageValidationError
from ..recovery_key import (
    RecoveryKey,
    decode_mnemonic,
    encode_mnemonic,
    generate_recovery_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_zeroise_refuses_immutable_bytes_and_str() -> None:
    """The wipe primitive cannot reach immutable material.

    This is the anti-tautology proof for every other test in this module: it
    establishes that "``zeroise`` accepted this buffer" is a real claim about
    the value's type, not a vacuous one. If the recovery surface regressed to
    handing back ``bytes``, the assertions below would raise rather than pass.
    """
    with pytest.raises(WipeTypeError):
        zeroise(bytes(32))
    with pytest.raises(WipeTypeError):
        zeroise("abandon abandon abandon")


def test_generated_recovery_key_entropy_is_reachable_by_zeroise() -> None:
    """A freshly minted recovery key exposes wipeable entropy."""
    recovery_key = generate_recovery_key()

    assert isinstance(recovery_key.raw, bytearray)
    zeroise(recovery_key.raw)
    assert recovery_key.raw == bytearray(32)


def test_recovery_key_wipe_zeroes_both_entropy_and_mnemonic() -> None:
    """Wiping clears the entropy and the words that encode it.

    The mnemonic is not merely a label for the entropy -- it *is* the entropy,
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
    """The decoded entropy -- the recovery key itself -- is wipeable."""
    mnemonic = encode_mnemonic(bytes([0x11] * 32))

    entropy = decode_mnemonic(mnemonic)

    assert isinstance(entropy, bytearray)
    assert entropy == bytearray([0x11] * 32)
    zeroise(entropy)
    assert entropy == bytearray(32)


def test_recovery_key_cannot_serialise_its_material() -> None:
    """``RecoveryKey`` exposes no serialisation path."""
    recovery_key = generate_recovery_key()

    assert not hasattr(recovery_key, "model_dump_json")
    assert not hasattr(recovery_key, "model_dump")


def test_recovery_key_refuses_wrong_sized_entropy() -> None:
    """Length validation survives the move off pydantic."""
    with pytest.raises(StorageValidationError):
        RecoveryKey(raw=bytes(16), mnemonic="abandon")


def test_recovery_key_refuses_empty_mnemonic() -> None:
    """Non-empty mnemonic validation survives the move off pydantic."""
    with pytest.raises(StorageValidationError):
        RecoveryKey(raw=bytes(32), mnemonic="")


def test_mnemonic_roundtrips_every_minted_key() -> None:
    """A minted key's words decode back to exactly its own entropy.

    The codec is the generator behind a per-profile recovery secret, so a
    round-trip that lost or reordered a single bit would hand the operator
    24 words that unwrap nothing -- discovered only on the day recovery is
    the last route left.
    """
    for _ in range(8):
        with generate_recovery_key() as recovery_key:
            entropy = decode_mnemonic(recovery_key.mnemonic)
            try:
                assert bytes(entropy) == bytes(recovery_key.raw)
            finally:
                zeroise(entropy)


def test_decode_refuses_a_single_substituted_word() -> None:
    """A transcription error fails the checksum instead of yielding key bytes.

    This is the codec's own anti-tautology arm: it proves the decode is
    verifying rather than merely reassembling, so the round-trip above
    cannot be passing on a decoder that accepts anything.
    """
    mnemonic = encode_mnemonic(bytes([0x22] * 32)).split()
    substitute = "zoo" if mnemonic[0] != "zoo" else "abandon"
    corrupted = " ".join([substitute, *mnemonic[1:]])

    with pytest.raises(StorageValidationError):
        decode_mnemonic(corrupted)


def test_decode_refuses_a_word_outside_the_canonical_list() -> None:
    """An unknown word names its position rather than failing opaquely."""
    mnemonic = encode_mnemonic(bytes([0x33] * 32)).split()
    corrupted = " ".join([*mnemonic[:5], "cadrumo", *mnemonic[6:]])

    with pytest.raises(StorageValidationError, match="position 6"):
        decode_mnemonic(corrupted)
