"""Envelope substrate: JSON envelopes and secure-bound repositories.

Inert namespace. Consumers import from the defining modules directly:

* :mod:`cadrumo.adapters.persistence.storage.envelope.contract` defines the
  schema-versioned :class:`Envelope`, the :class:`AeadAlgorithm` catalogue,
  the :class:`EncryptionMetadata` record, and the non-sensitive file helpers
  :func:`save_envelope` and :func:`load_envelope`.
* :mod:`cadrumo.adapters.persistence.storage.envelope.secure_bound_repository`
  defines the :class:`SecureBoundRepository` generic base that domain
  repositories subclass for encrypted-object persistence.

Sensitive persistence uses the encrypted SQL :class:`SecureObjectRepository`
backend through :class:`SecureBoundRepository`; its path-shaped methods are
logical diagnostics, not authority to create sidecar files.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
