"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from pathlib import Path

from ..custody.filesystem import compare_and_replace_profile_custody_local_record
from ..profile_custody import _PersistenceProfileCustodyLocalRecordStore


def compare_and_replace(
    self: object, path: Path, *, expected: bytes | None, replacement: bytes, maximum_bytes: int
) -> None:
    if not isinstance(self, _PersistenceProfileCustodyLocalRecordStore):
        raise TypeError("fixture requires the persistence local record store")
    compare_and_replace_profile_custody_local_record(
        path, expected=expected, replacement=replacement, maximum_bytes=maximum_bytes
    )
