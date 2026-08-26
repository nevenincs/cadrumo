"""Bounded live/historical log views projected solely from public event pages.

The modal's log pane never reads the journal directly. It folds successive
:class:`OperationPublicEventPageV1` pages into one bounded, append-only view,
honoring the page's own cursor and replay-status contract (``PAGE``,
``CAUGHT_UP``, ``EXPIRED``/``COMPACTED``) rather than re-deriving it.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from ....application.operations.event_replay import OperationEventCursor
from ....application.operations.events import OperationEventCode, OperationLogSeverity
from ....application.operations.frontend_contracts import (
    OperationPublicDiagnosticEventV1,
    OperationPublicEventPageV1,
    OperationPublicEventV1,
    OperationPublicLogEventV1,
    OperationPublicTerminalEventV1,
)
from ....application.operations.models import OperationDiagnosticReference, OperationId
from ....application.operations.persistence.replay import OperationReplayStatus
from ....core.operations import OperationEventKind

_LOG_VIEW_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid")

_DEFAULT_MAX_ROWS = 500


class OperationModalLogRowV1(BaseModel):
    """One renderer-neutral row folded from a public operation event."""

    model_config = _LOG_VIEW_CONFIG

    sequence: OperationEventCursor
    timestamp: datetime
    kind: OperationEventKind
    code: OperationEventCode
    severity: OperationLogSeverity | None
    diagnostic_ref: OperationDiagnosticReference | None


class OperationModalLogViewV1(BaseModel):
    """Bounded, append-only public log view anchored to one observation cursor."""

    model_config = _LOG_VIEW_CONFIG

    operation_id: OperationId
    anchor_cursor: OperationEventCursor
    next_cursor: OperationEventCursor
    restart_cursor: OperationEventCursor | None
    status: OperationReplayStatus
    resynchronized: bool
    rows: tuple[OperationModalLogRowV1, ...]

    @model_validator(mode="after")
    def _validate_view(self) -> OperationModalLogViewV1:
        if self.resynchronized != (self.status in {OperationReplayStatus.EXPIRED, OperationReplayStatus.COMPACTED}):
            raise ValueError("modal log resynchronization flag must mirror its replay status")
        if self.resynchronized and self.rows:
            raise ValueError("a resynchronizing modal log view cannot retain stale historical rows")
        for previous, current in zip(self.rows, self.rows[1:], strict=False):
            if current.sequence <= previous.sequence:
                raise ValueError("modal log rows must be strictly ordered by sequence")
        if self.rows and self.rows[-1].sequence > self.next_cursor:
            raise ValueError("modal log rows cannot exceed their own next cursor")
        return self


def build_initial_log_view(operation_id: OperationId) -> OperationModalLogViewV1:
    """Return the empty log view a modal starts with before its first page."""
    return OperationModalLogViewV1(
        operation_id=operation_id,
        anchor_cursor=0,
        next_cursor=0,
        restart_cursor=None,
        status=OperationReplayStatus.CAUGHT_UP,
        resynchronized=False,
        rows=(),
    )


def fold_event_page(
    view: OperationModalLogViewV1,
    page: OperationPublicEventPageV1,
    *,
    max_rows: int = _DEFAULT_MAX_ROWS,
) -> OperationModalLogViewV1:
    """Fold one public event page into the bounded live/historical log view."""
    if page.operation_id != view.operation_id:
        raise ValueError("modal log view cannot fold a page from a different operation")
    if page.status in {OperationReplayStatus.EXPIRED, OperationReplayStatus.COMPACTED}:
        assert page.restart_cursor is not None
        return OperationModalLogViewV1(
            operation_id=view.operation_id,
            anchor_cursor=page.anchor_cursor,
            next_cursor=page.next_cursor,
            restart_cursor=page.restart_cursor,
            status=page.status,
            resynchronized=True,
            rows=(),
        )
    new_rows = tuple(_project_row(event) for event in page.events)
    merged = (*view.rows, *new_rows)[-max_rows:]
    return OperationModalLogViewV1(
        operation_id=view.operation_id,
        anchor_cursor=page.anchor_cursor,
        next_cursor=page.next_cursor,
        restart_cursor=None,
        status=page.status,
        resynchronized=False,
        rows=merged,
    )


_DIAGNOSTIC_CARRYING_EVENTS = (
    OperationPublicLogEventV1,
    OperationPublicDiagnosticEventV1,
    OperationPublicTerminalEventV1,
)


def _project_row(event: OperationPublicEventV1) -> OperationModalLogRowV1:
    severity = event.severity if isinstance(event, OperationPublicLogEventV1) else None
    diagnostic_ref = event.diagnostic_ref if isinstance(event, _DIAGNOSTIC_CARRYING_EVENTS) else None
    return OperationModalLogRowV1(
        sequence=event.sequence,
        timestamp=event.timestamp,
        kind=event.kind,
        code=event.code,
        severity=severity,
        diagnostic_ref=diagnostic_ref,
    )


__all__ = [
    "OperationModalLogRowV1",
    "OperationModalLogViewV1",
    "build_initial_log_view",
    "fold_event_page",
]
