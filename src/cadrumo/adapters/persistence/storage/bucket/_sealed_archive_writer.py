"""Sealed bucket-export archive writer.

Writes a gzipped tar archive carrying the plaintext
:class:`ExportArchiveHeader` followed by the encrypted payload bytes
and an optional recovery-wrap member. Metadata for every tar member
is normalised at write time (timestamps pinned to the header's
``created_at``, mode pinned to ``0o400``, ownership cleared) so two
same-bucket exports differ only in the header's ``created_at`` field.

Authority: ``2026-06-03-bucket-sealed-archive-adr``.
"""

from __future__ import annotations

import io
import tarfile
from datetime import datetime
from pathlib import Path

from .....core.external_constants import UTF_8_ENCODING
from ._export_header import ExportArchiveHeader
from ._sealed_archive_errors import SealedArchiveWriteError

# Canonical member names. The layout MUST stay positional — the
# reader validates the order. New member kinds open a new archive
# schema version per the ADR.
HEADER_MEMBER_NAME = "header.json"
PAYLOAD_MEMBER_NAME = "payload.envelope"
RECOVERY_WRAP_MEMBER_NAME = "recovery.wrap"

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
    payload_envelope_bytes: bytes,
    recovery_wrap_bytes: bytes | None = None,
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
        payload_envelope_bytes: The encrypted payload bytes (already
            wrapped in an :class:`Envelope` by the caller). Written
            as the second archive member.
        recovery_wrap_bytes: Optional recovery-wrap material. When
            present the header MUST carry
            ``recovery_wrap_present = True``; when ``None`` the header
            MUST carry ``recovery_wrap_present = False``.

    Raises:
        SealedArchiveWriteError: When ``target_path`` exists, the
            header's ``recovery_wrap_present`` flag disagrees with
            ``recovery_wrap_bytes``, or the underlying IO write fails.
    """
    if recovery_wrap_bytes is not None and not header.recovery_wrap_present:
        raise SealedArchiveWriteError(
            "sealed-archive write refused: recovery_wrap_bytes supplied but header.recovery_wrap_present is False",
        )
    if recovery_wrap_bytes is None and header.recovery_wrap_present:
        raise SealedArchiveWriteError(
            "sealed-archive write refused: header.recovery_wrap_present is True but no recovery_wrap_bytes supplied",
        )
    if target_path.exists():
        raise SealedArchiveWriteError(
            f"sealed-archive write refused: target_path {target_path!s} already exists; "
            f"remove it first if a re-export is intended",
        )

    header_bytes = header.model_dump_json().encode(UTF_8_ENCODING)
    instant = header.created_at
    try:
        with tarfile.open(target_path, mode="w:gz") as archive:
            header_info = _normalised_tarinfo(HEADER_MEMBER_NAME, len(header_bytes), instant)
            archive.addfile(header_info, io.BytesIO(header_bytes))
            payload_info = _normalised_tarinfo(PAYLOAD_MEMBER_NAME, len(payload_envelope_bytes), instant)
            archive.addfile(payload_info, io.BytesIO(payload_envelope_bytes))
            if recovery_wrap_bytes is not None:
                recovery_info = _normalised_tarinfo(RECOVERY_WRAP_MEMBER_NAME, len(recovery_wrap_bytes), instant)
                archive.addfile(recovery_info, io.BytesIO(recovery_wrap_bytes))
    except OSError as exc:
        raise SealedArchiveWriteError(
            f"sealed-archive write to {target_path!s} failed: {type(exc).__name__}: {exc}",
        ) from exc


__all__ = [
    "HEADER_MEMBER_NAME",
    "PAYLOAD_MEMBER_NAME",
    "RECOVERY_WRAP_MEMBER_NAME",
    "write_sealed_archive",
]
