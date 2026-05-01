"""Envelope substrate: file-backed JSON / cipher envelope I/O.

Bucket boundary established by audit-4 in the aeat-restructure ADR.
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
