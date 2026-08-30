"""Neutral application contracts shared by reset and bucket deletion."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..core.models import STRICT_FROZEN_CONFIG
from ..core.identity import ContentDigest


class BucketDeletionFingerprint(BaseModel):
    """Structured fold of observed deletion-relevant bucket contents.

    The fingerprint is neither a revision lock nor proof recorded by a reset
    journal.

    Carried a ``manifest_digest`` until the plaintext bucket manifest was
    retired. Nothing produced it in production -- every construction in the
    tree was a hand-built fixture -- and its subject no longer exists, so it
    was removed rather than left as a field only tests could fill. The three
    surviving facts are exactly what
    :class:`~application.user_profile.ProfileCustodyInventoryWitness` observes
    of a capsule, which is what makes this contract answerable at all now.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(default=1, ge=1)
    digest: ContentDigest
    file_count: int = Field(ge=1)
    total_bytes: int = Field(ge=0)


__all__ = ["BucketDeletionFingerprint"]
