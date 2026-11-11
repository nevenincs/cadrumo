"""Agenda and backlog payloads name the resolved door of every warning and recovery, as the calendar does."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel

from ....application.operator_actions.models import DeclaredNextAction
from ....application.overview.agenda import OverviewAgenda
from ....application.overview.backlog import OverviewBacklog
from ....application.overview.calendar_models import (
    CalendarWarning,
    OverviewCalendarEntry,
    OverviewCalendarRange,
    OverviewPeriodState,
)
from ....application.overview.calendar_warnings import calendar_applicability_disagreement_warnings
from ....application.overview.next_actions import declare_next_action
from ....core.json_contract import ResolvedNoticeAction
from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.models import ObligationStatus, RecargoBand, Recovery
from ..overview_rendering import overview_agenda_output, overview_backlog_output

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_AS_OF = date(filing_year_envelope().horizon, 6, 1)
_WORK_UNIT_ID = "wu-00000000000000000000000000000001"
_GENERATED_AT = datetime(filing_year_envelope().horizon, 6, 1, tzinfo=UTC)


def _agenda(
    warnings: tuple[CalendarWarning, ...] = (), overdue: tuple[OverviewCalendarEntry, ...] = ()
) -> OverviewAgenda:
    return OverviewAgenda(as_of=_AS_OF, horizon_days=14, generated_at=_GENERATED_AT, warnings=warnings, overdue=overdue)


def _backlog(
    warnings: tuple[CalendarWarning, ...] = (), items: tuple[OverviewCalendarEntry, ...] = ()
) -> OverviewBacklog:
    return OverviewBacklog(
        range=OverviewCalendarRange(from_date=date(_AS_OF.year, 1, 1), to_date=_AS_OF),
        as_of=_AS_OF,
        items=items,
        late_count=len(items),
        generated_at=_GENERATED_AT,
        warnings=warnings,
    )


def _late_entry(recovery_action: DeclaredNextAction | None) -> OverviewCalendarEntry:
    """An overdue 130 entry; a recovery band is present exactly when a door is declared."""
    period = Period.from_year_and_code(_AS_OF.year, "1T")
    closes = _AS_OF - timedelta(days=40)
    return OverviewCalendarEntry(
        modelo="130",
        period=period,
        opens_on=closes - timedelta(days=20),
        closes_on=closes,
        adjusted_closes_on=closes,
        shift_reason="fixture",
        holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
        evaluated_on=_AS_OF,
        days_overdue=40,
        status=ObligationStatus.OVERDUE,
        user_state=OverviewPeriodState.LATE,
        recovery=None
        if recovery_action is None
        else Recovery(
            recargo_band=RecargoBand(
                id="completed_months_1",
                min_completed_months=1,
                max_completed_months=1,
                surcharge_pct=Decimal(2),
                interest_applies=False,
                legal_ref="ley-58-2003:art-27.2",
            )
        ),
        recovery_action=recovery_action,
        filing_year=period.filing_year,
    )


def _payload_warnings(typed: BaseModel) -> list[dict[str, Any]]:
    return typed.model_dump(mode="json")["warnings"]


def _bindings(warning: dict[str, Any]) -> dict[str, object]:
    return {binding["argument_name"]: binding["value"] for binding in warning["fix_action"]["argument_bindings"]}


def test_profile_edit_warning_family_carries_its_door_on_both_surfaces() -> None:
    warnings = calendar_applicability_disagreement_warnings(["303"])
    agenda, _, agenda_notices = overview_agenda_output(_agenda(warnings))
    backlog, _, backlog_notices = overview_backlog_output(_backlog(warnings), work_units_notice=None)

    for typed, notices in ((agenda, agenda_notices), (backlog, backlog_notices)):
        (warning,) = _payload_warnings(typed)
        assert warning["fix_action"]["action"]["action"]["action_id"] == "operator.profile.edit"
        assert warning["affected_modelos"] == ["303"]
        notice_action = notices[0].action
        assert isinstance(notice_action, ResolvedNoticeAction)
        assert notice_action.action.action_id == "operator.profile.edit"


def test_filed_pull_warning_family_carries_scoped_bindings_on_both_surfaces() -> None:
    year = filing_year_envelope().horizon
    warning = CalendarWarning(
        code="filing.justificante_unverified",
        message="cli.overview.warning.justificante_unverified",
        fix_action=declare_next_action("operator.live.filed.pull", modelos="303", year=year, period="1T"),
        affected_modelos=("303",),
    )
    agenda, _, _ = overview_agenda_output(_agenda((warning,)))
    backlog, _, _ = overview_backlog_output(_backlog((warning,)), work_units_notice=None)

    for typed in (agenda, backlog):
        (payload,) = _payload_warnings(typed)
        assert payload["fix_action"]["action"]["action"]["action_id"] == "operator.live.filed.pull"
        assert _bindings(payload) == {"modelos": "303", "year": year, "period": "1T"}


def test_modelo_describe_warning_family_binds_the_modelo() -> None:
    warning = CalendarWarning(
        code="iva.regime.m303_simplificado_forfait_unavailable",
        message="cli.overview.warning.m303_simplificado_forfait_unavailable",
        fix_action=declare_next_action("operator.modelo.describe", modelo="303"),
        affected_modelos=("303",),
    )
    agenda, _, _ = overview_agenda_output(_agenda((warning,)))

    (payload,) = _payload_warnings(agenda)
    assert payload["fix_action"]["action"]["action"]["action_id"] == "operator.modelo.describe"
    assert _bindings(payload) == {"modelo": "303"}


def test_no_warning_means_no_door_rows() -> None:
    agenda, _, agenda_notices = overview_agenda_output(_agenda(()))
    backlog, _, backlog_notices = overview_backlog_output(_backlog(()), work_units_notice=None)

    assert _payload_warnings(agenda) == []
    assert _payload_warnings(backlog) == []
    assert agenda_notices == []
    assert backlog_notices == []


def test_agenda_overdue_entry_keeps_its_work_create_door_with_bindings() -> None:
    period = Period.from_year_and_code(_AS_OF.year, "1T")
    door = declare_next_action(
        "operator.modelo.work.create", modelo="130", year=period.filing_year, period=period.registry_token
    )
    typed, _, _ = overview_agenda_output(_agenda(overdue=(_late_entry(door),)))

    (entry,) = typed.model_dump(mode="json")["overdue"]
    action = entry["recovery_action"]
    assert action["action"]["action_id"] == "operator.modelo.work.create"
    assert {item["argument_name"]: item["value"] for item in action["argument_bindings"]} == {
        "modelo": "130",
        "year": period.filing_year,
        "period": period.registry_token,
    }


def test_backlog_item_keeps_its_work_door_with_bindings() -> None:
    door = declare_next_action("operator.modelo.work.calculate", work_unit_id=_WORK_UNIT_ID)
    typed, _, _ = overview_backlog_output(_backlog(items=(_late_entry(door),)), work_units_notice=None)

    (item,) = typed.model_dump(mode="json")["items"]
    action = item["recovery_action"]
    assert action["action"]["action_id"] == "operator.modelo.work.calculate"
    assert {entry["argument_name"]: entry["value"] for entry in action["argument_bindings"]} == {
        "work_unit_id": _WORK_UNIT_ID
    }


def test_entry_without_recovery_declares_no_door() -> None:
    entry = _late_entry(None)
    agenda, _, _ = overview_agenda_output(_agenda(overdue=(entry,)))
    backlog, _, _ = overview_backlog_output(_backlog(items=(entry,)), work_units_notice=None)

    assert agenda.model_dump(mode="json")["overdue"][0]["recovery_action"] is None
    assert backlog.model_dump(mode="json")["items"][0]["recovery_action"] is None
