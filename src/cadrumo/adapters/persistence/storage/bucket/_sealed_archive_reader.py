"""Sealed bucket-export archive reader.

Validates the gzipped tar layout, strict-parses the header, and
yields the encrypted payload bytes + optional recovery-wrap bytes
for the caller to decrypt. Fast-fails on layout drift (extra,
missing, out-of-order, or unknown members) before any decryption
attempt so a tampered or wrong-version archive surfaces precisely.
"""

from __future__ import annotations

import gzip
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from .....core.product_identity import PRODUCT_IDENTITY
from ._export_header import ExportArchiveHeader
from ._sealed_archive_errors import (
    SealedArchiveHeaderError,
    SealedArchiveLayoutError,
    SealedArchivePayloadError,
)
from ._sealed_archive_writer import (
    CADRUMO_BUCKET_BUNDLE_SUFFIX,
    FORMER_PRODUCT_BUCKET_BUNDLE_SUFFIX,
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


def _read_member_info(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    """Read one already-discovered regular tar member."""
    extracted = archive.extractfile(member)
    if extracted is None:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: member {member.name!r} is not a regular file",
        )
    with extracted:
        return extracted.read()


def _read_member(archive: tarfile.TarFile, expected_name: str) -> bytes:
    """Read one required tar member by name, refusing an absent or empty one.

    The docstring already promised the empty case was refused; the check was
    missing. Both required members carry encrypted material, so zero bytes
    cannot be a legitimate value: an archive with an empty ``payload.envelope``
    is structurally valid, round-trips cleanly, and carries nothing to
    decrypt, while an empty declared ``recovery.wrap`` silently loses the
    recovery material the header says is present.
    """
    try:
        member = archive.getmember(expected_name)
    except KeyError as exc:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: required member {expected_name!r} is missing",
        ) from exc
    member_bytes = _read_member_info(archive, member)
    if not member_bytes:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: required member {expected_name!r} is empty",
        )
    return member_bytes


def _validate_source_suffix(source_path: Path) -> None:
    """Refuse a former-product suffix or any non-Cadrumo bundle suffix."""
    if source_path.name.endswith(FORMER_PRODUCT_BUCKET_BUNDLE_SUFFIX):
        raise SealedArchiveHeaderError(
            "sealed-archive read refused: former-product bundle suffix is incompatible with Cadrumo; "
            "the archive was not opened, migrated, copied, renamed, unpacked, or deleted",
        )
    if not source_path.name.endswith(CADRUMO_BUCKET_BUNDLE_SUFFIX):
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: source must end with {CADRUMO_BUCKET_BUNDLE_SUFFIX!r}",
        )


def _read_archive_header(archive: tarfile.TarFile) -> ExportArchiveHeader:
    """Read, product-guard, and strict-parse the archive's first (header) member."""
    first_member = archive.next()
    if first_member is None or first_member.name != HEADER_MEMBER_NAME:
        actual = None if first_member is None else first_member.name
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: first member must be {HEADER_MEMBER_NAME!r}, got {actual!r}",
        )
    header_bytes = _read_member_info(archive, first_member)
    try:
        raw_header = json.loads(header_bytes)
    except (TypeError, ValueError):
        raw_header = None
    if not isinstance(raw_header, dict) or raw_header.get("product") != PRODUCT_IDENTITY.python_package:
        raise SealedArchiveHeaderError(
            "sealed-archive read refused: header does not identify the canonical Cadrumo bundle format; "
            "payload members were not read and the archive was not migrated, copied, renamed, unpacked, "
            "or deleted",
        )
    try:
        return ExportArchiveHeader.model_validate_json(header_bytes)
    except Exception as exc:  # pydantic ValidationError or its subclasses
        raise SealedArchiveHeaderError(
            f"sealed-archive read refused: header schema validation failed: {type(exc).__name__}: {exc}",
        ) from exc


def _read_recovery_wrap(archive: tarfile.TarFile, header: ExportArchiveHeader) -> bytes | None:
    """Return the recovery-wrap member bytes when the header declares one present."""
    if header.recovery_wrap_present:
        return _read_member(archive, RECOVERY_WRAP_MEMBER_NAME)
    return None


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
            the expected contract (extra / missing / out-of-order /
            unknown members, non-regular members).
        SealedArchiveHeaderError: When ``header.json`` fails strict
            validation as :class:`ExportArchiveHeader`.
        SealedArchivePayloadError: When the payload member cannot be
            read, or when a torn write truncated the gzip stream so the
            decompression layer raises ``EOFError`` / ``gzip.BadGzipFile``.
            Decryption failures surface from this same class when the
            caller's :class:`Envelope` parse fails.

    Truncation-detection scope: a torn write that damages the gzip stream
    (the common case) is caught here at read time and surfaces as
    ``SealedArchivePayloadError``. A *near-complete* truncation that still
    decompresses to the expected two or three members passes this reader;
    it is caught downstream by the AEAD tag on the encrypted payload, which
    the importer verifies before it provisions any bucket store, so a torn
    archive never restores a partial bucket. Read-time detection of a
    near-complete truncation would require a trailing integrity marker in
    the archive format (writer + reader change); that hardening is a tracked
    follow-up recorded in the crash-window reference.
    """
    _validate_source_suffix(source_path)
    try:
        with tarfile.open(source_path, mode="r:gz") as archive:
            header = _read_archive_header(archive)

            member_names = tuple(member.name for member in archive.getmembers())
            _validate_layout(member_names)
            _validate_member_cardinality(member_names, header)

            payload_bytes = _read_member(archive, PAYLOAD_MEMBER_NAME)
            recovery_wrap_bytes = _read_recovery_wrap(archive, header)
    except tarfile.TarError as exc:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: tar layer rejected the archive: {type(exc).__name__}: {exc}",
        ) from exc
    except (gzip.BadGzipFile, EOFError) as exc:
        # A torn write truncates the gzip stream: the decompression layer
        # raises ``EOFError`` (stream ended before the end-of-stream marker)
        # or ``gzip.BadGzipFile`` (a damaged gzip header/CRC). Neither is an
        # ``OSError`` on every platform, so surface them explicitly as the
        # documented truncation error rather than leaking a raw builtin.
        raise SealedArchivePayloadError(
            f"sealed-archive read of {source_path!s} refused: archive is truncated or its gzip "
            f"stream is incomplete: {type(exc).__name__}: {exc}",
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


def _validate_member_cardinality(member_names: tuple[str, ...], header: ExportArchiveHeader) -> None:
    """Bind the member count to the header's own recovery declaration.

    Layout validation permits a third member by NAME, and the recovery reader
    consults only the header, so an archive repacked with an undeclared
    ``recovery.wrap`` read back cleanly: the header said no recovery material
    was present, the reader returned ``None``, and the extra member rode along
    unexamined. The count and the declaration are two statements about one
    fact and must agree.
    """
    expected_members = 3 if header.recovery_wrap_present else 2
    if len(member_names) != expected_members:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: header declares recovery_wrap_present="
            f"{header.recovery_wrap_present}, which requires exactly {expected_members} members, "
            f"got {len(member_names)}: {list(member_names)!r}",
        )


__all__ = ["SealedArchiveContents", "read_sealed_archive"]
