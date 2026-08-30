"""Error classes for the sealed bucket-export archive read / write path.

The classes descend from the existing domain
:class:`domain.buckets.BucketExportError` /
:class:`BucketImportError` so the CLI boundary's
``command_error_boundary`` routes them through the same surface as
the other bucket-maintenance verbs.
"""

from __future__ import annotations

from .....domain.buckets.errors import BucketExportError, BucketImportError


class SealedArchiveLayoutError(BucketImportError):
    """Raised when the sealed archive's tar layout does not match the expected contract.

    The expected layout is exactly two named members in the order
    ``header.json``, ``payload.envelope``. Extra members, out-of-order
    members, and unknown member names all raise this error before any
    decryption attempt so a tampered or wrong-framing archive fast-fails
    at the layout boundary.
    """


class SealedArchiveHeaderError(BucketImportError):
    """Raised when ``header.json`` fails strict-validation as :class:`ExportArchiveHeader`.

    Covers both schema-shape mismatches (missing or extra fields,
    wrong types, malformed manifest digest) and semantic refusals
    (unsupported ``archive_schema_version``).
    """


class SealedArchivePayloadError(BucketImportError):
    """Raised when the encrypted payload member cannot be decrypted or fails integrity.

    Distinct from :class:`SealedArchiveHeaderError` so the operator
    sees a precise failure mode: a bad header is fixable
    upstream (re-export); a bad payload typically means the archive
    was tampered with or the wrong key was supplied.
    """


class SealedArchiveWriteError(BucketExportError):
    """Raised when the sealed archive cannot be written to the operator-specified path.

    Covers IO errors (permission denied, disk full, target is a
    directory) at archive write time. The export service catches
    this and surfaces it through the CLI boundary's
    ``command_error_boundary`` without retry.
    """


__all__ = [
    "SealedArchiveHeaderError",
    "SealedArchiveLayoutError",
    "SealedArchivePayloadError",
    "SealedArchiveWriteError",
]
