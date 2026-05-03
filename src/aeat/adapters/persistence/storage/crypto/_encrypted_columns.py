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

All decorators consult :func:`get_master_key_provider` lazily on
every bind and result conversion. Tests inject an
:class:`EphemeralMasterKeyProvider` via the
:func:`override_master_key_provider` test helper so the SQLite
round-trip uses a deterministic key without touching the OS keychain
or the file backend.

The AAD (associated authenticated data) per decorator binds the
ciphertext to its purpose: a ciphertext minted for an
:class:`EncryptedString` column will refuse to decrypt as
:class:`EncryptedBytes` even though the master key is the same.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from typing import Any

from sqlalchemy import LargeBinary
from sqlalchemy.types import TypeDecorator

from .....core.logging import get_logger
from ..master_key._master_key import MasterKeyProvider, get_master_key_provider
from ._crypto import EncryptedBlob, decrypt_record, derive_key, encrypt_record

_log = get_logger(__name__)
_LOW_ENTROPY_LENGTH_THRESHOLD = 12  # sec-M-4: warn below this byte-length
_low_entropy_warning_emitted = False

_AAD_STRING = b"aeat.column.encrypted_string.v1"
_AAD_BYTES = b"aeat.column.encrypted_bytes.v1"
_AAD_JSON = b"aeat.column.encrypted_json.v1"
_HKDF_CONTEXT_COLUMN_LOOKUP = b"aeat.column.hashed_lookup.v1"

_HASHED_LOOKUP_DIGEST_SIZE = 32
"""HMAC-SHA256 digest size in bytes."""


_provider_lock = threading.Lock()
_provider_override: MasterKeyProvider | None = None


def override_master_key_provider(provider: MasterKeyProvider | None) -> None:
    """Test helper: install (or clear) a process-wide provider override.

    Args:
        provider: The provider every column decorator should use, or
            ``None`` to clear the override and revert to the standard
            :func:`get_master_key_provider` resolution.
    """
    global _provider_override
    with _provider_lock:
        _provider_override = provider


def _resolve_master_key() -> bytes:
    """Resolve the master key honouring the test override when set."""
    return _resolve_master_key_provider().get_master_key()


def _resolve_master_key_provider() -> MasterKeyProvider:
    """Resolve the active :class:`MasterKeyProvider`, honouring the override.

    Returns the provider installed via :func:`override_master_key_provider`
    when set; otherwise falls back to the standard
    :func:`get_master_key_provider` resolution. Encrypted-envelope
    consumers (per-domain repositories) call this helper rather than
    receiving the provider through their constructor so the same
    test-override discipline that gates column-level decrypt also gates
    envelope-level decrypt.
    """
    with _provider_lock:
        override = _provider_override
    if override is not None:
        return override
    return get_master_key_provider()


class EncryptedString(TypeDecorator[str]):
    """SQLAlchemy column type that round-trips ``str`` through AES-256-GCM.

    Storage type is ``LargeBinary``; values stored on disk are
    ``nonce || ciphertext_with_tag`` bytes. Plaintext is encoded as
    UTF-8 before encryption.
    """

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f"EncryptedString expects str; got {type(value).__name__}")
        key = _resolve_master_key()
        blob = encrypt_record(value.encode("utf-8"), key=key, associated_data=_AAD_STRING)
        return blob.to_wire()

    def process_result_value(self, value: bytes | None, dialect: Any) -> str | None:
        if value is None:
            return None
        key = _resolve_master_key()
        blob = EncryptedBlob.from_wire(bytes(value))
        plaintext = decrypt_record(blob, key=key, associated_data=_AAD_STRING)
        return plaintext.decode("utf-8")


