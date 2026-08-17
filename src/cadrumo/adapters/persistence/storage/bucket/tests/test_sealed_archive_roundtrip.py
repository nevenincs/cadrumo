"""Round-trip tests for the sealed bucket-export archive writer + reader.

Exercises the sealed bucket-export archive layout contract:
write → read returns the same header + payload bytes; the member set is
the one fixed pair and any other shape fast-fails before any
payload-decryption attempt; a header naming any other archive framing is
refused rather than parsed; and the metadata normalisation produces a
byte-stable archive for the same content.
"""

from __future__ import annotations

import io
import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......core import scan_directory
from .._export_header import ARCHIVE_SCHEMA_VERSION, ExportArchiveHeader
from .._sealed_archive_errors import (
    SealedArchiveHeaderError,
    SealedArchiveLayoutError,
    SealedArchiveWriteError,
)
from .._sealed_archive_reader import read_sealed_archive
from .._sealed_archive_writer import (
    HEADER_MEMBER_NAME,
    PAYLOAD_MEMBER_NAME,
    SEALED_ARCHIVE_MEMBER_NAMES,
    write_sealed_archive,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


_BUCKET_ID = "bucket-sealed-archive-roundtrip-test"
_MANIFEST_DIGEST = "a" * 64
_FROZEN_INSTANT = datetime(2026, 6, 3, 14, 30, 0, tzinfo=UTC)
_PAYLOAD = b"sealed-payload-envelope-ciphertext-v1"


def _header() -> ExportArchiveHeader:
    return ExportArchiveHeader(
        product="cadrumo",
        bucket_id=_BUCKET_ID,
        manifest_digest=_MANIFEST_DIGEST,
        archive_schema_version=ARCHIVE_SCHEMA_VERSION,
        created_at=_FROZEN_INSTANT,
    )


def _write_raw_archive(path: Path, *, header_bytes: bytes, payload_bytes: bytes = _PAYLOAD) -> None:
    """Build a canonically-shaped archive around caller-supplied header bytes.

    The writer refuses everything these fixtures exist to present to the
    reader, so the tar is assembled directly. The member names and order stay
    canonical: each fixture must fail on the one property it is probing rather
    than on an incidental layout violation.
    """
    with tarfile.open(path, mode="w:gz") as archive:
        header_info = tarfile.TarInfo(HEADER_MEMBER_NAME)
        header_info.size = len(header_bytes)
        archive.addfile(header_info, io.BytesIO(header_bytes))
        payload_info = tarfile.TarInfo(PAYLOAD_MEMBER_NAME)
        payload_info.size = len(payload_bytes)
        archive.addfile(payload_info, io.BytesIO(payload_bytes))


def test_roundtrip_returns_the_same_header_and_payload(tmp_path: Path) -> None:
    """The archive round-trips its header and payload with strict equality."""
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    header = _header()

    write_sealed_archive(
        archive_path,
        header=header,
        payload_bytes=_PAYLOAD,
    )

    contents = read_sealed_archive(archive_path)
    assert contents.header == header
    assert contents.payload_bytes == _PAYLOAD


def test_written_archive_carries_exactly_the_canonical_members(tmp_path: Path) -> None:
    """No optional member exists, so the shape is a constant on disk."""
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"

    write_sealed_archive(archive_path, header=_header(), payload_bytes=_PAYLOAD)

    with tarfile.open(archive_path, mode="r:gz") as archive:
        assert tuple(member.name for member in archive.getmembers()) == SEALED_ARCHIVE_MEMBER_NAMES


def test_writer_refuses_to_overwrite_existing_target(tmp_path: Path) -> None:
    """Existing target_path refuses; operator removes it first."""
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    archive_path.write_bytes(b"existing")
    header = _header()

    with pytest.raises(SealedArchiveWriteError, match="already exists"):
        write_sealed_archive(archive_path, header=header, payload_bytes=_PAYLOAD)


def test_reader_rejects_layout_with_extra_member(tmp_path: Path) -> None:
    """An archive with an extra unknown member fast-fails the layout gate."""
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    header = _header()
    write_sealed_archive(archive_path, header=header, payload_bytes=_PAYLOAD)

    # Re-pack the archive with an extra unknown member appended.
    rebuilt_path = tmp_path / "tampered.cadrumo-bucket.tar.gz"
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

    with pytest.raises(SealedArchiveLayoutError, match="members must be exactly"):
        read_sealed_archive(rebuilt_path)


def test_reader_rejects_archive_without_cadrumo_product_marker(tmp_path: Path) -> None:
    """A pre-cut header refuses before its payload is returned."""
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    _write_raw_archive(archive_path, header_bytes=b'{"bucket_id": "x", "missing": "fields"}')

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
    archive_path = tmp_path / "renamed-former.cadrumo-bucket.tar.gz"
    former_header = {
        "bucket_id": _BUCKET_ID,
        "manifest_digest": _MANIFEST_DIGEST,
        "recovery_wrap_present": False,
        "archive_schema_version": 2,
        "created_at": _FROZEN_INSTANT.isoformat(),
    }
    _write_raw_archive(archive_path, header_bytes=json.dumps(former_header).encode("utf-8"))
    original_bytes = archive_path.read_bytes()

    with pytest.raises(SealedArchiveHeaderError, match="payload members were not read"):
        read_sealed_archive(archive_path)

    assert archive_path.read_bytes() == original_bytes


@pytest.mark.parametrize(
    "declared_version",
    (ARCHIVE_SCHEMA_VERSION - 1, ARCHIVE_SCHEMA_VERSION + 1),
    ids=("superseded-framing", "unwritten-framing"),
)
def test_reader_refuses_a_header_naming_another_archive_framing(tmp_path: Path, declared_version: int) -> None:
    """A header declaring any other framing is refused, never parsed.

    The refusal is symmetric on purpose. A lower version names a framing whose
    members and header fields are not these, so reading it would mean applying
    this contract to bytes that never satisfied it; a higher one names a
    framing this build has never produced. Neither is a shape to tolerate, and
    the payload member is not reached in either case.
    """
    archive_path = tmp_path / "other-framing.cadrumo-bucket.tar.gz"
    header_payload = json.loads(_header().model_dump_json())
    header_payload["archive_schema_version"] = declared_version
    _write_raw_archive(archive_path, header_bytes=json.dumps(header_payload).encode("utf-8"))

    with pytest.raises(SealedArchiveHeaderError, match="archive_schema_version"):
        read_sealed_archive(archive_path)


def test_writer_cannot_be_handed_a_header_naming_another_framing() -> None:
    """The refusal binds the write side too, at header construction."""
    with pytest.raises(ValueError, match="archive_schema_version must be"):
        ExportArchiveHeader(
            product="cadrumo",
            bucket_id=_BUCKET_ID,
            manifest_digest=_MANIFEST_DIGEST,
            archive_schema_version=ARCHIVE_SCHEMA_VERSION - 1,
            created_at=_FROZEN_INSTANT,
        )


def test_writer_refuses_former_suffix_without_creating_a_bundle(tmp_path: Path) -> None:
    """Cadrumo never writes or auto-renames the former published suffix."""
    former_path = tmp_path / "export.aeat-bucket.tar.gz"

    with pytest.raises(SealedArchiveWriteError, match="former-product bundle suffix"):
        write_sealed_archive(former_path, header=_header(), payload_bytes=_PAYLOAD)

    assert not former_path.exists()
    assert not (tmp_path / "export.cadrumo-bucket.tar.gz").exists()


def test_archive_metadata_is_normalised_byte_stable(tmp_path: Path) -> None:
    """Two writes of the same content produce bit-identical archives."""
    first_path = tmp_path / "first.cadrumo-bucket.tar.gz"
    second_path = tmp_path / "second.cadrumo-bucket.tar.gz"
    header = _header()

    write_sealed_archive(first_path, header=header, payload_bytes=_PAYLOAD)
    write_sealed_archive(second_path, header=header, payload_bytes=_PAYLOAD)

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
            payload_bytes=b"payload-envelope-bytes",
        )

    # Nothing at the operator's path, and no staging residue anywhere.
    assert not target.exists()
    assert not missing_parent.exists()
    assert [path.name for path in scan_directory(tmp_path)] == []


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
            payload_bytes=b"payload-envelope-bytes",
        )

    assert archive_path.read_bytes() == b"pre-existing-bytes"
    assert [path.name for path in scan_directory(tmp_path)] == ["export.cadrumo-bucket.tar.gz"]


