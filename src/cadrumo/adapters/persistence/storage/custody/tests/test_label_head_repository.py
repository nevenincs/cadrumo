"""Real-filesystem separation tests for profile label-head operations."""

from __future__ import annotations

from uuid import UUID

import pytest

from .._capsule_records import ProfileCustodyCapsuleLabel
from .._label_head_repository import ProfileLabelHeadRepository

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
