"""Recovery-key generation, encoding, and master-key wrapping.

The recovery-key story for the secure-persistence substrate is two-
fold:

1. **Mnemonic encoding**: a 32-byte recovery key is encoded as a
   24-word BIP-39 English mnemonic for human-readability. The
   operator prints the mnemonic at provision time and stores it
   somewhere safe; lost passphrase / lost keychain implies recovery
   via this mnemonic. The substrate never persists the mnemonic on
   disk.

2. **Recovery-key wrapping**: at provision time, the master key is
   wrapped under an HKDF-SHA256-derived KEK seeded by the recovery
   key, and the wrapped ciphertext is persisted as
   ``master.recovery.key``. When the active master-key provider
   becomes unavailable (forgotten passphrase, locked keychain,
   broken keyring), operator key-management code supplies the
   recovery mnemonic and the substrate uses the wrapping to mint a
   fresh ``master.key`` + ``master.kdf`` + ``salt`` triplet under the
   chosen new backend.

This module exports the cryptographic primitives only; command wiring
must remain outside the storage substrate.

**Wipeable key material.** Every secret this module mints or recovers —
the recovery entropy, the mnemonic, the derived recovery KEK, and the
unwrapped master key — is held in a ``bytearray`` rather than immutable
``bytes`` / ``str``, so the substrate's :func:`zeroise` primitive can
overwrite it in place. The recovery surface needs this more than the
steady-state session path does: its exposure window opens on every mint,
unwrap, and passphrase change, and an enrollment holds live key material
across the operator's interactive confirmation. Functions that derive a
KEK zero it in a ``finally`` before returning; functions that *return*
key material hand back a buffer the caller is expected to zero once it
has finished with it.

The honest limit is unchanged from the one the session path already
discloses: passing a buffer to a ``bytes``-typed cryptographic primitive,
or reading the mnemonic as a ``str``, materialises a transient immutable
copy whose lifetime the garbage collector owns. Those copies are bounded
by a single call; what this module no longer does is hold the *only*
copy of a secret in a form no wipe primitive can reach.

The encoding follows BIP-39 (Bitcoin Improvement Proposal 0039)
exactly — 256-bit entropy → 8-bit checksum → 24 11-bit words drawn
from the canonical English wordlist. The wordlist is bundled at
:file:`_bip39_wordlist.txt` (2048 lines, public domain, identical
to the Bitcoin Core source).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import secrets
from collections.abc import Buffer, Callable
from pathlib import Path
from typing import Final, Self

from pydantic import BaseModel, Field, ValidationError

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ..crypto import (
    KEY_SIZE,
    EncryptedBlob,
    decrypt_record,
    derive_key,
    encrypt_record,
)
from ..errors import (
    storage_validation_error as _storage_validation_error,
)
from ._zeroise import zeroise as _zeroise

_RECOVERY_KEY_SIZE: Final[int] = 32
_MNEMONIC_WORD_COUNT: Final[int] = 24
_HKDF_CONTEXT_RECOVERY: Final[bytes] = b"cadrumo.recovery-key.master-wrap.v1"
_RECOVERY_AAD: Final[bytes] = b"cadrumo.recovery-key.aad.v1"


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
    buffers mutable, and — because there is no ``model_dump_json`` — makes
    it structurally impossible to serialise the secret by accident.

    Honest contract, identical in kind to the one ``BucketSession``
    discloses: reading :attr:`mnemonic` materialises a transient ``str``
    copy whose lifetime the garbage collector owns, and passing
    :attr:`raw` to a ``bytes``-typed cryptographic primitive materialises a
    transient ``bytes`` copy for the duration of that call. The buffers this
    object *holds* are wipeable; those short-lived boundary copies are not.
    """

    __slots__ = ("_mnemonic_buffer", "_raw_buffer")

    def __init__(self, *, raw: Buffer, mnemonic: str) -> None:
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
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.wipe()


class WrappedMasterKey(BaseModel):
    """Frozen container for the recovery-key-wrapped master.key file.

    Persisted as JSON at ``<secret_store_dir>/master.recovery.key``.
    The operator's recovery key is the only material that can unwrap
    this file; the substrate's regular providers (keyring,
    file-fallback, unsecured) cannot consume it.

    The nonce and ciphertext are stored as base64 strings (rather than
    raw ``bytes``) so the JSON serialisation is portable across pydantic
    versions and operating systems. The ``to_blob`` / ``from_blob``
    helpers convert back to the in-memory :class:`EncryptedBlob` form.
    """

    model_config = _STRICT_FROZEN

    schema_version: int = Field(default=1, ge=1)
    nonce_b64: str = Field(min_length=1)
    ciphertext_b64: str = Field(min_length=1)

    def to_blob(self) -> EncryptedBlob:
        """Decode the base64 fields into an :class:`EncryptedBlob`."""
        try:
            return EncryptedBlob(
                nonce=base64.b64decode(self.nonce_b64.encode("ascii"), validate=True),
                ciphertext=base64.b64decode(self.ciphertext_b64.encode("ascii"), validate=True),
            )
        except (ValueError, binascii.Error, ValidationError) as exc:
            raise _storage_validation_error("wrapped recovery master key is malformed") from exc

    @classmethod
    def from_blob(cls, blob: EncryptedBlob) -> WrappedMasterKey:
        """Build a :class:`WrappedMasterKey` from an in-memory blob."""
        return cls(
            nonce_b64=base64.b64encode(blob.nonce).decode("ascii"),
            ciphertext_b64=base64.b64encode(blob.ciphertext).decode("ascii"),
        )


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


