"""Typed ``--json`` payload schemas for review CLI commands.

Each class declared here is a strict
:class:`~aeat.entrypoints.cli._schemas.OutputSchema` subclass decorated with
:func:`~aeat.entrypoints.cli._schemas.register_schema` so the JSON-contract
test suite can enumerate every review-command surface. The typed result enters
the shared :class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope` through
:func:`~aeat.entrypoints.cli._common._emit_envelope`.

The application review facade remains authoritative for
:class:`~aeat.application.review.ReviewQueueRow`,
:class:`~aeat.application.review.ReviewQueueReport`,
:class:`~aeat.application.review.ReviewState`, and
:class:`~aeat.application.review.ReviewSeverity`. These payloads only pin the
CLI transport shape for ``review queue`` and ``review view`` so downstream JSON
tooling does not depend on free-form ``model_dump(mode="json")`` output.
"""

from __future__ import annotations

from ...core.identity import BucketId
from ._schemas import OutputSchema, register_schema


class ReviewQueueRowPayload(OutputSchema):
    """One row in the review queue.

    Mirrors :class:`~aeat.application.review.ReviewQueueRow`: ``bucket_id`` keeps
    the active :class:`~aeat.core.identity.BucketId`, ``severity`` and ``state``
    carry the application enum values, and ``legal_refs`` stays present in JSON
    even when text output requires ``--explain`` to render those references.
    """

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
    """JSON envelope for ``aeat review queue``.

    Wraps :class:`~aeat.application.review.ReviewQueueReport` rows after the CLI
    applies kind, source-kind, state, and modelo filters through
    :func:`~aeat.application.review.project_review_queue`.
    """

    operation: str = "review.queue"
    rows: tuple[ReviewQueueRowPayload, ...]


@register_schema("review.view")
class ReviewViewResult(OutputSchema):
    """JSON envelope for ``aeat review view <item_id>``.

    Carries the single :class:`ReviewQueueRowPayload` returned by
    :func:`~aeat.application.review.project_review_item`; not-found items are
    refused before this envelope is emitted.
    """

    operation: str = "review.view"
    row: ReviewQueueRowPayload
