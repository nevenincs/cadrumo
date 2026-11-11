"""Agenda and backlog payloads name the resolved door of every warning, as the calendar does."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest
from pydantic import BaseModel

from ....application.overview.agenda import OverviewAgenda
from ....application.overview.backlog import OverviewBacklog
from ....application.overview.calendar_models import CalendarWarning, OverviewCalendarRange
from ....application.overview.calendar_warnings import calendar_applicability_disagreement_warnings
from ....application.overview.next_actions import declare_next_action
from ....core.json_contract import ResolvedNoticeAction
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..overview_rendering import overview_agenda_output, overview_backlog_output

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_AS_OF = date(filing_year_envelope().horizon, 6, 1)
_GENERATED_AT = datetime(filing_year_envelope().horizon, 6, 1, tzinfo=UTC)


def _agenda(warnings: tuple[CalendarWarning, ...]) -> OverviewAgenda:
    return OverviewAgenda(as_of=_AS_OF, horizon_days=14, generated_at=_GENERATED_AT, warnings=warnings)


def _backlog(warnings: tuple[CalendarWarning, ...]) -> OverviewBacklog:
    return OverviewBacklog(
        range=OverviewCalendarRange(from_date=date(_AS_OF.year, 1, 1), to_date=_AS_OF),
        as_of=_AS_OF,
        late_count=0,
        generated_at=_GENERATED_AT,
        warnings=warnings,
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
