"""Sealed bucket-export archive writer.

Writes a gzipped tar archive carrying the plaintext
:class:`ExportArchiveHeader` followed by the encrypted payload bytes.
The layout is fixed at exactly those two members: there is no optional
member, so the archive's shape is a constant rather than something the
header negotiates. Metadata for every tar member is normalised at
write time (timestamps pinned to the header's ``created_at``, mode
pinned to ``0o400``, ownership cleared) so two same-bucket exports
differ only in the header's ``created_at`` field.
"""

from __future__ import annotations

import io
import os
import tarfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .....core.external_constants import UTF_8_ENCODING
from .....core.fsync import fsync_parent_dir
from .....core.logging import get_logger
from .....core.product_identity import PRODUCT_IDENTITY
from ._export_header import ExportArchiveHeader
from ._sealed_archive_errors import SealedArchiveWriteError

_log = get_logger(__name__)

# Canonical member names. The layout MUST stay positional — the
# reader validates the order. New member kinds open a new archive
# schema version.
HEADER_MEMBER_NAME = "header.json"
PAYLOAD_MEMBER_NAME = "payload.envelope"
#: The archive's members, in the one order the reader accepts.
SEALED_ARCHIVE_MEMBER_NAMES = (HEADER_MEMBER_NAME, PAYLOAD_MEMBER_NAME)
CADRUMO_BUCKET_BUNDLE_SUFFIX = f".{PRODUCT_IDENTITY.python_package}-bucket.tar.gz"
FORMER_PRODUCT_BUCKET_BUNDLE_SUFFIX = ".aeat-bucket.tar.gz"

_NORMALISED_MODE = 0o400
_NORMALISED_UID = 0
_NORMALISED_GID = 0
_NORMALISED_UNAME = ""
_NORMALISED_GNAME = ""


def _normalised_tarinfo(name: str, size: int, instant: datetime) -> tarfile.TarInfo:
    """Construct a :class:`tarfile.TarInfo` with host-leak-free metadata.

    Every module that writes a member into a sealed-archive tar MUST
    use this helper rather than constructing :class:`tarfile.TarInfo`
    directly. Codified by the sealed-archive-metadata-normalisation
    rule candidate. Pins the modification time to the supplied
    instant, the mode to ``0o400`` (operator-read only), and clears
    ownership so the archive byte-stream is reproducible across
    hosts.
    """
    info = tarfile.TarInfo(name)
    info.size = size
    info.mtime = int(instant.timestamp())
    info.mode = _NORMALISED_MODE
    info.uid = _NORMALISED_UID
    info.gid = _NORMALISED_GID
    info.uname = _NORMALISED_UNAME
    info.gname = _NORMALISED_GNAME
    info.type = tarfile.REGTYPE
    return info


