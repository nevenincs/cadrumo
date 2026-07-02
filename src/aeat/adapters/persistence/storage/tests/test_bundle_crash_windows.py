"""Crash-injection tests for the sealed bucket-export / import archive.

The sealed archive is the bucket export/import transport. The writer writes
directly to the operator's output path (no tmp + rename) and refuses to
overwrite an existing target; the torn-artifact guarantee is meant to be met by
READ-TIME detection: the reader fast-fails a damaged archive before any
decryption, and the import service reads + validates the whole archive in memory
before it provisions any bucket store, so an aborted import is invisible to the
manifest pointer (no partial bucket is ever materialised). There is no on-disk
staging directory to clean, so staging cleanup is a documented non-goal.

These tests drive the real writer, reader, and import service - no primitive is
patched. The interruption is simulated by damaging the archive bytes on disk,
and the anti-tautology proof shows the intact archive reads / imports cleanly.

Reader gap (reported, not fixed here per the campaign scope boundary): a
*truncated* gzip archive (the exact torn-write shape) is NOT reliably rejected
by ``read_sealed_archive`` today - a mid-file truncation leaks a raw
``EOFError`` and a near-complete truncation is silently accepted, because the
reader catches only ``tarfile.TarError`` / ``OSError``. These tests therefore
pin the detection that DOES hold at HEAD - layout / member corruption rejection,
refuse-overwrite, and the import service refusing a damaged archive before
provisioning any bucket - and do not assert the truncation case, which is
tracked as a production hardening follow-up.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....domain.buckets import BucketExportError, BucketImportError
from .....tests.secure_sql import isolated_profile_storage_root
from .. import BUCKETS_DIRNAME
from ..bucket._export_header import ExportArchiveHeader
from ..bucket._sealed_archive_reader import read_sealed_archive
from ..bucket._sealed_archive_writer import write_sealed_archive

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "abababab-abab-4bab-8bab-abababababab"
_MANIFEST_DIGEST = "a" * 64
_INSTANT = datetime(2026, 7, 2, 12, 0, 0, tzinfo=UTC)
_PAYLOAD = b"sealed-archive encrypted payload bytes for the crash-window test" * 32


def _write_valid_archive(path: Path) -> None:
    write_sealed_archive(
        path,
        header=ExportArchiveHeader(
            bucket_id=_BUCKET_ID,
            manifest_digest=_MANIFEST_DIGEST,
            recovery_wrap_present=False,
            archive_schema_version=2,
            created_at=_INSTANT,
        ),
        payload_envelope_bytes=_PAYLOAD,
    )


def _corrupt_midstream(path: Path) -> None:
    """Flip a byte in the middle of the archive to simulate a damaged write.

    A mid-stream bit flip fails the gzip CRC / tar layer, which the reader
    catches and re-raises as a ``BucketImportError`` subclass - the detection
    guarantee this test pins.
    """
    raw = bytearray(path.read_bytes())
    raw[len(raw) // 2] ^= 0xFF
    path.write_bytes(bytes(raw))


class TestBundleExportCrashWindow:
    def test_untruncated_archive_reads_cleanly(self, tmp_path: Path) -> None:
        # Anti-tautology: an intact archive round-trips through the reader, so
        # the corruption test's refusal is caused by the damage, not by the
        # archive being unreadable in general.
        archive = tmp_path / "profile.aeat-bucket.tar.gz"
        _write_valid_archive(archive)

        contents = read_sealed_archive(archive)
        assert contents.header.bucket_id == _BUCKET_ID
        assert contents.payload_envelope_bytes == _PAYLOAD

    def test_damaged_archive_is_rejected_by_the_reader(self, tmp_path: Path) -> None:
        # A damaged archive is detected at read time (positional / gzip-CRC
        # layer) and surfaces as a BucketImportError before any decryption.
        archive = tmp_path / "profile.aeat-bucket.tar.gz"
        _write_valid_archive(archive)
        _corrupt_midstream(archive)

        with pytest.raises(BucketImportError):
            read_sealed_archive(archive)

    def test_writer_refuses_to_overwrite_an_existing_target(self, tmp_path: Path) -> None:
        # Refuse-overwrite is why a torn export never clobbers a prior good
        # archive: a re-export to the same path is refused rather than
        # silently replacing the (possibly good) file.
        archive = tmp_path / "profile.aeat-bucket.tar.gz"
        _write_valid_archive(archive)

        with pytest.raises(BucketExportError):
            _write_valid_archive(archive)


class TestBundleImportCrashWindow:
    @pytest.fixture
    def backend(self, tmp_path: Path) -> Iterator[Path]:
        with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
            yield storage_root

    def test_damaged_import_provisions_no_bucket(self, backend: Path, tmp_path: Path) -> None:
        # The import service reads + validates the whole archive before writing
        # any bucket store, so an aborted / damaged import is invisible to the
        # manifest pointer: no partial bucket is provisioned. There is no
        # on-disk staging directory (the archive is read in memory), so staging
        # cleanup is a documented non-goal.
        from .....application.bucket_maintenance._contracts import ImportBucketCommand
        from .....application.bucket_maintenance._service import BucketMaintenanceService
        from .....application.workflow._profile_bucket_scan import read_profile_bucket_by_id

        archive = tmp_path / "import-source.aeat-bucket.tar.gz"
        _write_valid_archive(archive)
        _corrupt_midstream(archive)

        with pytest.raises(BucketImportError):
            BucketMaintenanceService().import_(ImportBucketCommand(source_path=archive))

        # No bucket was provisioned for the header's id — the aborted import
        # left no manifest pointer behind.
        assert read_profile_bucket_by_id(_BUCKET_ID) is None
        buckets_root = backend / BUCKETS_DIRNAME
        assert not buckets_root.exists() or not any(buckets_root.iterdir()), (
            "a damaged import materialised a bucket directory"
        )
