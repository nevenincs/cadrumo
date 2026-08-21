"""Sealed bucket-export archive reader.

Validates the gzipped tar layout, strict-parses the header, and yields
the encrypted payload bytes for the caller to decrypt. Fast-fails on
layout drift (extra, missing, out-of-order, or unknown members) before
any decryption attempt so a tampered or wrong-framing archive surfaces
precisely.

The accepted layout is one fixed tuple of member names, so the member
set is not a function of anything the header says. An archive is either
exactly those members in exactly that order or it is refused; there is
no shape whose validity depends on a declaration inside the archive
being truthful about itself.
"""

from __future__ import annotations

import gzip
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Final

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
    SEALED_ARCHIVE_MEMBER_NAMES,
)


@dataclass(frozen=True)
class SealedArchiveContents:
    """Decoded sealed-archive contents ready for downstream decryption.

    The reader returns this aggregate so the caller composes its
    own decryption and validation pipeline without re-parsing the
    archive.

    ``payload_bytes`` is OPAQUE to this layer, in both
    directions: the writer stored whatever it was handed, and this
    reader returns those bytes verbatim without parsing, validating or
    verifying them. It names no payload type on purpose. An
    :class:`~adapters.persistence.storage.Envelope` is one thing a
    caller may put here and was for a time the only one, which is how
    the writer's own documentation came to promise it; the transport
    never required it and must not, or it could refuse a sealed payload
    it merely failed to recognise.

    Integrity is the caller's, not this layer's. No digest is checked
    here -- the header's ``manifest_digest`` is carried, not verified --
    so a caller that needs to know the bytes are the bytes it sealed
    must check that itself.
    """

    __test__: ClassVar[bool] = False

    header: ExportArchiveHeader
    payload_bytes: bytes


#: Largest member this reader will decompress, in bytes.
#:
#: A sealed archive is opened ``r:gz``, so the bytes on disk bound nothing: a
#: small file can expand without limit, and an unbounded ``read()`` on a member
#: turns an operator-supplied archive into a memory-exhaustion surface. The
#: input reaches this function from ``config profile restore``, which takes a
#: path -- an archive can be corrupted, or supplied by someone other than the
#: operator who wrote it.
#:
#: The value is not a guess. The WRITER caps a capsule payload at
#: ``application.user_profile._capsule_archive._MAX_PAYLOAD_BYTES``, so no
#: archive this product produced can carry a larger member, and refusing above
#: that rejects nothing legitimate. The two are held equal by
#: ``test_sealed_archive_member_bound_matches_the_writer_cap``; a bound that
#: silently drifted BELOW the writer's cap would refuse real archives, which is
#: the failure a lone literal here would eventually cause.
_MAX_MEMBER_BYTES: Final[int] = 512 * 1024 * 1024


def _read_member_info(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    """Read one already-discovered regular tar member, bounded.

    Reads one byte past the ceiling rather than trusting ``member.size``: the
    declared size is attacker-controlled tar metadata, so a bound checked
    against it would be checking the claim rather than the bytes.
    """
    extracted = archive.extractfile(member)
    if extracted is None:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: member {member.name!r} is not a regular file",
        )
    with extracted:
        payload = extracted.read(_MAX_MEMBER_BYTES + 1)
    if len(payload) > _MAX_MEMBER_BYTES:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: member {member.name!r} decompresses beyond the "
            f"{_MAX_MEMBER_BYTES}-byte ceiling this format's writer can produce",
        )
    return payload


def _read_member(archive: tarfile.TarFile, expected_name: str) -> bytes:
    """Read one required tar member by name, refusing an absent or empty one.

    The docstring already promised the empty case was refused; the check was
    missing. The payload member carries encrypted material, so zero bytes
    cannot be a legitimate value: an archive with an empty ``payload.envelope``
    is structurally valid, round-trips cleanly, and carries nothing to decrypt.
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


def read_sealed_archive(source_path: Path) -> SealedArchiveContents:
    """Read and strict-validate a sealed bucket-export archive.

    Args:
        source_path: Operator-specified input path.

    Returns:
        A :class:`SealedArchiveContents` carrying the parsed header and
        the encrypted payload bytes.

    Raises:
        SealedArchiveLayoutError: When the tar layout deviates from
            the expected contract (extra / missing / out-of-order /
            unknown members, non-regular members).
        SealedArchiveHeaderError: When ``header.json`` fails strict
            validation as :class:`ExportArchiveHeader`, which includes
            an ``archive_schema_version`` naming any framing other than
            the one this build reads.
        SealedArchivePayloadError: When the payload member cannot be
            read, or when a torn write truncated the gzip stream so the
            decompression layer raises ``EOFError`` / ``gzip.BadGzipFile``.
            Decryption failures surface from this same class when the
            caller's :class:`Envelope` parse fails.

    Truncation-detection scope: a torn write that damages the gzip stream
    (the common case) is caught here at read time and surfaces as
    ``SealedArchivePayloadError``. A *near-complete* truncation that still
    decompresses to the expected two members passes this reader;
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

            payload_bytes = _read_member(archive, PAYLOAD_MEMBER_NAME)
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

    return SealedArchiveContents(header=header, payload_bytes=payload_bytes)


def _validate_layout(member_names: tuple[str, ...]) -> None:
    """Ensure the archive carries exactly the expected members in order.

    The comparison is against the whole canonical tuple rather than a
    per-position check with a permitted tail, because a permitted tail is what
    once let undeclared bytes ride along: an optional third member was allowed
    by NAME while the code deciding whether to read it consulted only the
    header, so a repacked archive carrying material the header did not declare
    read back as valid and the extra member was never examined. With one fixed
    tuple there is no position whose admissibility is decided elsewhere.
    """
    if member_names != SEALED_ARCHIVE_MEMBER_NAMES:
        raise SealedArchiveLayoutError(
            f"sealed-archive read refused: members must be exactly "
            f"{list(SEALED_ARCHIVE_MEMBER_NAMES)!r} in that order, got {list(member_names)!r}",
        )


__all__ = ["SealedArchiveContents", "read_sealed_archive"]
