"""Per-bucket directory model under ``<cadrumo-root>/buckets/<bucket-id>/``.

Pydantic v2 strict records, error types, and filesystem primitives that compose
the multi-bucket on-disk layout. The namespace is an inert marker and exports
nothing: every consumer imports from the module that defines the symbol.
:mod:`directory_layout` owns :class:`BucketPaths` / :func:`bucket_paths` for the
``db/`` and ``blobs/`` tree, and :mod:`lockfile` owns the per-bucket ``.lock``
concurrency primitive.

The plaintext per-bucket manifest that once registered a bucket here is
retired: profile discovery, labels and key material all belong to the custody
capsule, and nothing in production reads or writes a manifest. The keystore
helpers in :mod:`keystore_paths` enforce that custody material lives outside the
``buckets/`` tree and the per-bucket database directory.

The sealed-archive surface spans three modules: :mod:`export_archive_header`
defines :data:`ARCHIVE_SCHEMA_VERSION` and :class:`ExportArchiveHeader`, while
:mod:`sealed_archive_writer` and :mod:`sealed_archive_reader` own
:func:`write_sealed_archive` and :func:`read_sealed_archive` for
application-level bucket export/import. These helpers own archive shape and
metadata normalisation only; profile payload composition remains in
:mod:`application.user_profile`, while :mod:`application.bucket_maintenance`
orchestrates operator-facing export and import. The archive is a transport for
committed profile data alone: recovery material is a separate per-profile
artifact and never travels as an archive member.

See Also:
    :mod:`directory_layout`
        Resolves and destroys the per-bucket directory tree.
    :mod:`export_archive_header`
        Plaintext frontmatter record for sealed bucket-export archives.
    :mod:`sealed_archive_writer`
        Host-metadata-normalising writer for sealed export archives.
    :mod:`sealed_archive_reader`
        Reader that validates archive member order and header shape before
        returning encrypted payload bytes.
    :mod:`application.bucket_maintenance`
        Application service facade that composes these archive primitives with
        profile lifecycle and domain event history.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
