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


def forge_colliding_capsule_label(*, profile_id: UUID, label: str, root: Path | None = None) -> None:
    """Forge a committed label that a supported writer would refuse.

    This is a custody corruption fixture, so it belongs beside the custody
    label-file mutation primitive rather than in shared test support.
    """
    from ..capsule import load_committed_profile_custody_label_record
    from ..capsule_records import ProfileCustodyCapsuleLabel
    from ..label_head_repository import ProfileLabelHeadRepository
    from cadrumo.core.config import load_settings
    from cadrumo.core.hashing import prefixed_digest

    resolved_root = root if root is not None else load_settings().cadrumo_local_storage_root
    if resolved_root is None:
        raise RuntimeError("forging a capsule label requires a configured local storage root")

    current = load_committed_profile_custody_label_record(profile_id, root=resolved_root)
    heads = ProfileLabelHeadRepository(root=resolved_root)
    heads.recover_pending(profile_id=profile_id, current_label=current)
    current_head = heads.verify(label=current)
    if current_head is None:
        raise RuntimeError("forging a capsule label requires an existing label head")
    replacement = ProfileCustodyCapsuleLabel.create(
        profile_id=profile_id,
        label=label,
        label_revision=current.label_revision + 1,
        previous_label_digest=current.content_digest,
    )
    heads.begin_advance(
        current_head=current_head,
        current_label=current,
        replacement_label=replacement,
    )
    replace_test_profile_custody_label_file(
        profile_id,
        replacement.canonical_json_bytes(),
        expected_sha256=prefixed_digest(current.canonical_json_bytes()),
        root=resolved_root,
    )
    heads.recover_pending(profile_id=profile_id, current_label=replacement)
    if heads.verify(label=replacement) is None:
        raise RuntimeError("forged replacement label did not retain its head")


__all__ = ["forge_colliding_capsule_label", "replace_test_profile_custody_label_file"]
