"""Leaf records shared by workflow state and profile-bucket scanning."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.identity.bucket import BucketId
from ...core.identity.profile_label import ProfileLabel
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN


class ProfileBucketPointer(BaseModel):
    """Pointer to a secure profile bucket and its operator-facing label.

    Both identity fields carry the shared core constraint the bucket
    manifest persists them under, so the projection from a manifest to this
    pointer cannot fail on a value the manifest accepted.
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    label: ProfileLabel


__all__ = ["ProfileBucketPointer"]
