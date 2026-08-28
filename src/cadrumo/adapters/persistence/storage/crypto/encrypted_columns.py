"""SQLAlchemy ``TypeDecorator`` set for column-level at-rest encryption.

Four type decorators wrap the AEAD primitives behind SQLAlchemy's
``TypeDecorator`` interface so consumer ORM models declare encryption
at the column level without touching the cipher directly:

- :class:`EncryptedString` — round-trips a Python ``str`` through
  AES-256-GCM. Storage type is ``LargeBinary``.
- :class:`EncryptedBytes` — round-trips raw ``bytes``. Storage type is
  ``LargeBinary``.
- :class:`EncryptedJSON` — JSON-serialises any pydantic-mode-compatible
  Python value, then encrypts. Storage type is ``LargeBinary``.
- :class:`HashedLookup` — deterministic HMAC-SHA256 keyed by a
  sub-key derived from the master key plus a stable ``context``.
  Storage type is ``LargeBinary`` (32 bytes). Use this column when
  consumers need ``WHERE column = ?`` lookups against an
  :class:`EncryptedString`-shaped value without leaking the
  plaintext.

:class:`EncryptedPayload` validates the decoded JSON result from
:class:`EncryptedJSON`, while the secure-object helpers bind
``namespace``, ``object_key`` digest, and ``schema_version`` into
payload AEAD associated data so ciphertext copied across rows fails
authentication.

All decorators and helpers resolve key bytes through
:func:`~adapters.persistence.storage.master_key._active_session.get_active_master_key`
on the active
:class:`~adapters.persistence.storage.master_key._bucket_session.BucketSession`.
Tests use :class:`~cadrumo.tests.master_key.EphemeralMasterKeyProvider`,
whose context manager enters a real session without touching the OS
keychain or file backend.

The AAD (associated authenticated data) per decorator binds the
ciphertext to its purpose: a ciphertext minted for an
:class:`EncryptedString` column will refuse to decrypt as
:class:`EncryptedBytes` even though the master key is the same.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import override

from pydantic import BaseModel, ConfigDict
from sqlalchemy import LargeBinary
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from .....core.hashing import canonical_json_bytes
from ..errors import (
    DecryptionError,
)
from ..errors import (
    storage_validation_error as _storage_validation_error,
)
from ..master_key import get_active_hmac_subkey, get_active_master_key
from .aead import EncryptedBlob, decrypt_record, derive_key, encrypt_record


class EncryptedPayload(BaseModel):
    """Validated wrapper for a value decrypted from an :class:`EncryptedJSON` column.

    The single ``data`` field carries the decoded JSON value (dict, list,
    str, int, float, bool, or None).  Wrapping the raw ``json.loads``
    result in a typed model ensures the decrypt path is auditable and
    rejects structurally invalid bytes at the persistence boundary rather
    than propagating bare ``object`` into domain code.
    """

    model_config = ConfigDict(strict=False)

    data: object


_AAD_STRING = b"cadrumo.column.encrypted_string.v1"
_AAD_BYTES = b"cadrumo.column.encrypted_bytes.v1"
_AAD_JSON = b"cadrumo.column.encrypted_json.v1"
_HKDF_CONTEXT_COLUMN_LOOKUP = b"cadrumo.column.hashed_lookup.v1"


_AAD_SECURE_OBJECT_PAYLOAD = b"cadrumo.secure-object.payload.v2"


def secure_object_payload_aad(namespace: str, object_key_digest: bytes, schema_version: int) -> bytes:
    """Bind a secure-object row's identity into its payload AEAD associated data.

    The associated data length-prefixes the namespace, the ``object_key`` HMAC
    digest, and the schema version so the AEAD authentication tag is valid only
    for the exact row that produced the ciphertext. A ciphertext copied into a
    different ``(namespace, object_key)`` row fails the tag and refuses to
    decrypt, closing the at-rest row-substitution gap.
    """
    namespace_bytes = namespace.encode("utf-8")
    return b"".join(
        (
            _AAD_SECURE_OBJECT_PAYLOAD,
            len(namespace_bytes).to_bytes(4, "big"),
            namespace_bytes,
            len(object_key_digest).to_bytes(4, "big"),
            bytes(object_key_digest),
            schema_version.to_bytes(4, "big"),
        ),
    )


def secure_object_key_digest(object_key: str | bytes) -> bytes:
    """Return the stored ``object_key`` digest for a natural or pre-digested key.

    Mirrors the :class:`HashedLookup` column's bind behaviour so the digest used
    to build the payload AAD at write time matches the digest persisted in the
    ``object_key`` column (and therefore the value reconstructed on read).
    """
    if isinstance(object_key, bytes | bytearray | memoryview):
        return bytes(object_key)
    return HashedLookup.compute(object_key)


def encrypt_secure_object_payload(plaintext: bytes, *, associated_data: bytes) -> bytes:
    """Encrypt a secure-object payload under the active DEK, bound to ``associated_data``."""
    key = _resolve_master_key()
    return encrypt_record(plaintext, key=key, associated_data=associated_data).to_wire()


def decrypt_secure_object_payload(wire: bytes, *, associated_data: bytes) -> bytes:
    """Decrypt a row-AAD-bound secure-object payload; raises on a tag mismatch."""
    blob = EncryptedBlob.from_wire(wire)
    key = _resolve_master_key()
    return decrypt_record(blob, key=key, associated_data=associated_data)


def decrypt_encrypted_bytes_column(wire: bytes) -> bytes:
    """Decrypt one ``EncryptedBytes`` on-wire payload under the active master key.

    Exposed so iterator consumers (notably
    :class:`adapters.persistence.storage.SecureObjectRepository`)
    can decrypt rows one-by-one inside their own try/except, rather than
    delegating to SQLAlchemy's column processor whose failure mode aborts
    the entire result-set materialisation.

    Args:
        wire: The raw on-wire bytes stored in an ``EncryptedBytes`` column
            (``nonce || ciphertext_with_tag``).

    Returns:
        The decrypted plaintext bytes.
    """
    blob = EncryptedBlob.from_wire(wire)
    key = _resolve_master_key()
    return decrypt_record(blob, key=key, associated_data=_AAD_BYTES)


_HASHED_LOOKUP_DIGEST_SIZE = 32
"""HMAC-SHA256 digest size in bytes."""


def _resolve_master_key() -> bytes:
    """Resolve the column-level encryption key from the active session.

    Delegates to :func:`get_active_master_key`, which reads the DEK
    of the :class:`BucketSession` bound to the active-session
    ``ContextVar``. Raises
    :class:`NoActiveBucketSessionError` when no session block is
    active on the calling thread or task.
    """
    return get_active_master_key()


class EncryptedString(TypeDecorator[str]):
    """SQLAlchemy column type that round-trips ``str`` through AES-256-GCM.

    Storage type is ``LargeBinary``; values stored on disk are
    ``nonce || ciphertext_with_tag`` bytes. Plaintext is encoded as
    UTF-8 before encryption.
    """

    impl = LargeBinary
    cache_ok = True

    @override
    def process_bind_param(self, value: str | None, dialect: Dialect) -> bytes | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise _storage_validation_error(f"EncryptedString expects str; got {type(value).__name__}")
        key = _resolve_master_key()
        blob = encrypt_record(value.encode("utf-8"), key=key, associated_data=_AAD_STRING)
        return blob.to_wire()

    @override
    def process_result_value(self, value: bytes | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        key = _resolve_master_key()
        blob = EncryptedBlob.from_wire(bytes(value))
        plaintext = decrypt_record(blob, key=key, associated_data=_AAD_STRING)
        try:
            return plaintext.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DecryptionError("EncryptedString payload is not valid UTF-8") from exc


class EncryptedBytes(TypeDecorator[bytes]):
    """SQLAlchemy column type that round-trips raw ``bytes`` through AES-256-GCM.

    Storage type is ``LargeBinary``. Useful for opaque binary payloads
    that must be ciphertext at rest (e.g. SHA-256-derived index
    tags, certificate thumbprints, encrypted-blob descriptors).
    """

    impl = LargeBinary
    cache_ok = True

    @override
    def process_bind_param(self, value: bytes | None, dialect: Dialect) -> bytes | None:
        if value is None:
            return None
        if not isinstance(value, bytes | bytearray | memoryview):
            raise _storage_validation_error(f"EncryptedBytes expects bytes-like; got {type(value).__name__}")
        key = _resolve_master_key()
        blob = encrypt_record(bytes(value), key=key, associated_data=_AAD_BYTES)
        return blob.to_wire()

    @override
    def process_result_value(self, value: bytes | None, dialect: Dialect) -> bytes | None:
        if value is None:
            return None
        key = _resolve_master_key()
        blob = EncryptedBlob.from_wire(bytes(value))
        return decrypt_record(blob, key=key, associated_data=_AAD_BYTES)


class EncryptedJSON(TypeDecorator[object]):
    """SQLAlchemy column type that JSON-encodes and then encrypts a value.

    Storage type is ``LargeBinary``. Values must be JSON-serialisable
    via :func:`json.dumps` with ``ensure_ascii=False``,
    ``separators=(',', ':')``, ``sort_keys=True`` so the on-wire form
    is deterministic for identical inputs (modulo nonces).
    """

    impl = LargeBinary
    cache_ok = True

    @override
    def process_bind_param(self, value: object | None, dialect: Dialect) -> bytes | None:
        if value is None:
            return None
        try:
            serialised = canonical_json_bytes(value)
        except (TypeError, ValueError) as exc:
            raise _storage_validation_error(f"EncryptedJSON expects a JSON-serialisable value: {exc}") from exc
        key = _resolve_master_key()
        blob = encrypt_record(serialised, key=key, associated_data=_AAD_JSON)
        return blob.to_wire()

    @override
    def process_result_value(self, value: bytes | None, dialect: Dialect) -> object | None:
        if value is None:
            return None
        key = _resolve_master_key()
        blob = EncryptedBlob.from_wire(bytes(value))
        plaintext = decrypt_record(blob, key=key, associated_data=_AAD_JSON)
        try:
            decoded = plaintext.decode("utf-8")
            return EncryptedPayload(data=json.loads(decoded)).data
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DecryptionError("EncryptedJSON payload is not valid JSON") from exc


class HashedLookup(TypeDecorator[bytes]):
    """Deterministic HMAC-SHA256 keyed by a master-key-derived sub-key.

    Storage type is ``LargeBinary`` (32 bytes). The HMAC key is derived
    from the master key via HKDF-SHA256 with a stable ``context``, so
    the same plaintext maps to the same digest across processes that
    share the master key. The plaintext is NEVER recoverable from the
    digest.

    Bind accepts a ``str`` (digested via :meth:`compute`) or already-
    computed ``bytes`` (pass-through after size validation). Result is
    always the raw 32-byte digest.

    Use cases:

    - Indexable lookup of an encrypted natural key (e.g. a secret
      identifier whose plaintext lives in a sibling
      :class:`EncryptedString` column). Consumers query
      ``WHERE lookup_column = "plaintext"`` (the str is digested at
      bind time) or ``WHERE lookup_column = HashedLookup.compute(...)``.
    - Idempotency keys keyed by sensitive content where the digest is
      acceptable as the storage key.

    Security note: deterministic encryption / hashing is only safe when
    the consumer accepts that two equal plaintexts produce equal
    digests (they do, by design; that is the point). Do NOT use this
    decorator for low-entropy plaintexts (e.g. yes/no flags, short
    enumerations) — a frequency analysis on the digest column would
    leak the plaintext distribution.
    """

    impl = LargeBinary
    cache_ok = True

    @classmethod
    def compute(cls, plaintext: str) -> bytes:
        """Compute the HMAC-SHA256 digest of ``plaintext``.

        Args:
            plaintext: The natural-key string to digest.

        Returns:
            32 raw bytes — the deterministic lookup digest.

        Raises:
            StorageValidationError: When ``plaintext`` is not a string.
        """
        if not isinstance(plaintext, str):
            raise _storage_validation_error(f"HashedLookup.compute expects str; got {type(plaintext).__name__}")
        # The sub-key depends only on the active DEK and the column-lookup
        # context, so it is resolved through the session-scoped memo rather
        # than re-derived per digest; the HMAC over ``plaintext`` is the only
        # per-call work. Byte-identical to
        # ``hkdf_hmac_digest(get_active_master_key(), ...)`` by construction.
        sub_key = get_active_hmac_subkey(_HKDF_CONTEXT_COLUMN_LOOKUP)
        return hmac.new(sub_key, plaintext.encode("utf-8"), hashlib.sha256).digest()

    @override
    def process_bind_param(self, value: str | bytes | None, dialect: Dialect) -> bytes | None:
        if value is None:
            return None
        if isinstance(value, str):
            return self.compute(value)
        if isinstance(value, bytes | bytearray | memoryview):
            digest = bytes(value)
            if len(digest) != _HASHED_LOOKUP_DIGEST_SIZE:
                raise _storage_validation_error(
                    f"HashedLookup pre-computed digest must be {_HASHED_LOOKUP_DIGEST_SIZE} bytes; got {len(digest)}",
                )
            return digest
        raise _storage_validation_error(
            f"HashedLookup expects str or bytes; got {type(value).__name__}",
        )

    @override
    def process_result_value(self, value: bytes | None, dialect: Dialect) -> bytes | None:
        if value is None:
            return None
        # The plaintext is intentionally not recoverable. We hand back
        # the raw digest so callers can compare it against another
        # ``compute()`` result.
        if len(value) != _HASHED_LOOKUP_DIGEST_SIZE:
            raise _storage_validation_error(
                f"HashedLookup expects {_HASHED_LOOKUP_DIGEST_SIZE}-byte digests; got {len(value)}",
            )
        return bytes(value)
