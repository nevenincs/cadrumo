"""An isolated copy of a real authority publication with one database byte altered."""

from __future__ import annotations

import shutil
from pathlib import Path

from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor

DESCRIPTOR_NAME = "authority.current.json"


def copy_and_corrupt_published_database(source_descriptor: Path, destination: Path) -> Path:
    """Copy one real publication and alter one database byte in the isolated copy."""
    descriptor = AuthorityDescriptor.read(source_descriptor)
    copied_descriptor = destination / DESCRIPTOR_NAME
    copied_database = destination / descriptor.database
    shutil.copy2(source_descriptor, copied_descriptor)
    shutil.copy2(source_descriptor.parent / descriptor.database, copied_database)

    offset = copied_database.stat().st_size // 2
    with copied_database.open("r+b") as stream:
        stream.seek(offset)
        original = stream.read(1)
        stream.seek(offset)
        stream.write(bytes([original[0] ^ 0xFF]))
    return copied_descriptor
