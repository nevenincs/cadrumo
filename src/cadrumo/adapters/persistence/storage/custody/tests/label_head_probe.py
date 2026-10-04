"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from uuid import UUID

from ..capsule_records import ProfileCustodyCapsuleLabel
from ..errors import ProfileCustodyRecordError
from ..label_head_models import ProfileLabelHead, ProfileLabelHeadPendingAdvance
from ..label_head_repository import ProfileLabelHeadRepository


def load_current(self: ProfileLabelHeadRepository, profile_id: UUID) -> ProfileLabelHead:
    """Return the exact durable head for an already-verified current capsule."""
    head = self._load_head(profile_id)
    if head is None:
        raise ProfileCustodyRecordError("profile label head is absent")
    return head


def begin_advance(
    self: ProfileLabelHeadRepository,
    *,
    current_head: ProfileLabelHead,
    current_label: ProfileCustodyCapsuleLabel,
    replacement_label: ProfileCustodyCapsuleLabel,
) -> ProfileLabelHeadPendingAdvance:
    """Durably record intent to advance the head before writing the new head itself.

    This is the write-ahead half of the crash-recovery protocol
    :meth:`recover_pending` completes on the other side: the pending
    record lands on disk FIRST, so a crash between here and the eventual
    head write leaves a resumable trail instead of an ambiguous
    half-advanced state.
    """
    if not current_head.verifies(current_label):
        raise ProfileCustodyRecordError("profile label differs from its trusted head")
    replacement_head = ProfileLabelHead.advance(current=current_head, label=replacement_label)
    pending = ProfileLabelHeadPendingAdvance.create(
        expected_head=current_head,
        expected_label=current_label,
        replacement_label=replacement_label,
        replacement_head=replacement_head,
    )
    self._write_pending_exclusive(pending)
    return pending
