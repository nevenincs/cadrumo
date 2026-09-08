"""Custody-owned helpers for manufacturing otherwise unreachable test states."""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from uuid import UUID

from .._capsule_data import replace_capsule_file
from ..capsule import recognize_current_profile_capsule
from ..capsule_records import PROFILE_CUSTODY_LABEL_FILENAME, PROFILE_CUSTODY_LABEL_MAX_BYTES
from ..errors import ProfileCustodyRecordError
from ..filesystem_primitives import anchor_directory


def replace_test_profile_custody_label_file(
    profile_id: UUID,
    payload: bytes,
    *,
    expected_sha256: str,
    root: Path,
) -> None:
    """CAS-replace a committed label solely to manufacture a test state."""
    capsule_path = recognize_current_profile_capsule(profile_id, root=root)
    if capsule_path is None:
        raise ProfileCustodyRecordError("test mutation requires a committed capsule")
    data_path = capsule_path / "data"
    with ExitStack() as anchors:
        anchor_directory(anchors, capsule_path)
        anchor_directory(anchors, data_path)
        replace_capsule_file(
            data_path,
            PROFILE_CUSTODY_LABEL_FILENAME,
            payload,
            expected_sha256=expected_sha256,
            maximum_bytes=PROFILE_CUSTODY_LABEL_MAX_BYTES,
        )


__all__ = ["replace_test_profile_custody_label_file"]
