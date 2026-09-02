"""The overview calendar's optional-evidence loaders degrade, never hard-refuse.

A live-model persona (audit `2026-07-03-agent-harness-operability-followup`)
found `overview calendar` hard-refused for a never-filed taxpayer with
`Local modelo event evidence is unavailable for this calendar row`, and
`--allow-incomplete` did not relax it — the same operability class the backlog
work-unit fix addressed. The three calendar-evidence loaders enrich the
schedule-derived calendar with observed AEAT events and filing evidence; when
their optional persisted state cannot be loaded they must DEGRADE to a
schedule-only calendar with a WARNING notice (over-reporting an obligation as
still due — the safe direction), not refuse the whole surface.

These tests force each loader's dependency to raise and assert the loader
returns empty rows plus a notice rather than raising a `typer.BadParameter`.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....application.overview.calendar_models import OverviewCalendarRange
from ....core.json_contract import NoticeSeverity
from .._overview import (
    local_calendar_filing_evidence,
    local_live_calendar_events,
    local_modelo_record_calendar_events,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_RANGE = OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2025, 12, 31))


def test_live_events_loader_degrades_to_notice() -> None:
    events, notice = local_live_calendar_events("bogus-bucket", _RANGE, as_of=date(2025, 6, 1))
    assert events == ()
    assert notice is not None
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.code == "overview.calendar_live_events_degraded"


def test_modelo_record_events_loader_degrades_to_notice() -> None:
    events, notice = local_modelo_record_calendar_events("bogus-bucket", _RANGE)
    assert events == ()
    assert notice is not None
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.code == "overview.calendar_modelo_events_degraded"


def test_filing_evidence_loader_degrades_to_notice() -> None:
    evidence, notice = local_calendar_filing_evidence("bogus-bucket", ())
    assert evidence == ()
    assert notice is not None
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.code == "overview.calendar_filing_evidence_degraded"