def test_successful_write_leaves_only_the_finished_archive(tmp_path: Path) -> None:
    """Positive control: staging is invisible once the write completes.

    Without this, the failure tests above would pass equally well if the
    writer had stopped producing archives at all.
    """
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"

    write_sealed_archive(
        archive_path,
        header=_header(),
        payload_bytes=b"payload-envelope-bytes",
    )

    assert [path.name for path in scan_directory(tmp_path)] == ["export.cadrumo-bucket.tar.gz"]
    recovered = read_sealed_archive(archive_path)
    assert recovered.payload_bytes == b"payload-envelope-bytes"


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


def _repack_with_extra_member(source: Path, target: Path, *, extra_name: str) -> None:
    """Copy the canonical archive and append one extra trailing member."""
    with tarfile.open(source, mode="r:gz") as original:
        members = [(member, _member_bytes(original, member)) for member in original.getmembers()]
    with tarfile.open(target, mode="w:gz") as repacked:
        for member, data in members:
            repacked.addfile(member, io.BytesIO(data))
        extra = tarfile.TarInfo(extra_name)
        extra.size = len(b"undeclared-trailing-material")
        repacked.addfile(extra, io.BytesIO(b"undeclared-trailing-material"))


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
            payload_bytes=b"",
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
        payload_bytes=b"payload-envelope-bytes",
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


