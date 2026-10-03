"""Read the one core-metadata document a wheel carries."""

from __future__ import annotations

import zipfile
from email.message import Message
from email.parser import Parser
from pathlib import Path

from dev._paths import UTF_8

_METADATA_SUFFIX = ".dist-info/METADATA"


def read_wheel_metadata(wheel: Path) -> Message:
    """Return ``wheel``'s core metadata, refusing a wheel without exactly one document.

    Picking the first of several would let a wheel that smuggles a second
    ``METADATA`` member answer for itself with whichever the archive lists
    first, so anything other than one member is a refusal.
    """
    with zipfile.ZipFile(wheel) as archive:
        members = [name for name in archive.namelist() if name.endswith(_METADATA_SUFFIX)]
        if len(members) != 1:
            raise SystemExit(f"expected one wheel METADATA member in {wheel}; got {members!r}")
        return Parser().parsestr(archive.read(members[0]).decode(UTF_8))
