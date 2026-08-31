"""Envelope substrate: JSON envelopes and secure-bound repositories.

Public surface for the schema-versioned envelope contract used by
file-backed persistence consumers. Re-exports the typed
:class:`Envelope` and
:class:`CipherEnvelope` records, the
:class:`AeadAlgorithm` catalogue, the
:class:`EncryptionMetadata` record, the
plaintext / ciphertext save/load helpers
(:func:`save_envelope`,
:func:`load_envelope`,
:func:`save_encrypted_envelope`,
:func:`load_encrypted_envelope`,
:func:`reencrypt_envelope_file`), and the
:class:`SecureBoundRepository` generic base
that domain repositories subclass for encrypted-object persistence.

The file helpers are the controlled plaintext/cipher envelope I/O
surface. :class:`SecureBoundRepository`
uses the encrypted SQL
:class:`adapters.persistence.storage.SecureObjectRepository`
backend instead; its path-shaped methods are logical diagnostics, not
authority to create plaintext sidecar files.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
