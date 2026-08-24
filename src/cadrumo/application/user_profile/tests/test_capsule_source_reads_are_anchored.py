"""A restore source is read through the anchored primitive, not by name.

``config profile restore`` accepts a capsule DIRECTORY, and that directory is
the least trusted input this domain takes: a published capsule sits inside the
product's own storage root, while a restore source is a path an operator points
at -- copied from a backup, handed over by someone else, or reconstructed by
hand after a disk failure.

It was read with ``path.is_file()`` followed by ``path.read_bytes()``. Three
things are wrong with that pair, and the custody layer had already solved all
three for the published reader:

* ``read_bytes`` FOLLOWS a symlink, so a member could name a file outside the
  capsule and its contents would be adopted into the restored profile. In a
  gestor or multi-client setting that is an exfiltration route: the bytes land
  in a profile the supplier of the capsule later receives back.
* it bounds NOTHING, while every one of these members has a declared ceiling
  the published reader already applies.
* asking ``is_file()`` and then reopening is two operations on a NAME rather
  than one on a file, which is the exact pattern
  ``read_optional_profile_custody_local_record`` documents itself as existing
  to prevent.

The reads now go through that primitive. These cases drive
``read_profile_capsule_source`` over real directories on disk -- a real
symlink, a real oversized file -- because the property is about what the
filesystem hands back, which a constructed fixture cannot stand in for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....adapters.persistence.storage.custody import PROFILE_CUSTODY_ENVELOPE_MAX_BYTES, ProfileCustodyRecordError
from .._capsule_restore import ProfileCapsuleSourceError, read_profile_capsule_source

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ENVELOPE = ("custody", "envelope.v1.json")


def _capsule_skeleton(root: Path) -> Path:
    """Create the capsule directory tree with no members written."""
    (root / "custody").mkdir(parents=True)
    (root / "data").mkdir(parents=True)
    (root / "db").mkdir(parents=True)
    return root


def test_a_member_beyond_its_ceiling_is_refused(tmp_path: Path) -> None:
    """DISCRIMINATING: an unbounded read would have loaded this whole file.

    The envelope's ceiling is small and declared, so a member far past it is
    not a large legitimate capsule -- it is a file this format cannot have
    produced.
    """
    source = _capsule_skeleton(tmp_path / "capsule")
    (source.joinpath(*_ENVELOPE)).write_bytes(b"{" + b"0" * (PROFILE_CUSTODY_ENVELOPE_MAX_BYTES * 4))

    with pytest.raises(ProfileCustodyRecordError, match="not a bounded regular file"):
        read_profile_capsule_source(source)


def test_a_member_that_is_a_symlink_is_not_followed(tmp_path: Path) -> None:
    """DISCRIMINATING: the exfiltration shape, on a real symlink.

    A capsule whose member points outside itself must not have that file's
    contents adopted into a restored profile. The fixture creates the real link
    that the filesystem gives the production reader, so inability to construct
    that link is a platform failure rather than an unobserved test case.
    """
    outside = tmp_path / "somebody-elses-secret.json"
    outside.write_bytes(b'{"stolen": true}')
    source = _capsule_skeleton(tmp_path / "capsule")
    link = source.joinpath(*_ENVELOPE)
    link.symlink_to(outside)

    with pytest.raises(ProfileCustodyRecordError, match="reparse point or directory") as raised:
        read_profile_capsule_source(source)

    assert "stolen" not in str(raised.value), "the linked file's contents must not reach the refusal either"


def test_a_missing_member_still_refuses_by_name(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the refusals above must not be "nothing reads at all".

    An empty capsule directory must still fail for the ORIGINAL reason -- a
    named missing member -- proving the reader reaches its subject and that the
    two cases above are refused for what they are rather than because the path
    stopped working.
    """
    source = _capsule_skeleton(tmp_path / "capsule")

    with pytest.raises(ProfileCapsuleSourceError, match="password envelope"):
        read_profile_capsule_source(source)
