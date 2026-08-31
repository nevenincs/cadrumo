"""Tests for the pending post-filing event notice surfaced on the overview.

Pins that an actionable pulled AEAT post-filing event (a requerimiento, a
diligencia de embargo, …) produces a single ``warning`` Notice on the
envelope notice channel — never a silent burial in an undifferentiated
event list — and that informational messages produce no notice.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....application.overview.calendar_models import OverviewCalendarEvent, OverviewCalendarEventType
from ....core.post_filing_event import PostFilingEventKind
from ....core.json_contract import NoticeSeverity, ResolvedNoticeAction
from .._overview_rendering import overview_post_filing_event_notices

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _event(*, kind: PostFilingEventKind, reference_id: str) -> OverviewCalendarEvent:
    return OverviewCalendarEvent(
        event_type=OverviewCalendarEventType.MESSAGE,
        post_filing_kind=kind,
        event_date=date(2025, 3, 12),
        source="aeat_sede_notifications",
        summary="AEAT post-filing event",
        reference_id=reference_id,
        status="unread",
    )


def test_actionable_events_emit_single_warning_notice() -> None:
    events = (
        _event(kind=PostFilingEventKind.REQUERIMIENTO, reference_id="2596230606502"),
        _event(kind=PostFilingEventKind.DILIGENCIA_EMBARGO, reference_id="2596230606504"),
        _event(kind=PostFilingEventKind.COMUNICACION, reference_id="2596230606503"),
    )

    notices = overview_post_filing_event_notices(events)

    assert len(notices) == 1
    notice = notices[0]
    assert notice.code == "overview.post_filing.pending"
    assert notice.severity is NoticeSeverity.WARNING
    notice_action = notice.action
    assert isinstance(notice_action, ResolvedNoticeAction)
    assert notice_action.argument_bindings == ()
    assert notice_action.action.action_id == "operator.live.notifications.list"
    assert notice_action.action.target_command_key == "app.live.notifications.list"
    # The structured per-event reference->kind map rides on context; the
    # informational comunicación is excluded.
    assert notice.context == {
        "2596230606502": "requerimiento",
        "2596230606504": "diligencia_embargo",
    }
    assert "requerimiento" in notice.message
    assert "diligencia_embargo" in notice.message


def test_no_notice_when_only_informational_events_present() -> None:
    events = (
        _event(kind=PostFilingEventKind.COMUNICACION, reference_id="2596230606503"),
        _event(kind=PostFilingEventKind.DECLARACION_PRESENTADA, reference_id="2596230606505"),
    )

    assert overview_post_filing_event_notices(events) == []


def test_no_notice_for_empty_event_set() -> None:
    assert overview_post_filing_event_notices(()) == []
