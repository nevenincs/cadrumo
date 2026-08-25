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

from ....core import StorageCustodyProfile


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

    Measured fact, not a justification: ``STORAGE_ROOT`` is bound to
    ``cadrumo_local_storage_root``, and every production
    :class:`~adapters.persistence.storage.blob_store.EncryptedBlobStore`
    construction at HEAD -- ``get_secret_store``, now the only one, since
    ``default_blob_store_roots`` went with the deleted master-key rotation
    sweep -- passes ``root_dir`` the SAME value.
    ``BLOB_STORE_ROOT`` appears at six sites in this tree and every one but
    its own declaration here is a comparison against that fact; it is bound
    to no value of its own anywhere.

    This member's original justification -- that ``root_dir`` was "a
    genuinely distinct value from the storage root in how production wires
    it today" -- was FALSE, not merely dated: commits ``69b2e4338208`` and
    ``5fbd329fd08d`` fixed a real ``blobs/blobs`` doubled-path bug by moving
    both call sites onto the plain storage root, which collapsed the value
    distinction this docstring used to claim. Two replacement
    justifications were then proposed and both were refuted by measurement
    before landing: that keeping the members apart prevents a
    directory-agreement gate from certifying a coincidental name-collision
    between two different anchors (dead once the anchors resolve to the
    same directory -- the agreement would be genuine, not coincidental);
    and that ``root_dir`` is caller-supplied and therefore not statically
    knowable (dead on inspection of the actual caller: every production
    path is settings-derived).

    Whether this two-member split still earns its place is, as of this
    writing, an OPEN QUESTION with no supporting answer on either side --
    not resolved by asserting a fourth justification nobody has measured.
    It is kept rather than collapsed because collapsing it is also an
    unmeasured claim, not because keeping it is justified. What changed as
    a direct consequence: the directory-agreement gate (in this package's
    ``tests/``) no longer excludes ``BLOB_STORE_ROOT``-anchored entries
    from its check -- that exclusion had no surviving justification
    either, and measurement (an isolated-archive mutation proof) showed
    including them costs nothing and catches a real break the prior
    exclusion missed.
    """

    STORAGE_ROOT = "storage_root"
    BLOB_STORE_ROOT = "blob_store_root"
