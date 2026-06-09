"""Sealed bucket-export archive reader.

Validates the gzipped tar layout, strict-parses the header, and
yields the encrypted payload bytes + optional recovery-wrap bytes
for the caller to decrypt. Fast-fails on layout drift (extra,
missing, out-of-order, or unknown members) before any decryption
attempt so a tampered or wrong-version archive surfaces precisely.

Authority: ``2026-06-03-bucket-sealed-archive-adr``.
"""

from __future__ import annotations

import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from ._export_header import ExportArchiveHeader
from ._sealed_archive_errors import (
    SealedArchiveHeaderError,
    SealedArchiveLayoutError,
    SealedArchivePayloadError,
)
from ._sealed_archive_writer import (
    HEADER_MEMBER_NAME,
    PAYLOAD_MEMBER_NAME,
    RECOVERY_WRAP_MEMBER_NAME,
)


@dataclass(frozen=True)
class SealedArchiveContents:
    """Decoded sealed-archive contents ready for downstream decryption.

    The reader returns this aggregate so the caller composes its
    own decryption + validation pipeline without re-parsing the
    archive. ``payload_envelope_bytes`` is opaque to this layer —
    the caller deserialises it via the existing :class:`Envelope`
    pipeline.
    """

    __test__: ClassVar[bool] = False

    header: ExportArchiveHeader
    payload_envelope_bytes: bytes
    recovery_wrap_bytes: bytes | None


def _read_member(archive: tarfile.TarFile, expected_name: str) -> bytes:
    """Read one tar member by name; raise layout error if absent or empty."""
    try:
        member = archive.getmember(expected_name)
    except KeyError as exc:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: required member {expected_name!r} is missing",
        ) from exc
    extracted = archive.extractfile(member)
    if extracted is None:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: member {expected_name!r} is not a regular file",
        )
    with extracted:
        return extracted.read()


def read_sealed_archive(source_path: Path) -> SealedArchiveContents:
    """Read and strict-validate a sealed bucket-export archive.

    Args:
        source_path: Operator-specified input path.

    Returns:
        A :class:`SealedArchiveContents` carrying the parsed header,
        the encrypted payload bytes, and the optional recovery-wrap
        bytes when ``header.recovery_wrap_present`` is ``True``.

    Raises:
        SealedArchiveLayoutError: When the tar layout deviates from
            the ADR contract (extra / missing / out-of-order /
            unknown members, non-regular members).
        SealedArchiveHeaderError: When ``header.json`` fails strict
            validation as :class:`ExportArchiveHeader`.
        SealedArchivePayloadError: When the payload member cannot be
            read (truncated archive). Decryption failures surface
            from this same class when the caller's
            :class:`Envelope` parse fails.
    """
    try:
        with tarfile.open(source_path, mode="r:gz") as archive:
            member_names = tuple(member.name for member in archive.getmembers())
            _validate_layout(member_names)

            header_bytes = _read_member(archive, HEADER_MEMBER_NAME)
            try:
                header = ExportArchiveHeader.model_validate_json(header_bytes)
            except Exception as exc:  # pydantic ValidationError or its subclasses
                raise SealedArchiveHeaderError(
                    f"sealed-archive read refused: header schema validation failed: {type(exc).__name__}: {exc}",
                ) from exc

            payload_bytes = _read_member(archive, PAYLOAD_MEMBER_NAME)
            recovery_wrap_bytes: bytes | None = None
            if header.recovery_wrap_present:
                recovery_wrap_bytes = _read_member(archive, RECOVERY_WRAP_MEMBER_NAME)
    except tarfile.TarError as exc:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: tar layer rejected the archive: {type(exc).__name__}: {exc}",
        ) from exc
    except OSError as exc:
        raise SealedArchivePayloadError(
            f"sealed-archive read of {source_path!s} failed at IO layer: {type(exc).__name__}: {exc}",
        ) from exc

    return SealedArchiveContents(
        header=header,
        payload_envelope_bytes=payload_bytes,
        recovery_wrap_bytes=recovery_wrap_bytes,
    )


def _validate_layout(member_names: tuple[str, ...]) -> None:
    """Ensure the archive carries exactly the expected member set in order."""
    if len(member_names) not in (2, 3):
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: expected 2 or 3 members, got {len(member_names)}: {list(member_names)!r}",
        )
    if member_names[0] != HEADER_MEMBER_NAME:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: first member must be {HEADER_MEMBER_NAME!r}, got {member_names[0]!r}",
        )
    if member_names[1] != PAYLOAD_MEMBER_NAME:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: second member must be {PAYLOAD_MEMBER_NAME!r}, got {member_names[1]!r}",
        )
    if len(member_names) == 3 and member_names[2] != RECOVERY_WRAP_MEMBER_NAME:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: third member must be {RECOVERY_WRAP_MEMBER_NAME!r}, got {member_names[2]!r}",
        )


__all__ = ["SealedArchiveContents", "read_sealed_archive"]
