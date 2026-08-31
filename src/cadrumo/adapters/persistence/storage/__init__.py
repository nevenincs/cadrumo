"""Inert namespace for the persistence storage package.

This package exports nothing. Every contract below has one canonical defining
module, and callers -- inside the package and out -- import it from there.

The phrase **encryption substrate** denotes the layered crypto stack
(master-key provider → envelope wrapper → encrypted blob store →
typed column helpers) that every persisted record passes through.
Throughout the package, "substrate" without a qualifier refers to
this stack.

Where the contracts live:

- SQL and secure-object persistence — ``sql.engine``, ``sql.session`` and
  ``sql.secure_objects``, which defines :class:`SecureObjectRepository` and the
  secure-object work records :class:`SecureObjectWrite`,
  :class:`SecureObjectDeletion` and :class:`SecureObjectNamespaceIntegrity`.
- Schema lineage — ``schema_lineage``, holding both version gates: the
  non-raising inner-envelope predicates
  :func:`inner_envelope_version_is_current` and
  :func:`inner_envelope_classification_is_expected`, and the layer-one row
  ceiling :func:`ensure_schema_version_readable`. The two are different
  contracts; a layer-two caller wants the predicates.
- Encryption substrate — ``envelope``, ``blob_store``, ``master_key``,
  ``secret_store`` and ``crypto``, defining :class:`Envelope`,
  :class:`CipherEnvelope`, :class:`EncryptedBlobStore`, :class:`SecretStore`,
  :class:`MasterKeyProvider` and the column-level helpers
  :class:`EncryptedString`, :class:`EncryptedBytes`, :class:`EncryptedJSON`
  and :class:`HashedLookup`.
- Runtime and custody boundary — ``runtime`` and ``runtime_readiness`` for
  :class:`StorageRuntime` and :class:`StorageRuntimeReadiness`,
  ``runtime_repository`` for the repository factories, ``custody`` for the
  per-profile custody operations, and ``profile_custody`` /
  ``profile_login_session`` for the concrete application-port adapters.
- Recovery — ``recovery_key``, the low-level BIP-39 helpers. Recovery and
  passphrase rotation are both per-profile custody operations; the
  shared-master wrapping primitives and the cross-provider rotation sweep are
  gone.
- Secure-object hierarchy — ``namespace_taxonomy`` for the vocabulary,
  ``secure_object_namespaces`` for the namespace declarations,
  ``storage_path_definitions`` for :data:`STORAGE_PATH_DEFINITIONS`, and
  ``namespace_registry`` for :data:`STORAGE_NAMESPACE_REGISTRY` and
  :func:`secure_object_logical_path` /
  :func:`secure_object_namespace_logical_path`. Persisted secure-storage
  locations come from these; never construct one by hand.
- Governance helpers — ``path_safety`` for path containment, ``errors`` for
  the package error hierarchy, and ``bucket`` for the file-lock primitives.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
