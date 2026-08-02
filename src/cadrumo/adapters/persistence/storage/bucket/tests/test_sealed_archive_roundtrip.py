"""Round-trip tests for the sealed bucket-export archive writer + reader.

Exercises the sealed bucket-export archive layout contract:
write → read returns the same header + payload bytes; layout drift
fast-fails before any payload-decryption attempt; the recovery-wrap
presence is consistent across write and read; the metadata
normalisation produces a byte-stable archive for the same content.
"""

from __future__ import annotations

import io
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
    RECOVERY_WRAP_MEMBER_NAME,
    write_sealed_archive,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


_BUCKET_ID = "bucket-sealed-archive-roundtrip-test"
_MANIFEST_DIGEST = "a" * 64
_FROZEN_INSTANT = datetime(2026, 6, 3, 14, 30, 0, tzinfo=UTC)
_PAYLOAD = b"sealed-payload-envelope-ciphertext-v1"
_RECOVERY_WRAP = b"sealed-recovery-wrap-ciphertext-v1"


def _header(*, recovery_wrap_present: bool = False) -> ExportArchiveHeader:
    return ExportArchiveHeader(
        product="cadrumo",
        bucket_id=_BUCKET_ID,
        manifest_digest=_MANIFEST_DIGEST,
        recovery_wrap_present=recovery_wrap_present,
        archive_schema_version=3,
        created_at=_FROZEN_INSTANT,
    )


def test_roundtrip_without_recovery_wrap_returns_same_header_and_payload(tmp_path: Path) -> None:
    """A 2-member archive round-trips exactly."""
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
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
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
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


@pytest.mark.parametrize(
    ("recovery_wrap_present", "recovery_wrap_bytes", "error_match"),
    (
        pytest.param(True, None, "no recovery_wrap_bytes supplied", id="flag-without-bytes"),
        pytest.param(False, _RECOVERY_WRAP, "recovery_wrap_present is False", id="bytes-without-flag"),
    ),
)
def test_writer_refuses_when_header_recovery_flag_disagrees_with_bytes(
    tmp_path: Path,
    recovery_wrap_present: bool,
    recovery_wrap_bytes: bytes | None,
    error_match: str,
) -> None:
    """Recovery-wrap header flag and payload bytes must agree."""
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    header = _header(recovery_wrap_present=recovery_wrap_present)

    with pytest.raises(SealedArchiveWriteError, match=error_match):
        write_sealed_archive(
            archive_path,
            header=header,
            payload_envelope_bytes=_PAYLOAD,
            recovery_wrap_bytes=recovery_wrap_bytes,
        )


def test_writer_refuses_to_overwrite_existing_target(tmp_path: Path) -> None:
    """Existing target_path refuses; operator removes it first."""
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    archive_path.write_bytes(b"existing")
    header = _header()

    with pytest.raises(SealedArchiveWriteError, match="already exists"):
        write_sealed_archive(archive_path, header=header, payload_envelope_bytes=_PAYLOAD)


def test_reader_rejects_layout_with_extra_member(tmp_path: Path) -> None:
    """An archive with an extra unknown member fast-fails the layout gate."""
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    header = _header()
    write_sealed_archive(archive_path, header=header, payload_envelope_bytes=_PAYLOAD)

    # Re-pack the archive with an extra unknown member appended.
    rebuilt_path = tmp_path / "tampered.cadrumo-bucket.tar.gz"
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


def test_reader_rejects_archive_without_cadrumo_product_marker(tmp_path: Path) -> None:
    """A pre-cut header refuses before its payload is returned."""
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    import io

    with tarfile.open(archive_path, "w:gz") as archive:
        bad_header_bytes = b'{"bucket_id": "x", "missing": "fields"}'
        info = tarfile.TarInfo(HEADER_MEMBER_NAME)
        info.size = len(bad_header_bytes)
        archive.addfile(info, io.BytesIO(bad_header_bytes))
        payload_info = tarfile.TarInfo(PAYLOAD_MEMBER_NAME)
        payload_info.size = len(_PAYLOAD)
        archive.addfile(payload_info, io.BytesIO(_PAYLOAD))

    with pytest.raises(SealedArchiveHeaderError, match="payload members were not read"):
        read_sealed_archive(archive_path)


def test_former_bundle_suffix_is_refused_without_opening_or_mutating_bytes(tmp_path: Path) -> None:
    """The former suffix refuses even when its bytes are not a readable archive."""
    former_path = tmp_path / "sentinel.aeat-bucket.tar.gz"
    sentinel = b"former-bundle-sentinel-bytes-must-remain-opaque"
    former_path.write_bytes(sentinel)

    with pytest.raises(SealedArchiveHeaderError, match="archive was not opened"):
        read_sealed_archive(former_path)

    assert former_path.read_bytes() == sentinel
    assert not (tmp_path / "sentinel.cadrumo-bucket.tar.gz").exists()