def write_sealed_archive(
    target_path: Path,
    *,
    header: ExportArchiveHeader,
    payload_bytes: bytes,
) -> None:
    """Write the sealed archive at ``target_path``.

    Args:
        target_path: Operator-specified output path. Must be writable
            and must not exist (the writer refuses to overwrite a
            sealed archive to avoid accidental clobber; remove the
            file first if a re-export is intended).
        header: Strict-validated :class:`ExportArchiveHeader`. The
            writer serialises it to UTF-8 JSON as the first archive
            member.
        payload_bytes: The sealed payload, OPAQUE to this
            writer. It is written byte-for-byte as the second and last
            archive member and is never parsed, validated or interpreted
            here.

            This deliberately does NOT require an
            :class:`~adapters.persistence.storage.Envelope`, and said so
            once by mistake. The archive is a transport: its guarantee is
            verbatim carriage, and binding it to one payload type would
            couple the transport to whichever caller happened to be first.
            Parsing here would be worse than useless -- it would let the
            transport REFUSE a sealed payload it could not understand,
            which for encrypted material is a liability rather than a
            safeguard.

            Opaque is not unconstrained. Empty is refused below, because
            an empty payload yields a structurally valid archive carrying
            nothing to decrypt. Beyond that the caller owns the payload's
            shape, its decryption, and its integrity: this layer verifies
            no digest, including the header's ``manifest_digest``, which
            it carries rather than checks.

    Raises:
        SealedArchiveWriteError: When ``target_path`` carries the wrong
            suffix, already exists, ``payload_bytes`` is empty,
            or the underlying IO write fails.
    """
    if target_path.name.endswith(FORMER_PRODUCT_BUCKET_BUNDLE_SUFFIX):
        raise SealedArchiveWriteError(
            "sealed-archive write refused: former-product bundle suffix is incompatible with Cadrumo",
        )
    if not target_path.name.endswith(CADRUMO_BUCKET_BUNDLE_SUFFIX):
        raise SealedArchiveWriteError(
            f"sealed-archive write refused: target must end with {CADRUMO_BUCKET_BUNDLE_SUFFIX!r}",
        )
    # The payload member carries encrypted material, so zero bytes is never a
    # legitimate value. An empty payload produced a structurally valid archive
    # that round-tripped cleanly and carried nothing to decrypt.
    if not payload_bytes:
        raise SealedArchiveWriteError(
            "sealed-archive write refused: payload_bytes is empty; there would be nothing to decrypt",
        )
    if target_path.exists():
        raise SealedArchiveWriteError(
            f"sealed-archive write refused: target_path {target_path!s} already exists; "
            f"remove it first if a re-export is intended",
        )

    header_bytes = header.model_dump_json().encode(UTF_8_ENCODING)
    instant = header.created_at
    # Staged at a unique sibling and moved into place only once every member
    # is written. Building directly at the operator's path meant a failure
    # part-way through left a partial tarball exactly where a complete archive
    # was expected: the next reader saw an apparently valid file with a
    # truncated layout, and a retry could not use the no-overwrite guard above
    # without the operator deleting the wreckage by hand.
    staging_path = target_path.with_name(f"{target_path.name}.{uuid4().hex}.partial")
    try:
        with tarfile.open(staging_path, mode="w:gz") as archive:
            header_info = _normalised_tarinfo(HEADER_MEMBER_NAME, len(header_bytes), instant)
            archive.addfile(header_info, io.BytesIO(header_bytes))
            payload_info = _normalised_tarinfo(PAYLOAD_MEMBER_NAME, len(payload_bytes), instant)
            archive.addfile(payload_info, io.BytesIO(payload_bytes))
        os.replace(staging_path, target_path)
        # The rename is only a directory-entry change until that entry is
        # durable. Without this the archive can survive a crash as a name
        # pointing at nothing, which the no-overwrite guard above then
        # refuses to let the operator re-export over.
        fsync_parent_dir(target_path)
    except OSError as exc:
        _discard_staging_archive(staging_path)
        raise SealedArchiveWriteError(
            f"sealed-archive write to {target_path!s} failed: {type(exc).__name__}: {exc}",
        ) from exc
    except BaseException:
        # Includes the caller interrupting the export. The staged file is this
        # function's own temporary, so it is removed on every exit that does
        # not reach the rename.
        _discard_staging_archive(staging_path)
        raise


def _discard_staging_archive(staging_path: Path) -> None:
    """Remove the staged archive, ignoring an already-absent file.

    Failure to clean up must not mask the write failure being unwound, so a
    removal error is swallowed here; the residue carries the ``.partial``
    suffix that marks it as never having been a complete archive.
    """
    try:
        staging_path.unlink(missing_ok=True)
    except OSError:
        _log.warning("sealed-archive staging cleanup failed", exc_info=True)


__all__ = [
    "CADRUMO_BUCKET_BUNDLE_SUFFIX",
    "FORMER_PRODUCT_BUCKET_BUNDLE_SUFFIX",
    "HEADER_MEMBER_NAME",
    "PAYLOAD_MEMBER_NAME",
    "SEALED_ARCHIVE_MEMBER_NAMES",
    "write_sealed_archive",
]
