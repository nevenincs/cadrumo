"""Typed ``--json`` payload schemas for ``aeat config profile history``.

The adjacent :mod:`cadrumo.entrypoints.cli._config_descendiente_payloads` owns
the declared-descendant contract, leaving this module to carry append-only
bucket history without coupling the payload families.

:class:`BucketHistoryEventPayload` re-uses the canonical
identity aliases and closed enums from :mod:`cadrumo.domain.buckets` rather than
re-declaring their shape, following the projection pattern
:class:`~cadrumo.entrypoints.cli.modelo_aux_payloads.WorkUnitHistoryEventPayload`
used for the work-unit history surface.

The content-addressed ``event_id`` derivation is deliberately *not* re-run here:
this is a read-only presentation projection of an event the catalogue already
validated, and the wire row carries no signature of its own.

Both :class:`BucketHistoryEventPayload` and :class:`BucketHistoryResult` are
strict :class:`OutputSchema` transport shapes referenced for the CLI's
``--json`` contract.
"""

from __future__ import annotations

from datetime import datetime

from ...core.identity.bucket import BucketId
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

    Mirrors :class:`~cadrumo.domain.buckets.event.BucketEvent`'s operator-facing
    projection.
    ``payload_version`` is the discriminator a consumer needs to interpret the
    free-form ``payload`` mapping; the adjacent
    :class:`~cadrumo.entrypoints.cli.ledger_results.LedgerHistoryEventPayload`
    projection already carries it, so this row stays at parity.
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

    The envelope token ``config.bucket.history`` is a stable machine API.
    """

    operation: str
    bucket_id: BucketId
    event_types: list[BucketEventType] | None = None
    since: datetime | None = None
    until: datetime | None = None
    object_id: BucketObjectId | None = None
    actor: BucketActorLabel | None = None
    events: list[BucketHistoryEventPayload]
