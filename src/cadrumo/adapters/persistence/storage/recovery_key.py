"""Recovery-key minting and its BIP-39 mnemonic codec.

A recovery secret is an opaque high-entropy string as far as every
consumer is concerned; this module is the only thing in the substrate
that can mint one strong enough to resist offline guessing once material
derived from it has left the machine. A profile's recovery envelope wraps
that profile's DEK under its own supervised Argon2id parameters against a
generation-bound associated-data domain, and takes the minted mnemonic as
its secret. The codec itself is bound to no custody architecture, no file
layout and no key schedule.

It sits directly beneath the storage package, sibling to both the custody
package that consumes it and the shared-master ``master_key`` package it
used to live in, so it survives that package's retirement rather than
being swept away with the master-key wrapping half it happened to share a
file with. The substrate never persists the mnemonic.

**Wipeable key material.** The recovery entropy and the mnemonic are held
in ``bytearray`` buffers rather than immutable ``bytes`` / ``str``, so the
substrate's :func:`zeroise` primitive can overwrite them in place. The
recovery surface needs this more than the steady-state session path does:
an enrollment holds live key material across the operator's interactive
confirmation. The honest limit is unchanged from the one the session path
already discloses -- passing a buffer to a ``bytes``-typed cryptographic
primitive, or reading the mnemonic as a ``str``, materialises a transient
immutable copy whose lifetime the garbage collector owns. Those copies are
bounded by a single call; what this module does not do is hold the *only*
copy of a secret in a form no wipe primitive can reach.

The encoding follows BIP-39 (Bitcoin Improvement Proposal 0039) exactly --
256-bit entropy, an 8-bit checksum, and 24 11-bit words drawn from the
canonical English wordlist. The wordlist is bundled at
:file:`_bip39_wordlist.txt` (2048 lines, public domain, identical to the
Bitcoin Core source).
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Buffer
from pathlib import Path
from typing import Final, Self

from ....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .custody.zeroise import zeroise as _zeroise
from .errors import storage_validation_error as _storage_validation_error

_RECOVERY_KEY_SIZE: Final[int] = 32
_MNEMONIC_WORD_COUNT: Final[int] = 24


class RecoveryKey:
    """Wipeable container for a 32-byte recovery key + its 24-word mnemonic.

    The substrate never persists the raw entropy or the mnemonic. Both are
    held in ``bytearray`` buffers rather than immutable ``bytes`` / ``str``
    so :func:`zeroise` can overwrite them in place once the enrollment has
    committed, instead of leaving them to the garbage collector.

    This matters more here than on the steady-state session path: an
    enrollment holds live key material across the operator's *interactive*
    confirmation, which can last as long as it takes a human to copy down
    24 words. Immutable material held across that window is unreachable by
    any wipe primitive for its whole lifetime.

    Deliberately not a pydantic model. The sibling ``BucketSession`` sets
    the precedent for live key material: a slotted plain class keeps the
    buffers mutable, and -- because there is no ``model_dump_json`` --
    makes it structurally impossible to serialise the secret by accident.

    Honest contract, identical in kind to the one ``BucketSession``
    discloses: reading :attr:`mnemonic` materialises a transient ``str``
    copy whose lifetime the garbage collector owns, and passing :attr:`raw`
    to a ``bytes``-typed cryptographic primitive materialises a transient
    ``bytes`` copy for the duration of that call. The buffers this object
    *holds* are wipeable; those short-lived boundary copies are not.
    """

    __slots__ = ("_mnemonic_buffer", "_raw_buffer")

    def __init__(self, *, raw: Buffer, mnemonic: str) -> None:
        """Copy ``raw`` and ``mnemonic`` into the wipeable buffers this key owns.

        Args:
            raw: The entropy, which must be exactly the recovery-key size.
            mnemonic: The non-empty mnemonic encoding that entropy.

        Raises:
            StorageValidationError: If the entropy is the wrong length or the
                mnemonic is empty.
        """
        raw_buffer = bytearray(raw)
        if len(raw_buffer) != _RECOVERY_KEY_SIZE:
            raise _storage_validation_error(
                f"recovery key must be exactly {_RECOVERY_KEY_SIZE} bytes; got {len(raw_buffer)}",
            )
        if not mnemonic:
            raise _storage_validation_error("recovery key mnemonic must not be empty")
        self._raw_buffer = raw_buffer
        self._mnemonic_buffer = bytearray(mnemonic.encode(_UTF_8_ENCODING))

    @property
    def raw(self) -> bytearray:
        """Return the live 32-byte entropy buffer.

        The buffer itself is returned, not a copy, so :meth:`wipe` reaches
        every holder of this reference.
        """
        return self._raw_buffer

    @property
    def mnemonic(self) -> str:
        """Return the 24-word mnemonic, decoded from its wipeable buffer."""
        return self._mnemonic_buffer.decode(_UTF_8_ENCODING)

    def wipe(self) -> None:
        """Overwrite the entropy and mnemonic buffers with zero bytes.

        Idempotent: wiping an already-wiped key is a no-op that leaves the
        buffers zeroed and their lengths unchanged.
        """
        _zeroise(self._raw_buffer)
        _zeroise(self._mnemonic_buffer)

    def __enter__(self) -> Self:
        """Return this key, so a ``with`` block bounds the secret's lifetime."""
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Wipe the buffers on block exit, whether or not the body raised."""
        self.wipe()


def _load_wordlist() -> tuple[str, ...]:
    """Load the bundled BIP-39 English wordlist.

    Read at import time so the per-call cost is the dict lookup, not
    the file read. The wordlist is small (~13 KB) and immutable.
    """
    path = Path(__file__).with_name("_bip39_wordlist.txt")
    text = path.read_text(encoding="ascii")
    words = tuple(line.strip() for line in text.splitlines() if line.strip())
    if len(words) != 2048:
        raise _storage_validation_error(
            f"BIP-39 wordlist must have exactly 2048 words; got {len(words)}",
        )
    return words


_WORDLIST: Final[tuple[str, ...]] = _load_wordlist()
_WORD_TO_INDEX: Final[dict[str, int]] = {w: i for i, w in enumerate(_WORDLIST)}


def encode_mnemonic(entropy: Buffer) -> str:
    """Encode 32 bytes of entropy as a 24-word BIP-39 English mnemonic.

    Args:
        entropy: Exactly 32 bytes of cryptographic entropy. Accepts any
            buffer, so a wipeable ``bytearray`` can be encoded without
            first being copied into immutable ``bytes``.

    Returns:
        A space-joined string of 24 lowercase English words.

    Raises:
        StorageValidationError: When ``entropy`` is not exactly 32 bytes.
    """
    entropy_view = memoryview(entropy)
    if len(entropy_view) != _RECOVERY_KEY_SIZE:
        raise _storage_validation_error(
            f"BIP-39 24-word encoding requires exactly {_RECOVERY_KEY_SIZE} bytes; got {len(entropy_view)}",
        )
    # ENT (256) + CS (8) = 264 bits -> 24 x 11-bit groups.
    # CS = first 8 bits of SHA-256(entropy).
    checksum = hashlib.sha256(entropy_view).digest()[0]
    payload_int = int.from_bytes(entropy_view, "big") << 8 | checksum
    indices: list[int] = []
    for shift in range(_MNEMONIC_WORD_COUNT - 1, -1, -1):
        indices.append((payload_int >> (shift * 11)) & 0x7FF)
    return " ".join(_WORDLIST[i] for i in indices)


def decode_mnemonic(mnemonic: str) -> bytearray:
    """Decode a 24-word BIP-39 English mnemonic back into 32 bytes of entropy.

    Args:
        mnemonic: A space-separated string of exactly 24 words from
            the BIP-39 English wordlist.

    Returns:
        The 32-byte entropy in a wipeable ``bytearray`` the caller is
        expected to :func:`zeroise` once it has finished deriving from it.

    Raises:
        StorageValidationError: When the mnemonic does not have 24 words, contains
            an unknown word, or fails the BIP-39 checksum.
    """
    words = mnemonic.strip().lower().split()
    if len(words) != _MNEMONIC_WORD_COUNT:
        raise _storage_validation_error(
            f"BIP-39 mnemonic must contain exactly {_MNEMONIC_WORD_COUNT} words; got {len(words)}",
        )
    payload_int = 0
    for position, word in enumerate(words, start=1):
        index = _WORD_TO_INDEX.get(word)
        if index is None:
            raise _storage_validation_error(
                f"unknown BIP-39 word at position {position}; verify the word against the BIP-39 English wordlist.",
            )
        payload_int = (payload_int << 11) | index
    # Split off the 8-bit checksum.
    checksum = payload_int & 0xFF
    entropy_int = payload_int >> 8
    entropy = bytearray(entropy_int.to_bytes(_RECOVERY_KEY_SIZE, "big"))
    expected = hashlib.sha256(entropy).digest()[0]
    if checksum != expected:
        _zeroise(entropy)
        raise _storage_validation_error("BIP-39 mnemonic checksum mismatch — verify the words")
    return entropy


def generate_recovery_key() -> RecoveryKey:
    """Mint a fresh :class:`RecoveryKey` with 32-byte entropy and its 24-word mnemonic.

    Uses :func:`secrets.token_bytes` for the entropy, which is copied into
    the returned key's wipeable buffers and then zeroed, so the immutable
    ``bytes`` the generator produced does not outlive this call. The
    returned record is the only remaining in-memory copy; callers must
    arrange for the operator to copy or print the mnemonic, then
    :meth:`RecoveryKey.wipe` it.
    """
    seed = bytearray(secrets.token_bytes(_RECOVERY_KEY_SIZE))
    try:
        return RecoveryKey(raw=seed, mnemonic=encode_mnemonic(seed))
    finally:
        _zeroise(seed)


__all__ = [
    "RecoveryKey",
    "decode_mnemonic",
    "encode_mnemonic",
    "generate_recovery_key",
]
