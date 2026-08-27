"""A sealed archive member cannot decompress past what the writer can produce.

The reader opens the archive ``r:gz``, so the bytes on disk bound nothing. An
unbounded ``read()`` on a member turns an operator-supplied file into a
memory-exhaustion surface: a highly compressible payload expands by orders of
magnitude, and the path that reaches this reader is ``config profile archive import``,
which takes a path. An archive can be corrupted in place, or handed to an
operator by someone else.

The ceiling is not arbitrary. The writer caps a capsule payload at
``PROFILE_CAPSULE_ARCHIVE_MAX_PAYLOAD_BYTES``, so no archive this product produced can carry a larger
member -- refusing above it rejects nothing legitimate. Both halves are pinned
here, because the danger runs in two directions: a missing ceiling admits a
bomb, and a ceiling that drifted BELOW the writer's cap would start refusing
real archives, which is the quieter failure and the one a lone literal would
eventually cause.

The bound is applied to the bytes actually delivered. ``tarfile`` limits
``extractfile`` to the member's declared size, so a forged SMALL size truncates
rather than smuggling -- it is not a bypass. What the ceiling exists for is the
opposite shape: a member declaring an enormous size whose compressed form is
tiny, which ``tarfile`` will hand over in full.
"""

from __future__ import annotations

import io
import tarfile
from typing import TYPE_CHECKING

import pytest

from .._sealed_archive_errors import SealedArchiveLayoutError
from .._sealed_archive_reader import _MAX_MEMBER_BYTES, _read_member_info

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _archive_carrying(tmp_path: Path, *, name: str, payload: bytes) -> tarfile.TarFile:
    """Build a real gzip tar carrying one member."""
    archive_path = tmp_path / "probe.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as writing:
        info = tarfile.TarInfo(name=name)
        info.size = len(payload)
        writing.addfile(info, io.BytesIO(payload))
    return tarfile.open(archive_path, mode="r:gz")


def test_a_member_past_the_ceiling_is_refused(tmp_path: Path) -> None:
    """DISCRIMINATING: the expansion an unbounded read would have absorbed.

    Driven with a real gzip member of compressible bytes rather than a mock
    stream, so what is proved is the reader's behaviour against the format it
    actually parses.
    """
    oversized = b"\0" * (_MAX_MEMBER_BYTES + 1024)

    with _archive_carrying(tmp_path, name="payload.envelope", payload=oversized) as archive:
        member = archive.getmember("payload.envelope")
        with pytest.raises(SealedArchiveLayoutError, match="ceiling"):
            _read_member_info(archive, member)


def test_a_member_within_the_ceiling_is_returned_whole(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the ceiling must not be refusing everything.

    Without this, a bound of zero -- or a read that always raised -- would
    satisfy the refusal above while making every real archive unreadable. The
    payload is asserted byte-for-byte, so a truncating read fails here too.
    """
    body = b"cadrumo-sealed-archive-probe" * 64

    with _archive_carrying(tmp_path, name="payload.envelope", payload=body) as archive:
        member = archive.getmember("payload.envelope")

        assert _read_member_info(archive, member) == body


def test_sealed_archive_member_bound_matches_the_writer_cap() -> None:
    """Anchor: the ceiling must stay equal to what the writer can emit.

    Below the writer's cap this reader would refuse archives the product itself
    produced -- a failure that would surface as an operator unable to restore a
    legitimate backup, long after the change that caused it.
    """
    from ......application.user_profile.capsule_archive import PROFILE_CAPSULE_ARCHIVE_MAX_PAYLOAD_BYTES

    assert _MAX_MEMBER_BYTES == PROFILE_CAPSULE_ARCHIVE_MAX_PAYLOAD_BYTES
