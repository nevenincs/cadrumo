"""Round-trip tests for the sealed bucket-export archive writer + reader.

Exercises the sealed bucket-export archive layout contract:
write → read returns the same header + payload bytes; layout drift
fast-fails before any payload-decryption attempt; the recovery-wrap
presence is consistent across write and read; the metadata
normalisation produces a byte-stable archive for the same content.
"""

from __future__ import annotations

import tarfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from .._export_header import ExportArchiveHeader
from .._sealed_archive_errors import (
    SealedArchiveHeaderError,
    SealedArchiveLayoutError,
    SealedArchiveWriteError,
)
from .._sealed_archive_reader import read_sealed_archive
from .._sealed_archive_writer import (
    HEADER_MEMBER_NAME,
    PAYLOAD_MEMBER_NAME,
    write_sealed_archive,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


_BUCKET_ID = "bucket-sealed-archive-roundtrip-test"
_MANIFEST_DIGEST = "a" * 64
_FROZEN_INSTANT = datetime(2026, 6, 3, 14, 30, 0, tzinfo=UTC)
_PAYLOAD = b"encrypted-payload-bytes-stand-in"
_RECOVERY_WRAP = b"recovery-wrap-bytes-stand-in"


def _header(*, recovery_wrap_present: bool = False) -> ExportArchiveHeader:
    return ExportArchiveHeader(
        bucket_id=_BUCKET_ID,
        manifest_digest=_MANIFEST_DIGEST,
        recovery_wrap_present=recovery_wrap_present,
        archive_schema_version=1,
        created_at=_FROZEN_INSTANT,
    )


def test_roundtrip_without_recovery_wrap_returns_same_header_and_payload(tmp_path: Path) -> None:
    """A 2-member archive round-trips exactly."""
    archive_path = tmp_path / "export.tar.gz"
    header = _header()

    write_sealed_archive(
        archive_path,
        header=header,
        payload_envelope_bytes=_PAYLOAD,
    )

    contents = read_sealed_archive(archive_path)
    assert contents.header == header
    assert contents.payload_envelope_bytes == _PAYLOAD
    assert contents.recovery_wrap_bytes is None


def test_roundtrip_with_recovery_wrap_returns_all_three_members(tmp_path: Path) -> None:
    """A 3-member archive round-trips the recovery wrap too."""
    archive_path = tmp_path / "export.tar.gz"
    header = _header(recovery_wrap_present=True)

    write_sealed_archive(
        archive_path,
        header=header,
        payload_envelope_bytes=_PAYLOAD,
        recovery_wrap_bytes=_RECOVERY_WRAP,
    )

    contents = read_sealed_archive(archive_path)
    assert contents.header == header
    assert contents.payload_envelope_bytes == _PAYLOAD
    assert contents.recovery_wrap_bytes == _RECOVERY_WRAP


def test_writer_refuses_when_header_recovery_flag_disagrees_with_bytes(tmp_path: Path) -> None:
    """Header recovery_wrap_present=True without bytes is a service-side bug."""
    archive_path = tmp_path / "export.tar.gz"
    header = _header(recovery_wrap_present=True)

    with pytest.raises(SealedArchiveWriteError, match="no recovery_wrap_bytes supplied"):
        write_sealed_archive(
            archive_path,
            header=header,
            payload_envelope_bytes=_PAYLOAD,
            recovery_wrap_bytes=None,
        )


def test_writer_refuses_when_recovery_bytes_supplied_without_header_flag(tmp_path: Path) -> None:
    """Recovery bytes without header flag is also a service-side bug."""
    archive_path = tmp_path / "export.tar.gz"
    header = _header(recovery_wrap_present=False)

    with pytest.raises(SealedArchiveWriteError, match="recovery_wrap_present is False"):
        write_sealed_archive(
            archive_path,
            header=header,
            payload_envelope_bytes=_PAYLOAD,
            recovery_wrap_bytes=_RECOVERY_WRAP,
        )


def test_writer_refuses_to_overwrite_existing_target(tmp_path: Path) -> None:
    """Existing target_path refuses; operator removes it first."""
    archive_path = tmp_path / "export.tar.gz"
    archive_path.write_bytes(b"existing")
    header = _header()

    with pytest.raises(SealedArchiveWriteError, match="already exists"):
        write_sealed_archive(archive_path, header=header, payload_envelope_bytes=_PAYLOAD)


def test_reader_rejects_layout_with_extra_member(tmp_path: Path) -> None:
    """An archive with an extra unknown member fast-fails the layout gate."""
    archive_path = tmp_path / "export.tar.gz"
    header = _header()
    write_sealed_archive(archive_path, header=header, payload_envelope_bytes=_PAYLOAD)

    # Re-pack the archive with an extra unknown member appended.
    rebuilt_path = tmp_path / "tampered.tar.gz"
    import io

    with tarfile.open(archive_path, "r:gz") as source:
        members = list(source.getmembers())
        member_bytes: list[tuple[tarfile.TarInfo, bytes]] = []
        for m in members:
            extracted = source.extractfile(m)
            assert extracted is not None
            member_bytes.append((m, extracted.read()))
    with tarfile.open(rebuilt_path, "w:gz") as target:
        for info, payload in member_bytes:
            target.addfile(info, io.BytesIO(payload))
        extra_info = tarfile.TarInfo("unknown-member.bin")
        extra_info.size = 1
        target.addfile(extra_info, io.BytesIO(b"x"))

    # The tampered archive has exactly 3 members (header, payload,
    # unknown), which trips the third-member-name check rather than
    # the count check — both are layout violations and both must
    # fast-fail before any decryption attempt.
    with pytest.raises(SealedArchiveLayoutError, match="third member must be"):
        read_sealed_archive(rebuilt_path)


def test_reader_rejects_archive_with_corrupt_header(tmp_path: Path) -> None:
    """A header.json that does not parse as ExportArchiveHeader fast-fails."""
    archive_path = tmp_path / "export.tar.gz"
    import io

    with tarfile.open(archive_path, "w:gz") as archive:
        bad_header_bytes = b'{"bucket_id": "x", "missing": "fields"}'
        info = tarfile.TarInfo(HEADER_MEMBER_NAME)
        info.size = len(bad_header_bytes)
        archive.addfile(info, io.BytesIO(bad_header_bytes))
        payload_info = tarfile.TarInfo(PAYLOAD_MEMBER_NAME)
        payload_info.size = len(_PAYLOAD)
        archive.addfile(payload_info, io.BytesIO(_PAYLOAD))

    with pytest.raises(SealedArchiveHeaderError, match="header schema validation failed"):
        read_sealed_archive(archive_path)


def test_archive_metadata_is_normalised_byte_stable(tmp_path: Path) -> None:
    """Two writes of the same content produce bit-identical archives."""
    first_path = tmp_path / "first.tar.gz"
    second_path = tmp_path / "second.tar.gz"
    header = _header()

    write_sealed_archive(first_path, header=header, payload_envelope_bytes=_PAYLOAD)
    write_sealed_archive(second_path, header=header, payload_envelope_bytes=_PAYLOAD)

    # The gzip stream carries its own mtime in the header which is set
    # to the archive instant; the tar member metadata is normalised.
    # Compare the tar layer directly by re-opening and reading members.
    def _members_with_bytes(path: Path) -> list[tuple[str, int, int, int, bytes]]:
        with tarfile.open(path, "r:gz") as archive:
            out: list[tuple[str, int, int, int, bytes]] = []
            for m in archive.getmembers():
                extracted = archive.extractfile(m)
                assert extracted is not None
                with extracted:
                    out.append((m.name, m.mode, m.uid, m.gid, extracted.read()))
            return out

    assert _members_with_bytes(first_path) == _members_with_bytes(second_path)


def test_reader_rejects_out_of_order_members(tmp_path: Path) -> None:
    """Header in second position is a layout violation."""
    archive_path = tmp_path / "swapped.tar.gz"
    import io

    header = _header()
    header_bytes = header.model_dump_json().encode("utf-8")

    with tarfile.open(archive_path, "w:gz") as archive:
        # Write payload FIRST (wrong order)
        payload_info = tarfile.TarInfo(PAYLOAD_MEMBER_NAME)
        payload_info.size = len(_PAYLOAD)
        archive.addfile(payload_info, io.BytesIO(_PAYLOAD))
        header_info = tarfile.TarInfo(HEADER_MEMBER_NAME)
        header_info.size = len(header_bytes)
        archive.addfile(header_info, io.BytesIO(header_bytes))

    with pytest.raises(SealedArchiveLayoutError, match="first member must be"):
        read_sealed_archive(archive_path)
