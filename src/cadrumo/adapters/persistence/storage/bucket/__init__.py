"""Per-bucket directory model under ``<cadrumo-root>/buckets/<bucket-id>/``.

Pydantic v2 strict records, error types, and filesystem primitives that compose
the multi-bucket on-disk layout. The facade exposes
:class:`BucketPaths` / :func:`bucket_paths` for the ``db/`` and ``blobs/``
tree.

The plaintext per-bucket manifest that once registered a bucket here is
retired: profile discovery, labels and key material all belong to the custody
capsule, and nothing in production reads or writes a manifest. Keystore helpers
(:func:`keystore_root`, :func:`keystore_path`,
:func:`validate_keystore_separation`, and :func:`keystore_sidecar_path`)
enforce that custody material lives outside the ``buckets/`` tree and the
per-bucket database directory.

The sealed-archive surface re-exports :data:`ARCHIVE_SCHEMA_VERSION`,
:class:`ExportArchiveHeader`, :class:`SealedArchiveContents`,
:func:`write_sealed_archive`, and :func:`read_sealed_archive` for
application-level bucket export/import. These helpers own archive shape and
metadata normalisation only; profile payload composition remains in
:mod:`application.user_profile`, while :mod:`application.bucket_maintenance`
orchestrates operator-facing export and import. The archive is a transport for
committed profile data alone: recovery material is a separate per-profile
artifact and never travels as an archive member.

See Also:
    :class:`ExportArchiveHeader`
        Plaintext frontmatter for sealed bucket-export archives.
    :func:`write_sealed_archive`
        Host-metadata-normalising writer for sealed export archives.
    :func:`read_sealed_archive`
        Reader that validates archive member order and header shape before
        returning encrypted payload bytes.
    :mod:`application.bucket_maintenance`
        Application service facade that composes these archive primitives with
        profile lifecycle and domain event history.
"""

from __future__ import annotations

from .errors import (
    BucketAlreadyPresentError,
    BucketBusyError,
    BucketError,
    BucketLockedError,
    BucketPathTooLongError,
    BucketValidationError,
    NoActiveBucketError,
    RecoveryUnavailableError,
    RecoveryVerificationError,
)
from ._export_header import ARCHIVE_SCHEMA_VERSION, ExportArchiveHeader
from ._keystore_paths import keystore_path, keystore_root, keystore_sidecar_path, validate_keystore_separation
from ._layout import BucketPaths, bucket_paths, trash_rename_and_remove
from ._lockfile import BucketLockTarget, acquire_lock, lock_path, release_lock
from ._output_language_hint import (
    clear_bucket_output_language_hint,
    normalize_output_language_hint,
    read_bucket_output_language_hint,
    write_bucket_output_language_hint,
)
from ._sealed_archive_errors import SealedArchiveLayoutError
from ._sealed_archive_reader import SealedArchiveContents, read_sealed_archive
from ._sealed_archive_writer import CADRUMO_BUCKET_BUNDLE_SUFFIX, write_sealed_archive

__all__ = [
    "ARCHIVE_SCHEMA_VERSION",
    "CADRUMO_BUCKET_BUNDLE_SUFFIX",
    "BucketAlreadyPresentError",
    "BucketBusyError",
    "BucketError",
    "BucketLockTarget",
    "BucketLockedError",
    "BucketPathTooLongError",
    "BucketPaths",
    "BucketValidationError",
    "ExportArchiveHeader",
    "NoActiveBucketError",
    "RecoveryUnavailableError",
    "RecoveryVerificationError",
    "SealedArchiveContents",
    "SealedArchiveLayoutError",
    "acquire_lock",
    "bucket_paths",
    "clear_bucket_output_language_hint",
    "keystore_path",
    "keystore_root",
    "keystore_sidecar_path",
    "lock_path",
    "normalize_output_language_hint",
    "read_bucket_output_language_hint",
    "read_sealed_archive",
    "release_lock",
    "trash_rename_and_remove",
    "validate_keystore_separation",
    "write_bucket_output_language_hint",
    "write_sealed_archive",
]
