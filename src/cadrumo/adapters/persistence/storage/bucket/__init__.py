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

__all__: tuple[str, ...] = ()
