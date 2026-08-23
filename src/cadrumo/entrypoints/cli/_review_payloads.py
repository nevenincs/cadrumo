"""Typed ``--json`` payload schemas for review CLI commands.

Each class declared here is a strict
:class:`OutputSchema` subclass referenced by production-authored CommandSpec as
a deferred public schema target so the JSON-contract
test suite can enumerate every review-command surface. The typed result enters
the shared :class:`SchemaEnvelope` through
:func:`_emit_envelope`.

The application review facade remains authoritative for
:class:`ReviewQueueRow`,
:class:`ReviewQueueReport`,
:class:`ReviewState`, and
:class:`ReviewSeverity`. These payloads only pin the
CLI transport shape for ``review queue`` and ``review view`` so downstream JSON
tooling does not depend on free-form ``model_dump(mode="json")`` output.
"""

from __future__ import annotations

from ...application.review import ReviewSeverity, ReviewState
from ...core.identity import BucketId
from ...core.json_contract import OutputSchema
from ...core.time import UtcInstant
from ...domain.calculations.registry import LegalRefId


class ReviewQueueRowPayload(OutputSchema):
    """One row in the review queue.

    Mirrors :class:`ReviewQueueRow`: ``bucket_id`` keeps
    the active :class:`BucketId`, ``severity`` and ``state``
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
    severity: ReviewSeverity
    state: ReviewState
    blocking: bool
    reason: str = ""
    current_owner_surface: str
    canonical_next_command: str
    since: UtcInstant
    """The originating review item's instant, under the canonical UTC contract.

    Declared as a bare ``str`` this edge accepted any text -- ``not-date``, or
    a naive ISO instant the canonical review queue refuses -- and emitted it as
    the row's timestamp. Typed as :data:`~cadrumo.core.time.UtcInstant` it is
    the same contract the application row and the review item carry, and the
    envelope's ``model_dump(mode="json")`` still renders it as the ISO-8601
    string the wire contract documents.
    """
    summary: str
    legal_refs: tuple[LegalRefId, ...] = ()


class ReviewQueueResult(OutputSchema):
    """JSON envelope for ``aeat review queue``.

    Wraps :class:`ReviewQueueReport` rows after the CLI
    applies kind, source-kind, state, and modelo filters through
    :func:`project_review_queue`.
    """

    operation: str = "review.queue"
    rows: tuple[ReviewQueueRowPayload, ...]


class ReviewViewResult(OutputSchema):
    """JSON envelope for ``aeat review view <item_id>``.

    Carries the single
    :class:`ReviewQueueRowPayload`
    returned by
    :func:`project_review_item`; not-found items are
    refused before this envelope is emitted.
    """

    operation: str = "review.view"
    row: ReviewQueueRowPayload