@pytest.mark.parametrize("extra_name", ("recovery.wrap", "anything.else"), ids=("retired-name", "arbitrary-name"))
def test_reader_refuses_a_trailing_member_whatever_it_is_called(tmp_path: Path, extra_name: str) -> None:
    """Trailing bytes are refused on shape alone, with no privileged name.

    ``recovery.wrap`` is named explicitly because it is the member this
    transport used to admit: it was permitted by NAME while the decision to
    read it was taken from a header flag, so a repacked archive kept the extra
    member and still read back as valid. It must now be refused on exactly the
    same footing as any other trailing member, or the retired shape would
    survive as a quiet exception.
    """
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    write_sealed_archive(
        archive_path,
        header=_header(),
        payload_bytes=b"payload-envelope-bytes",
    )
    repacked_path = tmp_path / "repacked.cadrumo-bucket.tar.gz"
    _repack_with_extra_member(archive_path, repacked_path, extra_name=extra_name)

    with pytest.raises(SealedArchiveLayoutError):
        read_sealed_archive(repacked_path)


def test_dropping_a_header_field_on_disk_makes_the_read_refuse(tmp_path: Path) -> None:
    """Anti-tautology proof for the header boundary.

    Every round-trip above would pass equally well if the reader validated
    nothing and simply returned whatever it found. This removes one field from
    the header bytes of an otherwise untouched archive and requires the read to
    refuse, so the equality assertions are known to be carried by real
    validation rather than by the writer and reader agreeing to skip it.
    """
    archive_path = tmp_path / "export.cadrumo-bucket.tar.gz"
    write_sealed_archive(archive_path, header=_header(), payload_bytes=_PAYLOAD)

    with tarfile.open(archive_path, mode="r:gz") as original:
        stored_header = json.loads(_member_bytes(original, original.getmember(HEADER_MEMBER_NAME)))
    assert "manifest_digest" in stored_header, "fixture is stale: the header no longer carries the dropped field"
    del stored_header["manifest_digest"]

    damaged_path = tmp_path / "damaged.cadrumo-bucket.tar.gz"
    _write_raw_archive(damaged_path, header_bytes=json.dumps(stored_header).encode("utf-8"))

    with pytest.raises(SealedArchiveHeaderError, match="manifest_digest"):
        read_sealed_archive(damaged_path)


def test_the_payload_is_opaque_and_carried_verbatim(tmp_path: Path) -> None:
    """The transport carries any sealed payload byte-for-byte, parsing nothing.

    This pins a contract that was ambiguous long enough to block a caller: the
    writer's documentation once promised the payload was "already wrapped in an
    ``Envelope``", while both implementations parsed nothing and the reader's
    own aggregate called it opaque. A parameter whose docstring and behaviour
    disagree is one a caller resolves by guessing.

    The ruling is opacity, so it is asserted with payloads that are emphatically
    NOT an ``Envelope`` and could never be parsed as one -- invalid UTF-8, a
    lone NUL, a byte range covering every value. If the transport ever starts
    validating its payload, this fails, which is the point: binding the archive
    to one payload type would couple it to whichever caller came first, and
    would let it REFUSE sealed material it merely failed to recognise.
    """
    hostile_payloads = (
        b"\xff\xfe\x00\x01 not utf-8 and not json",
        b"\x00",
        bytes(range(256)),
        b"{",
    )
    for index, payload in enumerate(hostile_payloads):
        archive_path = tmp_path / f"opaque-{index}.cadrumo-bucket.tar.gz"
        write_sealed_archive(archive_path, header=_header(), payload_bytes=payload)

        contents = read_sealed_archive(archive_path)

        assert contents.payload_bytes == payload, f"payload {index} was not carried verbatim"


def test_an_empty_payload_is_the_one_refused_shape(tmp_path: Path) -> None:
    """Opaque is not unconstrained: nothing-to-decrypt is still refused.

    The single invariant the transport does enforce, kept distinct from the
    opacity above so a reader does not conclude that "opaque" means the writer
    accepts anything at all.
    """
    archive_path = tmp_path / "empty-payload.cadrumo-bucket.tar.gz"

    with pytest.raises(SealedArchiveWriteError, match="nothing to decrypt"):
        write_sealed_archive(archive_path, header=_header(), payload_bytes=b"")

    assert not archive_path.exists()
