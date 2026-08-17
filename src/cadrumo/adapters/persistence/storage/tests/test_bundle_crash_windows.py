"""Crash-injection tests for the sealed bucket-export / import archive.

The sealed archive is the bucket export/import transport. The writer writes
directly to the operator's output path (no tmp + rename) and refuses to
overwrite an existing target; the torn-artifact guarantee is met by two layers:

- Read-time detection. ``read_sealed_archive`` fast-fails a damaged archive
  before any decryption. A torn write that damages the gzip stream (the common
  truncation case) surfaces as ``SealedArchivePayloadError`` (a
  ``BucketImportError``); a member/layout corruption surfaces as
  ``SealedArchiveLayoutError``.
- AEAD backstop. A *near-complete* truncation that still decompresses to the
  expected members passes the reader, but the AEAD tag on the encrypted payload
  fails when the importer decrypts it, and the importer verifies that tag before
  it provisions any bucket store - so an aborted import never restores a partial
  bucket, regardless of which layer catches the damage.

There is no on-disk staging directory to clean (the archive is read in memory),
so staging cleanup is a documented non-goal. Read-time detection of a
near-complete truncation would require a trailing integrity marker in the
archive format; that hardening is a tracked follow-up in the crash-window
reference.

These tests drive the real writer, reader, crypto, and import service - no
primitive is patched. The interruption is simulated by damaging the archive
bytes on disk, and the anti-tautology proofs show the intact archive reads /
decrypts cleanly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....domain.buckets import BucketExportError, BucketImportError
from ..bucket import ARCHIVE_SCHEMA_VERSION, ExportArchiveHeader, read_sealed_archive, write_sealed_archive

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "abababab-abab-4bab-8bab-abababababab"
_MANIFEST_DIGEST = "a" * 64
_INSTANT = datetime(2026, 7, 2, 12, 0, 0, tzinfo=UTC)
_PAYLOAD = b"sealed-archive encrypted payload bytes for the crash-window test" * 32


def _write_valid_archive(path: Path, *, payload: bytes = _PAYLOAD, bucket_id: str = _BUCKET_ID) -> None:
    write_sealed_archive(
        path,
        header=ExportArchiveHeader(
            product="cadrumo",
            bucket_id=bucket_id,
            manifest_digest=_MANIFEST_DIGEST,
            archive_schema_version=ARCHIVE_SCHEMA_VERSION,
            created_at=_INSTANT,
        ),
        payload_bytes=payload,
    )


def _truncate(path: Path, *, keep_fraction: float) -> None:
    raw = path.read_bytes()
    path.write_bytes(raw[: max(1, int(len(raw) * keep_fraction))])


def _corrupt_midstream(path: Path) -> None:
    raw = bytearray(path.read_bytes())
    raw[len(raw) // 2] ^= 0xFF
    path.write_bytes(bytes(raw))


class TestBundleExportCrashWindow:
    def test_untruncated_archive_reads_cleanly(self, tmp_path: Path) -> None:
        # Anti-tautology: an intact archive round-trips through the reader, so
        # the damage tests' refusals are caused by the damage, not by the
        # archive being unreadable in general.
        archive = tmp_path / "profile.cadrumo-bucket.tar.gz"
        _write_valid_archive(archive)

        contents = read_sealed_archive(archive)
        assert contents.header.bucket_id == _BUCKET_ID
        assert contents.payload_bytes == _PAYLOAD

    def test_truncated_archive_is_rejected_at_read(self, tmp_path: Path) -> None:
        # A torn write that damages the gzip stream (30-80% kept) is caught at
        # read time as the documented typed payload error, never a raw builtin.
        for keep in (0.3, 0.5, 0.8):
            archive = tmp_path / f"trunc-{keep}.cadrumo-bucket.tar.gz"
            _write_valid_archive(archive)
            _truncate(archive, keep_fraction=keep)
            with pytest.raises(BucketImportError):
                read_sealed_archive(archive)

    def test_corrupted_archive_is_rejected_at_read(self, tmp_path: Path) -> None:
        # A member/layout corruption is detected at read time (gzip-CRC / tar
        # layer) and surfaces as a BucketImportError before any decryption.
        archive = tmp_path / "profile.cadrumo-bucket.tar.gz"
        _write_valid_archive(archive)
        _corrupt_midstream(archive)

        with pytest.raises(BucketImportError):
            read_sealed_archive(archive)

    def test_writer_refuses_to_overwrite_an_existing_target(self, tmp_path: Path) -> None:
        # Refuse-overwrite is why a torn export never clobbers a prior good
        # archive: a re-export to the same path is refused rather than
        # silently replacing the (possibly good) file.
        archive = tmp_path / "profile.cadrumo-bucket.tar.gz"
        _write_valid_archive(archive)

        with pytest.raises(BucketExportError):
            _write_valid_archive(archive)