def _derive_recovery_kek(recovery_key_bytes: Buffer) -> bytearray:
    """Derive the 32-byte KEK that wraps the master key under the recovery key.

    Returns a wipeable ``bytearray``; every caller zeroes it once the wrap
    or unwrap it seeds has completed.
    """
    return bytearray(
        derive_key(
            key_material=bytes(recovery_key_bytes),
            salt=b"",  # The recovery-key bytes are themselves high-entropy.
            context=_HKDF_CONTEXT_RECOVERY,
            length=KEY_SIZE,
        ),
    )


def wrap_master_key(*, master_key: Buffer, recovery_key: RecoveryKey) -> WrappedMasterKey:
    """Wrap a 32-byte master key under a recovery-key-derived KEK.

    Args:
        master_key: The 32-byte master key to wrap. Accepts any buffer, so
            a wipeable ``bytearray`` need not be copied into immutable
            ``bytes`` by the caller.
        recovery_key: The recovery key whose bytes seed the wrapping KEK.

    Returns:
        A :class:`WrappedMasterKey` carrying the 12-byte nonce + the
        AES-256-GCM ciphertext. Serialise via ``model_dump_json()`` and
        persist to ``master.recovery.key``.

    Raises:
        StorageValidationError: When ``master_key`` is not exactly 32 bytes.
    """
    master_key_view = memoryview(master_key)
    if len(master_key_view) != KEY_SIZE:
        raise _storage_validation_error(
            f"master key must be exactly {KEY_SIZE} bytes; got {len(master_key_view)}",
        )
    kek = _derive_recovery_kek(recovery_key.raw)
    try:
        blob = encrypt_record(bytes(master_key_view), key=bytes(kek), associated_data=_RECOVERY_AAD)
    finally:
        _zeroise(kek)
    return WrappedMasterKey.from_blob(blob)


def unwrap_master_key(*, wrapped: WrappedMasterKey, recovery_key_bytes: Buffer) -> bytearray:
    """Recover the 32-byte master key from a wrapped record + the recovery-key bytes.

    Args:
        wrapped: The :class:`WrappedMasterKey` loaded from disk.
        recovery_key_bytes: The 32-byte recovery key (decoded via
            :func:`decode_mnemonic`).

    Returns:
        The 32-byte master key in a wipeable ``bytearray`` the caller is
        expected to :func:`zeroise` once it has re-minted custody from it.

    Raises:
        StorageValidationError: When ``recovery_key_bytes`` is not exactly 32 bytes.
    """
    recovery_view = memoryview(recovery_key_bytes)
    if len(recovery_view) != _RECOVERY_KEY_SIZE:
        raise _storage_validation_error(
            f"recovery key must be exactly {_RECOVERY_KEY_SIZE} bytes; got {len(recovery_view)}",
        )
    kek = _derive_recovery_kek(recovery_view)
    try:
        return bytearray(
            decrypt_record(wrapped.to_blob(), key=bytes(kek), associated_data=_RECOVERY_AAD),
        )
    finally:
        _zeroise(kek)


def save_wrapped_master_key(wrapped: WrappedMasterKey, path: Path) -> None:
    """Atomically persist a wrapped master key to ``path``.

    Uses the substrate's ``atomic_write_secure_bytes`` helper so the
    file lands restricted from creation (mode 0o600), the tempfile is
    fsynced before the ``os.replace`` swap, and the parent directory
    entry is fsynced after — durable across power loss on POSIX.
    """
    from ._master_key import atomic_write_secure_bytes

    payload = wrapped.model_dump_json().encode(_UTF_8_ENCODING)
    atomic_write_secure_bytes(path, payload)


def load_wrapped_master_key(path: Path) -> WrappedMasterKey:
    """Read and validate a wrapped-master-key file, returning a :class:`WrappedMasterKey`."""
    try:
        return WrappedMasterKey.model_validate_json(path.read_text(encoding=_UTF_8_ENCODING))
    except (OSError, ValueError, ValidationError) as exc:
        raise _storage_validation_error("wrapped recovery master key file is malformed") from exc


def atomically_install_verified_recovery(
    *,
    path: Path,
    payload: bytes,
    verify: Callable[[], None],
) -> None:
    """Persist ``payload`` to ``path`` only after ``verify`` passes.

    This is the single ordering guarantee behind recovery ``create`` and
    ``rotate``: the candidate recovery envelope must be *fully* verified — a
    real mnemonic unwrap / AES-GCM tag check, never a string comparison —
    before it may replace whatever is already on disk. ``verify`` MUST raise
    when the candidate is not valid; it returns ``None`` only when the
    candidate is proven good.

    Because the atomic write is not reached until ``verify`` returns without
    raising, a cancelled, mistyped, or corrupt candidate leaves any prior
    recovery envelope at ``path`` byte-for-byte untouched. The write itself
    goes through the substrate's ``atomic_write_secure_bytes`` (restrictive
    permissions from creation, fsync, ``os.replace``), so the replacement is
    all-or-nothing and never leaves a torn envelope.

    Args:
        path: Destination recovery-envelope path.
        payload: The serialized candidate envelope bytes to install.
        verify: A zero-argument callable that fully validates the candidate and
            raises on any failure.
    """
    verify()
    from ._master_key import atomic_write_secure_bytes

    atomic_write_secure_bytes(path, payload)


__all__ = [
    "RecoveryKey",
    "WrappedMasterKey",
    "atomically_install_verified_recovery",
    "decode_mnemonic",
    "encode_mnemonic",
    "generate_recovery_key",
    "load_wrapped_master_key",
    "save_wrapped_master_key",
    "unwrap_master_key",
    "wrap_master_key",
]
