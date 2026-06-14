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
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ..crypto._crypto import (
    KEY_SIZE,
    EncryptedBlob,
    decrypt_record,
    derive_key,
    encrypt_record,
)
from ..errors import (
    storage_validation_error as _storage_validation_error,
)

_STRICT_FROZEN: Final = ConfigDict(strict=True, frozen=True, extra="forbid")

_RECOVERY_KEY_SIZE: Final[int] = 32
_MNEMONIC_WORD_COUNT: Final[int] = 24
_HKDF_CONTEXT_RECOVERY: Final[bytes] = b"aeat.recovery-key.master-wrap.v1"
_RECOVERY_AAD: Final[bytes] = b"aeat.recovery-key.aad.v1"


class RecoveryKey(BaseModel):
    """Frozen container for a 32-byte recovery key + its 24-word mnemonic.

    The substrate never persists the raw bytes or the mnemonic; this
    record exists in memory only at provision time so the CLI can
    display the mnemonic and the wrapping helper can derive a KEK from
    the bytes. After display + wrap, both fields are dropped from
    memory by Python's garbage collection.
    """

    model_config = _STRICT_FROZEN

    raw: bytes = Field(min_length=_RECOVERY_KEY_SIZE, max_length=_RECOVERY_KEY_SIZE)
    mnemonic: str = Field(min_length=1)


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


def encode_mnemonic(entropy: bytes) -> str:
    """Encode 32 bytes of entropy as a 24-word BIP-39 English mnemonic.

    Args:
        entropy: Exactly 32 bytes of cryptographic entropy.

    Returns:
        A space-joined string of 24 lowercase English words.

    Raises:
        StorageValidationError: When ``entropy`` is not exactly 32 bytes.
    """
    if len(entropy) != _RECOVERY_KEY_SIZE:
        raise _storage_validation_error(
            f"BIP-39 24-word encoding requires exactly {_RECOVERY_KEY_SIZE} bytes; got {len(entropy)}",
        )
    # ENT (256) + CS (8) = 264 bits -> 24 x 11-bit groups.
    # CS = first 8 bits of SHA-256(entropy).
    checksum = hashlib.sha256(entropy).digest()[0]
    payload_int = int.from_bytes(entropy, "big") << 8 | checksum
    indices: list[int] = []
    for shift in range(_MNEMONIC_WORD_COUNT - 1, -1, -1):
        indices.append((payload_int >> (shift * 11)) & 0x7FF)
    return " ".join(_WORDLIST[i] for i in indices)


def decode_mnemonic(mnemonic: str) -> bytes:
    """Decode a 24-word BIP-39 English mnemonic back into 32 bytes of entropy.

    Args:
        mnemonic: A space-separated string of exactly 24 words from
            the BIP-39 English wordlist.

    Returns:
        The 32-byte entropy.

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
    entropy = entropy_int.to_bytes(_RECOVERY_KEY_SIZE, "big")
    expected = hashlib.sha256(entropy).digest()[0]
    if checksum != expected:
        raise _storage_validation_error("BIP-39 mnemonic checksum mismatch — verify the words")
    return entropy


def generate_recovery_key() -> RecoveryKey:
    """Mint a fresh :class:`RecoveryKey` with 32-byte entropy and its 24-word mnemonic.

    Uses :func:`secrets.token_bytes` for the entropy. The returned
    record is the only in-memory copy; callers must arrange for the
    operator to copy or print the mnemonic before the record falls out
    of scope.
    """
    raw = secrets.token_bytes(_RECOVERY_KEY_SIZE)
    return RecoveryKey(raw=raw, mnemonic=encode_mnemonic(raw))


def _derive_recovery_kek(recovery_key_bytes: bytes) -> bytes:
    """Derive the 32-byte KEK that wraps the master key under the recovery key."""
    return derive_key(
        key_material=recovery_key_bytes,
        salt=b"",  # The recovery-key bytes are themselves high-entropy.
        context=_HKDF_CONTEXT_RECOVERY,
        length=KEY_SIZE,
    )


def wrap_master_key(*, master_key: bytes, recovery_key: RecoveryKey) -> WrappedMasterKey:
    """Wrap a 32-byte master key under a recovery-key-derived KEK.

    Args:
        master_key: The 32-byte master key to wrap.
        recovery_key: The recovery key whose bytes seed the wrapping KEK.

    Returns:
        A :class:`WrappedMasterKey` carrying the 12-byte nonce + the
        AES-256-GCM ciphertext. Serialise via ``model_dump_json()`` and
        persist to ``master.recovery.key``.

    Raises:
        StorageValidationError: When ``master_key`` is not exactly 32 bytes.
    """
    if len(master_key) != KEY_SIZE:
        raise _storage_validation_error(
            f"master key must be exactly {KEY_SIZE} bytes; got {len(master_key)}",
        )
    kek = _derive_recovery_kek(recovery_key.raw)
    blob = encrypt_record(master_key, key=kek, associated_data=_RECOVERY_AAD)
    return WrappedMasterKey.from_blob(blob)


def unwrap_master_key(*, wrapped: WrappedMasterKey, recovery_key_bytes: bytes) -> bytes:
    """Recover the 32-byte master key from a wrapped record + the recovery-key bytes.

    Args:
        wrapped: The :class:`WrappedMasterKey` loaded from disk.
        recovery_key_bytes: The 32-byte recovery key (decoded via
            :func:`decode_mnemonic`).

    Returns:
        The 32-byte master key.

    Raises:
        StorageValidationError: When ``recovery_key_bytes`` is not exactly 32 bytes.
    """
    if len(recovery_key_bytes) != _RECOVERY_KEY_SIZE:
        raise _storage_validation_error(
            f"recovery key must be exactly {_RECOVERY_KEY_SIZE} bytes; got {len(recovery_key_bytes)}",
        )
    kek = _derive_recovery_kek(recovery_key_bytes)
    return decrypt_record(wrapped.to_blob(), key=kek, associated_data=_RECOVERY_AAD)


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


__all__ = [
    "RecoveryKey",
    "WrappedMasterKey",
    "decode_mnemonic",
    "encode_mnemonic",
    "generate_recovery_key",
    "load_wrapped_master_key",
    "save_wrapped_master_key",
    "unwrap_master_key",
    "wrap_master_key",
]