class EncryptedBytes(TypeDecorator[bytes]):
    """SQLAlchemy column type that round-trips raw ``bytes`` through AES-256-GCM.

    Storage type is ``LargeBinary``. Useful for opaque binary payloads
    that must be ciphertext at rest (e.g. SHA-256-derived index
    tags, certificate thumbprints, encrypted-blob descriptors).
    """

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: bytes | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        if not isinstance(value, bytes | bytearray | memoryview):
            raise TypeError(f"EncryptedBytes expects bytes-like; got {type(value).__name__}")
        key = _resolve_master_key()
        blob = encrypt_record(bytes(value), key=key, associated_data=_AAD_BYTES)
        return blob.to_wire()

    def process_result_value(self, value: bytes | None, dialect: Any) -> bytes | None:
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

    def process_bind_param(self, value: object | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        try:
            serialised = json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise TypeError(f"EncryptedJSON expects a JSON-serialisable value: {exc}") from exc
        key = _resolve_master_key()
        blob = encrypt_record(serialised, key=key, associated_data=_AAD_JSON)
        return blob.to_wire()

    def process_result_value(self, value: bytes | None, dialect: Any) -> object | None:
        if value is None:
            return None
        key = _resolve_master_key()
        blob = EncryptedBlob.from_wire(bytes(value))
        plaintext = decrypt_record(blob, key=key, associated_data=_AAD_JSON)
        return json.loads(plaintext.decode("utf-8"))


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

    @staticmethod
    def _derive_lookup_key(master_key: bytes) -> bytes:
        return derive_key(
            key_material=master_key,
            salt=b"",
            context=_HKDF_CONTEXT_COLUMN_LOOKUP,
        )

    @classmethod
    def compute(cls, plaintext: str) -> bytes:
        """Compute the HMAC-SHA256 digest of ``plaintext``.

        Emits a one-shot WARNING (sec-M-4) when ``plaintext`` is
        shorter than 12 bytes — short plaintexts are vulnerable to
        frequency-analysis attacks against the deterministic digest
        column. The warning is suppressed for the rest of the process
        lifetime so high-volume call sites do not spam the log.

        Args:
            plaintext: The natural-key string to digest.

        Returns:
            32 raw bytes — the deterministic lookup digest.
        """
        if not isinstance(plaintext, str):
            raise TypeError(f"HashedLookup.compute expects str; got {type(plaintext).__name__}")
        global _low_entropy_warning_emitted
        if len(plaintext.encode("utf-8")) < _LOW_ENTROPY_LENGTH_THRESHOLD and not _low_entropy_warning_emitted:
            _log.warning(
                "hashed_lookup.compute called on a plaintext shorter than %d bytes; "
                "short plaintexts are vulnerable to frequency analysis on the "
                "deterministic digest column (logged once per process)",
                _LOW_ENTROPY_LENGTH_THRESHOLD,
            )
            _low_entropy_warning_emitted = True
        key = _resolve_master_key()
        sub_key = cls._derive_lookup_key(key)
        return hmac.new(sub_key, plaintext.encode("utf-8"), hashlib.sha256).digest()

    def process_bind_param(self, value: str | bytes | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        if isinstance(value, str):
            return self.compute(value)
        if isinstance(value, bytes | bytearray | memoryview):
            digest = bytes(value)
            if len(digest) != _HASHED_LOOKUP_DIGEST_SIZE:
                raise ValueError(
                    f"HashedLookup pre-computed digest must be {_HASHED_LOOKUP_DIGEST_SIZE} bytes; got {len(digest)}",
                )
            return digest
        raise TypeError(
            f"HashedLookup expects str or bytes; got {type(value).__name__}",
        )

    def process_result_value(self, value: bytes | None, dialect: Any) -> bytes | None:
        if value is None:
            return None
        # The plaintext is intentionally not recoverable. We hand back
        # the raw digest so callers can compare it against another
        # ``compute()`` result.
        if len(value) != _HASHED_LOOKUP_DIGEST_SIZE:
            raise ValueError(
                f"HashedLookup expects {_HASHED_LOOKUP_DIGEST_SIZE}-byte digests; got {len(value)}",
            )
        return bytes(value)
