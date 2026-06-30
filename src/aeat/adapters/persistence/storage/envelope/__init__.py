"""Envelope substrate: file-backed JSON and cipher envelope I/O.

Public surface for the schema-versioned envelope contract used by
file-backed persistence consumers. Re-exports the typed
:class:`Envelope` and :class:`CipherEnvelope` records, the
:class:`AeadAlgorithm` catalogue, the :class:`EncryptionMetadata`
record, the plaintext / ciphertext save/load helpers (:func:`save_envelope`,
:func:`load_envelope`, :func:`save_encrypted_envelope`,
:func:`load_encrypted_envelope`, :func:`reencrypt_envelope_file`),
and the :class:`SecureBoundRepository` generic base that domain
repositories subclass for encrypted-object persistence.
"""

from __future__ import annotations

from ._envelope import (
    AeadAlgorithm,
    CipherEnvelope,
    EncryptionMetadata,
    Envelope,
    load_encrypted_envelope,
    load_envelope,
    reencrypt_envelope_file,
    save_encrypted_envelope,
    save_envelope,
)
from ._secure_repository import SecureBoundRepository

__all__ = [
    "AeadAlgorithm",
    "CipherEnvelope",
    "EncryptionMetadata",
    "Envelope",
    "SecureBoundRepository",
    "load_encrypted_envelope",
    "load_envelope",
    "reencrypt_envelope_file",
    "save_encrypted_envelope",
    "save_envelope",
]