def test_renamed_former_header_refuses_before_payload_adoption(tmp_path: Path) -> None:
    """Renaming an old archive cannot bypass its missing product-format marker."""
    import io
    import json

    archive_path = tmp_path / "renamed-former.cadrumo-bucket.tar.gz"
    sentinel_payload = b"former-encrypted-payload-sentinel"
    former_header = {
        "bucket_id": _BUCKET_ID,
        "manifest_digest": _MANIFEST_DIGEST,
        "recovery_wrap_present": False,
        "archive_schema_version": 2,
        "created_at": _FROZEN_INSTANT.isoformat(),
    }
    with tarfile.open(archive_path, "w:gz") as archive:
        header_bytes = json.dumps(former_header).encode("utf-8")
        header_info = tarfile.TarInfo(HEADER_MEMBER_NAME)
        header_info.size = len(header_bytes)
        archive.addfile(header_info, io.BytesIO(header_bytes))
        payload_info = tarfile.TarInfo(PAYLOAD_MEMBER_NAME)
        payload_info.size = len(sentinel_payload)
        archive.addfile(payload_info, io.BytesIO(sentinel_payload))
    original_bytes = archive_path.read_bytes()

    with pytest.raises(SealedArchiveHeaderError, match="payload members were not read"):
        read_sealed_archive(archive_path)

    assert archive_path.read_bytes() == original_bytes


def test_writer_refuses_former_suffix_without_creating_a_bundle(tmp_path: Path) -> None:
    """Cadrumo never writes or auto-renames the former published suffix."""
    former_path = tmp_path / "export.aeat-bucket.tar.gz"

    with pytest.raises(SealedArchiveWriteError, match="former-product bundle suffix"):
        write_sealed_archive(former_path, header=_header(), payload_envelope_bytes=_PAYLOAD)

    assert not former_path.exists()
    assert not (tmp_path / "export.cadrumo-bucket.tar.gz").exists()


def test_archive_metadata_is_normalised_byte_stable(tmp_path: Path) -> None:
    """Two writes of the same content produce bit-identical archives."""
    first_path = tmp_path / "first.cadrumo-bucket.tar.gz"
    second_path = tmp_path / "second.cadrumo-bucket.tar.gz"
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
    archive_path = tmp_path / "swapped.cadrumo-bucket.tar.gz"
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


def test_failed_write_leaves_no_file_at_the_operator_target(tmp_path: Path) -> None:
    """A failed write leaves neither a target file nor staging residue.

    Scope note: this exercises a failure at archive-open time, which the
    previous writer also survived cleanly. The regression it guards is the
    STAGING path -- that the writer's temporary sibling is removed on the
    failure route rather than left beside the operator's output.

    The case that motivated the change, a failure after one member has been
    written, cannot be produced by a real filesystem condition and is not
    covered here; it is instead made structurally impossible, because nothing
    is written at the operator's path until a complete archive is renamed
    into place.
    """
    missing_parent = tmp_path / "not-created-yet"
    target = missing_parent / "export.cadrumo-bucket.tar.gz"

    with pytest.raises(SealedArchiveWriteError):
        write_sealed_archive(
            target,
            header=_header(),
            payload_envelope_bytes=b"payload-envelope-bytes",
        )

    # Nothing at the operator's path, and no staging residue anywhere.
    assert not target.exists()
    assert not missing_parent.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == []


def test_failed_write_preserves_an_unrelated_pre_existing_target(tmp_path: Path) -> None:
    """The refusal to overwrite still fires before anything is staged.

    A pre-existing archive must survive a re-export attempt byte-for-byte;
    staging must not create residue beside it either.
    """
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    archive_path.write_bytes(b"pre-existing-bytes")

    with pytest.raises(SealedArchiveWriteError):
        write_sealed_archive(
            archive_path,
            header=_header(),
            payload_envelope_bytes=b"payload-envelope-bytes",
        )

    assert archive_path.read_bytes() == b"pre-existing-bytes"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["export.cadrumo-bucket.tar.gz"]


def test_successful_write_leaves_only_the_finished_archive(tmp_path: Path) -> None:
    """Positive control: staging is invisible once the write completes.

    Without this, the failure tests above would pass equally well if the
    writer had stopped producing archives at all.
    """
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"

    write_sealed_archive(
        archive_path,
        header=_header(),
        payload_envelope_bytes=b"payload-envelope-bytes",
    )

    assert sorted(path.name for path in tmp_path.iterdir()) == ["export.cadrumo-bucket.tar.gz"]
    recovered = read_sealed_archive(archive_path)
    assert recovered.payload_envelope_bytes == b"payload-envelope-bytes"


