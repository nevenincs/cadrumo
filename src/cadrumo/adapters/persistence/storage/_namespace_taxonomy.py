"""Closed value sets describing how a secure-object namespace is held.

Four independent axes, deliberately separate rather than collapsed into one
"storage kind" enum: *scope* is who the data belongs to, *disposition* is what
a transport may carry, *mirror policy* is where a remote provider may hold it,
and *path kind* is what the hierarchy node physically is. A namespace picks one
value on each axis, and the combinations are not interchangeable — a
``PROFILE_LOCAL`` namespace can be ``STRUCTURED_CUSTODY`` or
``FULL_CUSTODY_ONLY``, and reading either off a single fused enum would lose
the distinction the custody gates depend on.

Separated from the namespace registry so the registry file holds namespace
declarations rather than the vocabulary they are declared in.

See Also:
    :mod:`~cadrumo.adapters.persistence.storage._namespace_registry`
        Declares every namespace using this vocabulary, and re-exports these
        names for the consumers that reach the registry directly.
"""

from __future__ import annotations

from enum import StrEnum


class StorageNamespaceScope(StrEnum):
    """Logical custody scope for a secure-object namespace."""

    PROFILE_LOCAL = "profile_local"
    BUCKET_LOCAL = "bucket_local"
    PROCESS_LOCAL = "process_local"


class StorageCustodyDisposition(StrEnum):
    """Transport custody disposition for one secure-object namespace."""

    STRUCTURED_CUSTODY = "structured_custody"
    FULL_CUSTODY_ONLY = "full_custody_only"
    DERIVED_REBUILDABLE = "derived_rebuildable"
    PROCESS_LOCAL = "process_local"


class StorageCustodyProfile(StrEnum):
    """Secure-object custody transport profile."""

    FULL = "full"
    STRUCTURED = "structured"


_CUSTODY_PROFILE_DISPOSITIONS: dict[StorageCustodyProfile, frozenset[StorageCustodyDisposition]] = {
    StorageCustodyProfile.FULL: frozenset(
        {
            StorageCustodyDisposition.STRUCTURED_CUSTODY,
            StorageCustodyDisposition.FULL_CUSTODY_ONLY,
        },
    ),
    StorageCustodyProfile.STRUCTURED: frozenset({StorageCustodyDisposition.STRUCTURED_CUSTODY}),
}


class StorageRemoteMirrorPolicy(StrEnum):
    """Remote-provider mirroring policy for one secure-object namespace."""

    CIPHERTEXT_WITH_METADATA = "ciphertext_with_metadata"
    LOCAL_ONLY = "local_only"
    TEST_ONLY = "test_only"


class StoragePathKind(StrEnum):
    """Persistent storage hierarchy node kind.

    A strict superset of the core taxonomy's :class:`StorageNodeKind`, which
    answers only "directory or file" because that is all the taxonomy needs to
    decide. This one additionally names ``LOGICAL_SQL``, for a record living in
    the encrypted database rather than on disk, and ``BLOB_OBJECT`` for
    content-addressed blob content -- concepts that belong to the adapter and
    would be noise in ``core``.

    Deliberately not merged with it: ``core`` must not import an adapter type,
    and a ``StrEnum`` carrying members cannot later be extended to subclass
    another. So the two agree by declared parity instead -- ``DIRECTORY`` and
    ``FILE`` carry identical values on both sides, pinned by a gate that
    covers the overlap alone. Adding a member here is expected and does not
    disturb that gate; **changing the spelling of a shared one does**, silently,
    because both enums are ``StrEnum`` and cross-boundary code compares them by
    value.
    """

    DIRECTORY = "directory"
    FILE = "file"
    LOGICAL_SQL = "logical_sql"
    BLOB_OBJECT = "blob_object"


class StoragePathAnchor(StrEnum):
    """Which directory a :class:`StoragePathDefinition` grammar's ``<root>`` token means.

    Declared because it is not one thing. Nearly every
    ``<root>``-anchored filesystem entry means the top-level storage root
    (``cadrumo_local_storage_root``); the three blob-content entries
    (``blob_manifest``, ``blob_content_plaintext``, ``blob_content_ciphertext``)
    instead anchor ``<root>`` at
    :class:`~adapters.persistence.storage.blob_store.EncryptedBlobStore`'s
    own ``root_dir`` constructor parameter -- a genuinely distinct value from
    the storage root in how production wires it today
    (``cadrumo_blob_store_dir``, which is itself already the storage root's
    ``blobs`` subdirectory). Conflating the two let a directory-agreement
    gate certify a match between two different anchors that happened to
    share a literal subdirectory name (``blobs``), rather than verifying
    anything real.
    """

    STORAGE_ROOT = "storage_root"
    BLOB_STORE_ROOT = "blob_store_root"
