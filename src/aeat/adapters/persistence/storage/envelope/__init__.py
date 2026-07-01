"""Envelope substrate: JSON envelopes and secure-bound repositories.

Public surface for the schema-versioned envelope contract used by
file-backed persistence consumers. Re-exports the typed
:class:`~aeat.adapters.persistence.storage.Envelope` and
:class:`~aeat.adapters.persistence.storage.CipherEnvelope` records, the
:class:`~aeat.adapters.persistence.storage.AeadAlgorithm` catalogue, the
:class:`~aeat.adapters.persistence.storage.EncryptionMetadata` record, the
plaintext / ciphertext save/load helpers
(:func:`~aeat.adapters.persistence.storage.save_envelope`,
:func:`~aeat.adapters.persistence.storage.load_envelope`,
:func:`~aeat.adapters.persistence.storage.save_encrypted_envelope`,
:func:`~aeat.adapters.persistence.storage.load_encrypted_envelope`,
:func:`~aeat.adapters.persistence.storage.reencrypt_envelope_file`), and the
:class:`~aeat.adapters.persistence.storage.SecureBoundRepository` generic base
that domain repositories subclass for encrypted-object persistence.

The file helpers are the controlled plaintext/cipher envelope I/O
surface. :class:`~aeat.adapters.persistence.storage.SecureBoundRepository`
uses the encrypted SQL
:class:`~aeat.adapters.persistence.storage.SecureObjectRepository`
backend instead; its path-shaped methods are logical diagnostics, not
authority to create plaintext sidecar files.
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
