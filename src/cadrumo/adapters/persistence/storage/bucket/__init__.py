"""Per-bucket directory model under ``<cadrumo-root>/buckets/<bucket-id>/``.

Pydantic v2 strict records, error types, and filesystem primitives that compose
the multi-bucket on-disk layout. The facade exposes
:class:`BucketPaths` / :func:`bucket_paths` /
:func:`provision_bucket_directory` for the ``db/``, ``blobs/``, and
``audit/`` tree; :class:`BucketManifest`,
:class:`ManifestKdfParams` and :class:`BucketKeySchedule` for the plaintext
manifest; and
:func:`read_manifest` / :func:`write_manifest` for strict TOML I/O.

The manifest is discovery metadata only: bucket identity, operator label,
UTC timestamps, public Argon2id KDF parameters and salt, recovery-enrollment
state, idle-lock setting, key schedule, schema version, and lifecycle mirror.
It must not contain passphrases, derived keys, wrapped DEKs, recovery secrets,
taxpayer payloads, or secure-object ciphertext. Keystore helpers
(:func:`keystore_root`, :func:`keystore_path`, and
:func:`validate_keystore_separation`) enforce that custody material lives
outside the ``buckets/`` tree and the per-bucket database directory.

The sealed-archive surface re-exports :class:`ExportArchiveHeader`,
:class:`SealedArchiveContents`, :func:`write_sealed_archive`, and
:func:`read_sealed_archive` for application-level bucket export/import. These
helpers own archive shape and metadata normalisation only; profile payload
composition remains in :mod:`application.user_profile`, while
:mod:`application.bucket_maintenance` orchestrates operator-facing export
and import.

See Also:
    :class:`BucketManifest`
        Strict per-bucket manifest record stored beside the bucket directory.
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

from ._errors import (
    BucketAlreadyPresentError,
    BucketBusyError,
    BucketError,
    BucketLockedError,
    BucketValidationError,
    NoActiveBucketError,
    RecoveryUnavailableError,
    RecoveryVerificationError,
)
from ._export_header import ExportArchiveHeader
from ._keystore_paths import keystore_path, keystore_root, validate_keystore_separation
from ._layout import BucketPaths, bucket_paths, provision_bucket_directory
from ._lockfile import acquire_lock, lock_path, release_lock
from ._manifest import (
    BUCKET_MANIFEST_DURABILITY_FLOOR,
    BUCKET_MANIFEST_SCHEMA_VERSION,
    BucketKeySchedule,
    BucketManifest,
    ManifestKdfParams,
)
from ._manifest_io import (
    MISSING_BUCKET_MANIFEST_MESSAGE,
    ensure_manifest_schema_readable,
    manifest_path,
    read_manifest,
    write_manifest,
)
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
    "BUCKET_MANIFEST_DURABILITY_FLOOR",
    "BUCKET_MANIFEST_SCHEMA_VERSION",
    "CADRUMO_BUCKET_BUNDLE_SUFFIX",
    "MISSING_BUCKET_MANIFEST_MESSAGE",
    "BucketAlreadyPresentError",
    "BucketBusyError",
    "BucketError",
    "BucketKeySchedule",
    "BucketLockedError",
    "BucketManifest",
    "BucketPaths",
    "BucketValidationError",
    "ExportArchiveHeader",
    "ManifestKdfParams",
    "NoActiveBucketError",
    "RecoveryUnavailableError",
    "RecoveryVerificationError",
    "SealedArchiveContents",
    "SealedArchiveLayoutError",
    "acquire_lock",
    "bucket_paths",
    "clear_bucket_output_language_hint",
    "ensure_manifest_schema_readable",
    "keystore_path",
    "keystore_root",
    "lock_path",
    "manifest_path",
    "normalize_output_language_hint",
    "provision_bucket_directory",
    "read_bucket_output_language_hint",
    "read_manifest",
    "read_sealed_archive",
    "release_lock",
    "validate_keystore_separation",
    "write_bucket_output_language_hint",
    "write_manifest",
    "write_sealed_archive",
]
