"""Result payloads owned by the ``config profile list`` leaf.

These live beside their leaf rather than in the shared config payload module.
That module imports the application services every config verb needs -- reset
journals, auth diagnostics, profile health -- and importing it to describe two
rows dragged a sibling command's whole service graph, including the
authenticated profile aggregate, into a listing that authenticates nothing.
"""

from __future__ import annotations

from ....core.identity import BucketId, ProfileLabel
from ....core.json_contract import OutputSchema


class ProfilePointerPayload(OutputSchema):
    """One profile row in the config profile listing.

    The row is deliberately limited to the committed capsule's operator-facing
    label and its immutable identity. Setup readiness belongs to the
    authenticated profile record projection, not to this unauthenticated
    listing row. ``name`` and ``bucket_id`` carry the same bounds the profile
    pointer enforces, so a blank label or identity is refused rather than
    listed.
    """

    name: ProfileLabel
    bucket_id: BucketId
    active: bool


class ConfigListResult(OutputSchema):
    """JSON envelope for ``aeat config profile list``.

    Each :class:`ProfilePointerPayload` row identifies one committed profile,
    while ``active_profile`` names the current pointer's operator-facing label
    -- bounded exactly as the label itself is bounded -- so an empty-but-present
    active label is refused rather than silently listed as active.
    """

    active_profile: ProfileLabel | None = None
    profiles: list[ProfilePointerPayload]


__all__ = ["ConfigListResult", "ProfilePointerPayload"]
