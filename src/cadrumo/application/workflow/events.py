"""Bucket-event emission for workflow-state lifecycle transitions.

Currently owns the ``workflow_state.reset`` emission path used by the
``aeat config repair reset-progress`` recovery route. The fingerprint
payload mirrors the row-level metadata of the discarded envelope plus
the actor/source/timestamp captured by the boundary; the plaintext
envelope content is never recorded. Events are appended to the
composed bucket-event history port via :func:`emit_workflow_state_reset`.

See Also:
    :class:`~cadrumo.application.workflow.WorkflowStateRepository`
        Computes :class:`WorkflowStateResetFingerprint` records and calls this
        module before deleting the workflow-state envelope.
    :func:`cadrumo.application.workflow.persistence.reset_workflow_state`
        Public helper used by the ``config repair reset-progress`` command to
        execute the emit-before-delete recovery route.
    :class:`~cadrumo.domain.buckets.BucketEvent`
        Immutable audit event emitted for ``workflow_state.reset``.
    :func:`~cadrumo.application.user_profile.default_profile_bucket_event_history_repository`
        Composed append-only repository port that stores the reset event.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.identity import BucketId
from ...core.time import now as utc_now
from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import emit_bucket_event
from ..user_profile.custody_ports import default_profile_bucket_event_history_repository

SYSTEM_BUCKET_ID: Final[str] = "system"
WORKFLOW_STATE_OBJECT_ID: Final[str] = "cadrumo.workflow:state"
_EVENT_PAYLOAD_VERSION: Final[int] = 1


class WorkflowStateResetFingerprint(BaseModel):
    """Row-level fingerprint of a discarded workflow-state envelope.

    Captured before the row is deleted so the operator-visible audit
    trail records what was discarded without retaining any plaintext
    payload. ``reason_class`` classifies the discarded envelope:
    ``"readable"`` when it decrypts and validates cleanly,
    ``"unreadable"`` when the row exists but cannot be decoded, and
    ``"absent"`` when no envelope row is present.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int | None = Field(default=None, ge=1)
    written_at: datetime | None = None
    byte_length: int | None = Field(default=None, ge=0)
    reason_class: str = Field(min_length=1, max_length=64)
    recovered_bucket_id: BucketId | None = None


class WorkflowStateResetEvent(BaseModel):
    """Typed payload for the ``workflow_state.reset`` bucket event."""

    model_config = STRICT_FROZEN_CONFIG

    fingerprint: WorkflowStateResetFingerprint
    actor: str = Field(min_length=1, max_length=64)
    source: str = Field(min_length=1, max_length=64)
    timestamp: datetime


def _payload_from_event(event: WorkflowStateResetEvent) -> dict[str, str]:
    """Project the typed event payload onto the bucket-event mapping."""
    fp = event.fingerprint
    payload: dict[str, str] = {
        "reason_class": fp.reason_class,
        "actor": event.actor,
        "source": event.source,
        "timestamp": event.timestamp.isoformat(),
    }
    if fp.schema_version is not None:
        payload["schema_version"] = str(fp.schema_version)
    if fp.written_at is not None:
        payload["written_at"] = fp.written_at.isoformat()
    if fp.byte_length is not None:
        payload["byte_length"] = str(fp.byte_length)
    if fp.recovered_bucket_id is not None:
        payload["recovered_bucket_id"] = fp.recovered_bucket_id
    return payload


def emit_workflow_state_reset(
    *,
    fingerprint: WorkflowStateResetFingerprint,
    actor: str,
    source: str,
) -> BucketEvent:
    """Append ``workflow_state.reset`` to history and return the :class:`BucketEvent`.

    The event is recorded against the recovered bucket id when one
    survives on the fingerprint, or against the system bucket otherwise.
    """
    occurred_at = utc_now()
    event_model = WorkflowStateResetEvent(
        fingerprint=fingerprint,
        actor=actor,
        source=source,
        timestamp=occurred_at,
    )
    return emit_bucket_event(
        repository=default_profile_bucket_event_history_repository(),
        bucket_id=fingerprint.recovered_bucket_id or SYSTEM_BUCKET_ID,
        event_type=BucketEventType.WORKFLOW_STATE_RESET,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.WORKFLOW_STATE,
        object_id=WORKFLOW_STATE_OBJECT_ID,
        payload=_payload_from_event(event_model),
        payload_version=_EVENT_PAYLOAD_VERSION,
    )


__all__ = [
    "SYSTEM_BUCKET_ID",
    "WORKFLOW_STATE_OBJECT_ID",
    "WorkflowStateResetEvent",
    "WorkflowStateResetFingerprint",
    "emit_workflow_state_reset",
]
