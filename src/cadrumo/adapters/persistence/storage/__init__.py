"""Persistence layer public API.

Public API of the storage subpackage. Callers outside
:mod:`adapters.persistence.storage` must import only from here; internal
modules (``sql._orm``, ``sql.engine``, ``sql.session``, ``sql.repository``,
and the encryption substrate under ``crypto``,
``envelope``, ``master_key``, ``blob_store``, ``secret_store``) are
implementation details.

The phrase **encryption substrate** denotes the layered crypto stack
(master-key provider → envelope wrapper → encrypted blob store →
typed column helpers) that every persisted record passes through.
Throughout the package, "substrate" without a qualifier refers to
this stack.

The public surface is grouped by contract:

- SQL and secure-object persistence — engine/session helpers, typed catalogue
  repositories, :class:`SecureObjectRepository`, and the secure-object work
  records :class:`SecureObjectWrite`, :class:`SecureObjectDeletion`, and
  :class:`SecureObjectNamespaceIntegrity`.
- Inner-envelope version contract — :func:`inner_envelope_version_is_current`,
  the non-raising equality predicate every persisted read path applies to the
  ``schema_version`` of the :class:`Envelope` inside a decrypted payload. The
  layer-one row gate ``ensure_schema_version_readable`` is deliberately absent
  from this facade: it is a ceiling, and advertising it here would offer
  layer-two callers the wrong contract.
- Inner-envelope classification contract — :func:`inner_envelope_classification_is_expected`,
  the version predicate's non-raising sibling, applied to the ``classification``
  of the :class:`Envelope` inside a decrypted payload against the caller's own
  declared :class:`SensitivityClass`.
- Encryption substrate — :class:`Envelope`, :class:`CipherEnvelope`,
  :class:`EncryptedBlobStore`, :class:`SecretStore`, :func:`get_secret_store`
  (the route-canonical store factory), :class:`MasterKeyProvider`, and the
  column-level helpers :class:`EncryptedString`, :class:`EncryptedBytes`,
  :class:`EncryptedJSON`, and :class:`HashedLookup`.
- Runtime and custody boundary — :class:`StorageRuntime`,
  :class:`StorageRuntimeReadiness`, runtime repository factories,
  :func:`activate_session`, :func:`get_active_master_key`,
  :func:`~cadrumo.adapters.persistence.storage.resolve_attachment_store`, the one place a caller holding an optional
  injected :class:`~domain.attachments.AttachmentStoreProtocol` turns it into a
  concrete :class:`AttachmentStore`.
- Recovery — the low-level BIP-39 recovery helpers. The shared-master
  wrapping primitives are gone, and so is the master-key rotation sweep that
  re-wrapped every envelope between two providers: recovery and passphrase
  rotation are both per-profile custody operations.
- Secure-object hierarchy registry — :data:`STORAGE_NAMESPACE_REGISTRY`,
  :data:`STORAGE_PATH_DEFINITIONS`, namespace constants, and
  :func:`secure_object_logical_path` /
  :func:`secure_object_namespace_logical_path`; callers must use these
  exported symbols instead of constructing persisted secure-storage locations
  by hand.
- Governance helpers — :class:`SensitivityClass`, classification policies,
  redaction helpers, corpus manifests, path-safety helpers, and file-lock
  primitives.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
