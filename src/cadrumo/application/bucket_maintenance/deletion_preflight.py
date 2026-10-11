"""The preflight every frontend runs before one named profile is deleted.

Deleting a profile is confirmed in two steps on every frontend: this
observation, which destroys nothing and unlocks nothing, and then the
runtime's deletion transaction, which accepts only the fingerprint this
observation reported. The decisions made here are the ones a person is told
about before authorising the destruction: which profile the name resolves to,
that the selected profile is never the target, and that filed records still
inside the legal retention window are not erased.

A refusal is returned as data, not raised. Each frontend reports it in its own
vocabulary, and a retention refusal still carries the observation the person
needs to see: how many records are retained and when the window clears.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from ...domain.retention.floor import erase_is_blocked
from ..user_profile.custody_ports import ProfileBucketStoragePort
from ..user_profile.profile_summary import selected_profile_id
from ..workflow.errors import ProfileLabelAmbiguousError
from ..workflow.profile_bucket_scan import read_profile_bucket
from .contracts import AssessBucketDeletionCommand, BucketDeletionAssessment
from .service import BucketMaintenanceService


class ProfileDeletionRefusal(StrEnum):
    """Why a named profile is not offered for deletion."""

    UNKNOWN_PROFILE = "unknown_profile"
    PROFILE_LABEL_AMBIGUOUS = "profile_label_ambiguous"
    PROFILE_SELECTED = "profile_selected"
    RETENTION_FLOOR = "retention_floor"


@dataclass(frozen=True, slots=True)
class ProfileDeletionPreflight:
    """What deleting one named profile would destroy, or why it is not offered.

    ``profile_id`` and ``label`` are present once the name resolved to exactly
    one profile. ``assessment`` is present once that profile was observed on
    disk, which a retention refusal has done and a selected-profile refusal
    has not.
    """

    requested_name: str
    refusal: ProfileDeletionRefusal | None = None
    profile_id: str | None = None
    label: str | None = None
    assessment: BucketDeletionAssessment | None = None


def assess_named_profile_deletion(
    name: str, *, bucket_storage: ProfileBucketStoragePort, root: Path | None = None
) -> ProfileDeletionPreflight:
    """Observe the profile ``name`` resolves to and decide whether it may be deleted.

    Args:
        name: The profile's label as the person typed it.
        bucket_storage: The bucket layout and lock capability of the calling host.
        root: Storage root override; the effective root when omitted.

    Returns:
        The observation, with ``refusal`` set when the profile is not offered
        for deletion. Nothing is unlocked, locked or written.

    Raises:
        BucketDeleteRefusedError: The target's custody is not in a state the
            maintenance authority can observe.
    """
    try:
        pointer = read_profile_bucket(name, root=root)
    except ProfileLabelAmbiguousError:
        return ProfileDeletionPreflight(name, ProfileDeletionRefusal.PROFILE_LABEL_AMBIGUOUS)
    except ValueError:
        return ProfileDeletionPreflight(name, ProfileDeletionRefusal.UNKNOWN_PROFILE)
    if pointer is None:
        return ProfileDeletionPreflight(name, ProfileDeletionRefusal.UNKNOWN_PROFILE)
    if selected_profile_id(root=root) == pointer.bucket_id:
        return ProfileDeletionPreflight(
            name, ProfileDeletionRefusal.PROFILE_SELECTED, profile_id=pointer.bucket_id, label=pointer.label
        )
    assessment = BucketMaintenanceService(bucket_storage=bucket_storage, root=root).assess_deletion(
        AssessBucketDeletionCommand(bucket_id=pointer.bucket_id)
    )
    if not assessment.exists:
        return ProfileDeletionPreflight(
            name, ProfileDeletionRefusal.UNKNOWN_PROFILE, profile_id=pointer.bucket_id, label=pointer.label
        )
    retention = assessment.retention
    blocked = retention is not None and erase_is_blocked(blocks_erase=retention.blocks_erase)
    return ProfileDeletionPreflight(
        name,
        ProfileDeletionRefusal.RETENTION_FLOOR if blocked else None,
        profile_id=pointer.bucket_id,
        label=pointer.label,
        assessment=assessment,
    )


__all__ = ["ProfileDeletionPreflight", "ProfileDeletionRefusal", "assess_named_profile_deletion"]
