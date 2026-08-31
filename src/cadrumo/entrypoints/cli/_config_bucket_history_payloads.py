"""Typed ``--json`` payload schemas for ``aeat config profile history``.

Split out of the cohesive sibling :mod:`_config_payloads` so the append-only
event history can carry the canonical bucket-event contract without growing that
module.

The nested event row previously crossed the envelope as a bare
``dict[str, object]``, so an empty row, a bogus event type, or an unparseable
timestamp reached the operator unchallenged even though the encrypted
:class:`~cadrumo.domain.buckets.BucketEventHistoryCatalogue` that produced it
refuses all three. :class:`BucketHistoryEventPayload` re-uses the canonical
identity aliases and closed enums from :mod:`cadrumo.domain.buckets` rather than
re-declaring their shape, following the projection pattern
:class:`~cadrumo.entrypoints.cli._modelo_aux_payloads.WorkUnitHistoryEventPayload`
already established for the work-unit history surface.

The content-addressed ``event_id`` derivation is deliberately *not* re-run here:
this is a read-only presentation projection of an event the catalogue already
validated, and the wire row carries no signature of its own.

Both :class:`BucketHistoryEventPayload` and :class:`BucketHistoryResult` are
strict :class:`OutputSchema` transport shapes referenced for the CLI's
``--json`` contract.
"""

from __future__ import annotations

from datetime import datetime

from ...core.identity import BucketId
from ...core.json_contract import OutputSchema
from ...core.text_bounds import PositiveCount
from ...core.time.utc import UtcInstant
from ...domain.buckets.event import (
    BucketActorLabel,
    BucketEventId,
    BucketEventObjectType,
    BucketEventType,
    BucketObjectId,
)


class BucketHistoryEventPayload(OutputSchema):
    """One append-only bucket event row in the profile-history envelope.

    Mirrors :class:`~cadrumo.domain.buckets.BucketEvent`'s operator-facing
    projection. Enum members and ``datetime`` values render to the same JSON the
    former hand-built mapping emitted, so the wire form is unchanged.
    ``payload_version`` is the discriminator a consumer needs to interpret the
    free-form ``payload`` mapping; the adjacent
    :class:`~cadrumo.entrypoints.cli._ledger_payloads.LedgerHistoryEventPayload`
    projection already carries it, so this row now stays at parity.
    """

    event_id: BucketEventId
    event_type: BucketEventType
    occurred_at: UtcInstant
    actor: BucketActorLabel
    object_type: BucketEventObjectType
    object_id: BucketObjectId
    payload_version: PositiveCount
    payload: dict[str, str] = {}


class BucketHistoryResult(OutputSchema):
    """JSON envelope for ``aeat config profile history``.

    The envelope token ``config.bucket.history`` is a stable machine API and
    is intentionally retained after the operator-facing verb moved from
    ``config bucket history`` to ``config profile history`` (D1 family).
    """

    operation: str
    bucket_id: BucketId
    event_types: list[BucketEventType] | None = None
    since: datetime | None = None
    until: datetime | None = None
    object_id: BucketObjectId | None = None
    actor: BucketActorLabel | None = None
    events: list[BucketHistoryEventPayload]
