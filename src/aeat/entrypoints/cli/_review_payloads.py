"""Typed ``--json`` payload schemas for review CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass
and is decorated with :func:`register_schema` so the JSON-contract
test suite can enumerate every review-command surface. Without these
typed payloads, ``review queue`` and ``review view`` emit
``model_dump(mode="json")`` of free-form pydantic records, which
gives downstream tooling no stability contract for the emitted JSON.
"""

from __future__ import annotations

from ...core.identity import BucketId
from ._schemas import OutputSchema, register_schema


class ReviewQueueRowPayload(OutputSchema):
    """One row in the review queue, mirroring application.review.ReviewQueueRow."""

    item_id: str
    kind: str
    source_kind: str | None = None
    affected_object_id: str
    bucket_id: BucketId
    modelo: str | None = None
    period: str | None = None
    severity: str
    state: str
    blocking: bool
    reason: str = ""
    current_owner_surface: str
    canonical_next_command: str
    since: str  # ISO-8601 datetime
    summary: str
    legal_refs: tuple[str, ...] = ()


@register_schema("review.queue")
class ReviewQueueResult(OutputSchema):
    """JSON envelope for ``aeat review queue``."""

    operation: str = "review.queue"
    rows: tuple[ReviewQueueRowPayload, ...]


@register_schema("review.view")
class ReviewViewResult(OutputSchema):
    """JSON envelope for ``aeat review view <item_id>``."""

    operation: str = "review.view"
    row: ReviewQueueRowPayload
