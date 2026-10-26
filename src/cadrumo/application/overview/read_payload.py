"""Canonical result payload variants for overview reads."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .coverage import ObligationCoverageReport
from .read_calendar_projection import OverviewAgendaSnapshot, OverviewBacklogSnapshot, OverviewCalendarSnapshot
from .read_projection import (
    OverviewCalendarSurveySnapshot,
    OverviewExplainSnapshot,
    OverviewNoticeSnapshot,
    OverviewPeriodStatusSnapshot,
    OverviewPrepareSnapshot,
    OverviewStatusSnapshot,
)


class OverviewStatusRead(BaseModel):
    """Full workspace status or the selected period's draft list."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["status"] = "status"
    report: OverviewStatusSnapshot | None = None
    period_report: OverviewPeriodStatusSnapshot | None = None
    coverage_advised_count: int = 0
    coverage: ObligationCoverageReport | None = None
    notices: tuple[OverviewNoticeSnapshot, ...] = ()

    @model_validator(mode="after")
    def _one(self) -> Self:
        if (self.report is None) == (self.period_report is None):
            raise ValueError("overview status requires exactly one report")
        return self


class OverviewCalendarRead(BaseModel):
    """One bound calendar or a survey with locked public pointers."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["calendar"] = "calendar"
    calendar: OverviewCalendarSnapshot | None = None
    survey: OverviewCalendarSurveySnapshot | None = None
    notices: tuple[OverviewNoticeSnapshot, ...] = ()
    deemed_served_legal_ref: str | None = None
    refusal_requirements: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _one(self) -> Self:
        if (self.calendar is None) == (self.survey is None):
            raise ValueError("overview calendar requires exactly one result")
        return self


class OverviewAgendaRead(BaseModel):
    """Canonical agenda cohorts with no underlying profile record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["agenda"] = "agenda"
    agenda: OverviewAgendaSnapshot
    refusal_requirements: tuple[str, ...] = ()


class OverviewBacklogRead(BaseModel):
    """Canonical late cohort and optional work-unit degradation notice."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["backlog"] = "backlog"
    backlog: OverviewBacklogSnapshot
    notices: tuple[OverviewNoticeSnapshot, ...] = ()
    refusal_requirements: tuple[str, ...] = ()


class OverviewExplainRead(BaseModel):
    """Registry-grounded applicability report and pending payer notices."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["explain"] = "explain"
    explanation: OverviewExplainSnapshot
    notices: tuple[OverviewNoticeSnapshot, ...] = ()


class OverviewPrepareRead(BaseModel):
    """Exact-period canonical preparation checklist."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["prepare"] = "prepare"
    preparation: OverviewPrepareSnapshot


type OverviewReadPayload = Annotated[
    OverviewStatusRead
    | OverviewCalendarRead
    | OverviewAgendaRead
    | OverviewBacklogRead
    | OverviewExplainRead
    | OverviewPrepareRead,
    Field(discriminator="kind"),
]


__all__ = [
    "OverviewAgendaRead",
    "OverviewBacklogRead",
    "OverviewCalendarRead",
    "OverviewExplainRead",
    "OverviewPrepareRead",
    "OverviewReadPayload",
    "OverviewStatusRead",
]