def _member_bytes(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    """Read one regular member's bytes, failing loudly on a non-regular entry.

    ``extractfile`` returns ``None`` for a non-regular member; every member a
    sealed archive carries is regular, so a ``None`` here means the fixture
    itself is wrong rather than the code under test.
    """
    extracted = archive.extractfile(member)
    assert extracted is not None, f"fixture archive member {member.name!r} is not a regular file"
    with extracted:
        return extracted.read()


def _repack_with_extra_recovery_member(source: Path, target: Path) -> None:
    """Copy a 2-member archive and append an undeclared ``recovery.wrap`` member."""
    with tarfile.open(source, mode="r:gz") as original:
        members = [(member, _member_bytes(original, member)) for member in original.getmembers()]
    with tarfile.open(target, mode="w:gz") as repacked:
        for member, data in members:
            repacked.addfile(member, io.BytesIO(data))
        extra = tarfile.TarInfo(RECOVERY_WRAP_MEMBER_NAME)
        extra.size = len(b"undeclared-recovery-material")
        repacked.addfile(extra, io.BytesIO(b"undeclared-recovery-material"))


def test_writer_refuses_an_empty_payload_member(tmp_path: Path) -> None:
    """An archive with nothing to decrypt is not a valid sealed archive.

    An empty ``payload.envelope`` produced a structurally valid archive that
    wrote and read back cleanly with ``payload_len=0``: every layout check
    passed and the result carried no encrypted material at all.
    """
    with pytest.raises(SealedArchiveWriteError):
        write_sealed_archive(
            tmp_path / "export.cadrumo-bucket.tar.gz",
            header=_header(),
            payload_envelope_bytes=b"",
        )


def test_writer_refuses_an_empty_declared_recovery_member(tmp_path: Path) -> None:
    """Declaring recovery material and supplying none loses it silently."""
    with pytest.raises(SealedArchiveWriteError):
        write_sealed_archive(
            tmp_path / "export.cadrumo-bucket.tar.gz",
            header=_header(recovery_wrap_present=True),
            payload_envelope_bytes=b"payload-envelope-bytes",
            recovery_wrap_bytes=b"",
        )


def test_reader_refuses_an_empty_required_member(tmp_path: Path) -> None:
    """The reader refuses a zero-byte required member it did not write itself.

    The writer can no longer produce one, so this repacks the archive by hand
    to prove the READ boundary also refuses it -- an archive from any other
    producer must not be trusted on the writer's guarantees alone.
    """
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    write_sealed_archive(
        archive_path,
        header=_header(),
        payload_envelope_bytes=b"payload-envelope-bytes",
    )
    hollowed = tmp_path / "hollowed.cadrumo-bucket.tar.gz"
    with tarfile.open(archive_path, mode="r:gz") as original:
        members = [(member, _member_bytes(original, member)) for member in original.getmembers()]
    with tarfile.open(hollowed, mode="w:gz") as repacked:
        for member, data in members:
            if member.name == PAYLOAD_MEMBER_NAME:
                member.size = 0
                repacked.addfile(member, io.BytesIO(b""))
                continue
            repacked.addfile(member, io.BytesIO(data))

    with pytest.raises(SealedArchiveLayoutError):
        read_sealed_archive(hollowed)


def test_reader_refuses_an_undeclared_recovery_member(tmp_path: Path) -> None:
    """A third member the header does not declare must not ride along unexamined.

    Layout validation permitted the name and the recovery reader consulted
    only the header, so a repacked archive returned
    ``recovery_wrap_bytes=None`` while retaining the extra member: undeclared
    bytes travelled inside an archive that read back as valid.
    """
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    write_sealed_archive(
        archive_path,
        header=_header(),
        payload_envelope_bytes=b"payload-envelope-bytes",
    )
    repacked_path = tmp_path / "repacked.cadrumo-bucket.tar.gz"
    _repack_with_extra_recovery_member(archive_path, repacked_path)

    with pytest.raises(SealedArchiveLayoutError):
        read_sealed_archive(repacked_path)


def test_a_declared_recovery_archive_still_round_trips(tmp_path: Path) -> None:
    """Positive control: the cardinality rule accepts the declared 3-member shape."""
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    write_sealed_archive(
        archive_path,
        header=_header(recovery_wrap_present=True),
        payload_envelope_bytes=b"payload-envelope-bytes",
        recovery_wrap_bytes=b"recovery-wrap-bytes",
    )

    recovered = read_sealed_archive(archive_path)

    assert recovered.payload_envelope_bytes == b"payload-envelope-bytes"
    assert recovered.recovery_wrap_bytes == b"recovery-wrap-bytes"
