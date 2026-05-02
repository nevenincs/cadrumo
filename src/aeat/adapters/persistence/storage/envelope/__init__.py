"""Envelope substrate: file-backed JSON and cipher envelope I/O.

Public surface for the schema-versioned envelope contract used by
file-backed persistence consumers. Re-exports the typed
:class:`Envelope` and :class:`CipherEnvelope` records, the
:class:`AeadAlgorithm` catalogue, the :class:`EncryptionMetadata`
record, the :class:`EnvelopeMigrator` extension protocol, and the
plaintext / ciphertext save/load helpers (:func:`save_envelope`,
:func:`load_envelope`, :func:`save_encrypted_envelope`,
:func:`load_encrypted_envelope`, :func:`reencrypt_envelope_file`).
"""

from __future__ import annotations

from ._envelope import (
    AeadAlgorithm,
    CipherEnvelope,
    EncryptionMetadata,
    Envelope,
    EnvelopeMigrator,
    load_encrypted_envelope,
    load_envelope,
    reencrypt_envelope_file,
    save_encrypted_envelope,
    save_envelope,
)

__all__ = [
    "AeadAlgorithm",
    "CipherEnvelope",
    "EncryptionMetadata",
    "Envelope",
    "EnvelopeMigrator",
    "load_encrypted_envelope",
    "load_envelope",
    "reencrypt_envelope_file",
    "save_encrypted_envelope",
    "save_envelope",
]
