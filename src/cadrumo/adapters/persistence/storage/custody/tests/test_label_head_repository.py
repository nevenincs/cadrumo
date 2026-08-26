"""Real-filesystem separation tests for profile label-head operations."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import pytest

from ......tests.path_obstruction import obstructed_path
from .._capsule_records import ProfileCustodyCapsuleLabel
from .._label_head_repository import ProfileLabelHeadRepository
from ..errors import ProfileCustodyRecordError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("9be7d27e-9cb6-43c1-8c42-7b194e2cad5e")
_SOURCE_WITNESS = "sha256:" + "c" * 64


def _initial_label() -> ProfileCustodyCapsuleLabel:
    return ProfileCustodyCapsuleLabel.create(profile_id=_PROFILE_ID, label="Initial label")


def _replacement_label(initial: ProfileCustodyCapsuleLabel) -> ProfileCustodyCapsuleLabel:
    return ProfileCustodyCapsuleLabel.create(
        profile_id=initial.profile_id,
        label="Replacement label",
        label_revision=initial.label_revision + 1,
        previous_label_digest=initial.content_digest,
    )


def test_pure_verify_never_publishes_or_repairs_a_pending_advance(tmp_path) -> None:
    """A read-only verification observes exact state and leaves it untouched."""
    repository = ProfileLabelHeadRepository(root=tmp_path)
    initial = _initial_label()

    assert repository.verify(label=initial) is None
    assert not repository.head_path(_PROFILE_ID).exists()

    head = repository.publish_initial(label=initial, source_witness=_SOURCE_WITNESS)
    replacement = _replacement_label(initial)
    repository.begin_advance(
        current_head=head,
        current_label=initial,
        replacement_label=replacement,
    )
    pending_path = repository.pending_path(_PROFILE_ID)
    pending_bytes = pending_path.read_bytes()

    assert repository.verify(label=initial) == head
    assert pending_path.read_bytes() == pending_bytes
    assert repository.load_current(_PROFILE_ID) == head

    repository.recover_pending(profile_id=_PROFILE_ID, current_label=initial)

    assert not pending_path.exists()
    assert repository.verify(label=initial) == head


def test_explicit_pending_recovery_repairs_the_replacement_head(tmp_path) -> None:
    """Repair is an opt-in operation and its resulting head must verify."""
    repository = ProfileLabelHeadRepository(root=tmp_path)
    initial = _initial_label()
    current_head = repository.publish_initial(label=initial, source_witness=_SOURCE_WITNESS)
    replacement = _replacement_label(initial)
    repository.begin_advance(
        current_head=current_head,
        current_label=initial,
        replacement_label=replacement,
    )

    repository.recover_pending(profile_id=_PROFILE_ID, current_label=replacement)

    repaired = repository.verify(label=replacement)
    assert repaired is not None
    assert repaired.label_revision == 2
    assert repaired.previous_head_digest == current_head.self_digest
    assert not repository.pending_path(_PROFILE_ID).exists()


def test_pure_verify_refuses_malformed_linked_and_denied_heads_without_repairing_them(tmp_path: Path) -> None:
    """Read-only verification never turns hostile durable state into a new head."""
    repository = ProfileLabelHeadRepository(root=tmp_path)
    initial = _initial_label()
    head = repository.publish_initial(label=initial, source_witness=_SOURCE_WITNESS)
    head_path = repository.head_path(_PROFILE_ID)

    head_path.write_bytes(b"not a canonical profile label head")
    with pytest.raises(ProfileCustodyRecordError, match="invalid"):
        repository.verify(label=initial)

    head_path.write_bytes(head.canonical_json_bytes())
    outside = tmp_path / "outside-label-head.json"
    outside.write_bytes(head.canonical_json_bytes())
    head_path.unlink()
    os.symlink(outside, head_path)
    with pytest.raises(ProfileCustodyRecordError, match="invalid"):
        repository.verify(label=initial)
    assert outside.read_bytes() == head.canonical_json_bytes()

    head_path.unlink()
    head_path.write_bytes(head.canonical_json_bytes())
    with obstructed_path(head_path), pytest.raises(ProfileCustodyRecordError, match="invalid"):
        repository.verify(label=initial)

    assert repository.verify(label=initial) == head
