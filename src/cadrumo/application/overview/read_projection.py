"""Closed snapshots for authenticated overview read results."""

from __future__ import annotations

from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, NonNegativeInt, model_validator

from ...core.filing_year import FilingYear
from ...core.json_contract import Notice, NoticeSeverity
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.applicability import ApplicabilityVerdict
from ..operations.public_period import PublicPeriod
from ..operations.public_scalar import PublicNamedScalar, project_facts, restore_facts
from .calendar_models import OverviewStatusReport
from .data_prep import DataPrepStep, DataPrepStepId, DataPrepStepState, DataPrepWalkthrough
from .explain import OverviewExplain
from .pipeline_projection import PipelineNextActionSnapshot
from .read_calendar_projection import OverviewCalendarSnapshot


class OverviewStatusSnapshot(BaseModel):
    """Exact existing workspace counters and advisory keys."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    active_profile_name: str | None
    transactions: NonNegativeInt
    invoices: NonNegativeInt
    drafts: NonNegativeInt
    work_units: NonNegativeInt
    discarded_work_units: NonNegativeInt
    calculation_revisions: NonNegativeInt
    unreadable_rows: NonNegativeInt
    filing_obligation_advisories: tuple[str, ...]
    unsupported_work_create_modelos: tuple[str, ...]

    @classmethod
    def from_report(cls, report: OverviewStatusReport) -> Self:
        """Copy the canonical report without broad or inferred fields."""
        return cls(**report.model_dump(mode="python"))

    def to_report(self) -> OverviewStatusReport:
        """Rebuild the same validated report for existing CLI rendering."""
        return OverviewStatusReport.model_validate(self.model_dump(mode="python"), strict=True)


class OverviewDraftSnapshot(BaseModel):
    """One already-scoped declaration draft in period status output."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    draft_id: str
    modelo: str
    status: str


class OverviewPeriodStatusSnapshot(BaseModel):
    """Only declaration drafts in the requested canonical filing period."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    period: PublicPeriod
    drafts: tuple[OverviewDraftSnapshot, ...]
    verbose: bool


class OverviewLockedProfileSnapshot(BaseModel):
    """Public pointer row; no other profile's encrypted facts are read."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: str
    label: str


class OverviewCalendarSurveySnapshot(BaseModel):
    """One bound profile calendar and public locked-profile pointers."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    from_date: date
    to_date: date
    active_profile_id: str | None
    active_label: str | None
    active_calendar: OverviewCalendarSnapshot | None
    locked: tuple[OverviewLockedProfileSnapshot, ...]
    setup_incomplete: tuple[OverviewLockedProfileSnapshot, ...]

    @model_validator(mode="after")
    def _active(self) -> Self:
        if (self.active_profile_id is None) != (self.active_calendar is None):
            raise ValueError("survey active profile identity and calendar must agree")
        if self.active_calendar is not None and self.active_label is None:
            raise ValueError("survey active profile needs its public label")
        return self


class OverviewNoticeSnapshot(BaseModel):
    """One bounded already-derived advisory, without a second action channel."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    severity: NoticeSeverity
    code: str
    message: str
    context: tuple[tuple[str, str], ...]
    action_id: str | None

    @model_validator(mode="after")
    def _context(self) -> Self:
        if len({key for key, _value in self.context}) != len(self.context):
            raise ValueError("overview notice repeats a context field")
        return self

    @classmethod
    def from_notice(cls, notice: Notice) -> Self:
        """Copy only scalar diagnostic facts and declared no-argument action ID."""
        action = notice.action
        action_id: str | None = None
        if action is not None:
            if action.action is None:
                raise ValueError("overview notice action is unresolved")
            action_id = action.action.action_id
            if action.argument_bindings:
                raise ValueError("overview notice action requires unsupported bound arguments")
        return cls(
            severity=notice.severity,
            code=notice.code,
            message=notice.message,
            context=tuple(sorted((notice.context or {}).items())),
            action_id=action_id,
        )


class OverviewExplainSnapshot(BaseModel):
    """Applicability evidence and bounded scalar profile facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: str
    year: FilingYear
    applicable: bool
    verdict: ApplicabilityVerdict
    rationale: str
    legal_refs: tuple[str, ...]
    scheduling_rationale: str | None
    out_of_plazo_warning: str | None
    profile_facts: tuple[PublicNamedScalar, ...]
    generated_at: datetime

    @model_validator(mode="after")
    def _facts(self) -> Self:
        restore_facts(self.profile_facts)
        if not self.modelo or not self.rationale or not self.legal_refs:
            raise ValueError("overview explanation is incomplete")
        return self

    @classmethod
    def from_explain(cls, report: OverviewExplain) -> Self:
        """Copy a canonical explanation without widening its fact values."""
        return cls(
            modelo=report.modelo,
            year=report.year,
            applicable=report.applicable,
            verdict=report.verdict,
            rationale=report.rationale,
            legal_refs=tuple(report.legal_refs),
            scheduling_rationale=report.scheduling_rationale,
            out_of_plazo_warning=report.out_of_plazo_warning,
            profile_facts=project_facts(report.profile_facts),
            generated_at=report.generated_at,
        )

    def to_explain(self) -> OverviewExplain:
        """Restore the canonical validated report for localized rendering."""
        return OverviewExplain.model_validate(
            {
                "modelo": self.modelo,
                "year": self.year,
                "applicable": self.applicable,
                "verdict": self.verdict,
                "rationale": self.rationale,
                "legal_refs": self.legal_refs,
                "scheduling_rationale": self.scheduling_rationale,
                "out_of_plazo_warning": self.out_of_plazo_warning,
                "profile_facts": restore_facts(self.profile_facts),
                "generated_at": self.generated_at,
            },
            strict=True,
        )


class OverviewPrepareStepSnapshot(BaseModel):
    """One ordered preparation result and its canonical declared action."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    step_id: DataPrepStepId
    state: DataPrepStepState
    summary: str
    next_action: PipelineNextActionSnapshot | None

    @classmethod
    def from_step(cls, step: DataPrepStep) -> Self:
        """Capture the canonical state and action without reconstructing advice."""
        return cls(
            step_id=step.step_id,
            state=step.state,
            summary=step.summary,
            next_action=PipelineNextActionSnapshot.from_action(step.next_action)
            if step.next_action is not None
            else None,
        )

    def to_step(self) -> DataPrepStep:
        """Restore one canonical validated checklist step."""
        return DataPrepStep(
            step_id=self.step_id,
            state=self.state,
            summary=self.summary,
            next_action=self.next_action.to_action() if self.next_action is not None else None,
        )


class OverviewPrepareSnapshot(BaseModel):
    """Exact scope and ordered canonical data-preparation checklist."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: str
    filing_year: FilingYear
    period: str
    steps: tuple[OverviewPrepareStepSnapshot, ...]
    ready_for_calculation: bool

    @model_validator(mode="after")
    def _steps(self) -> Self:
        if len({step.step_id for step in self.steps}) != len(self.steps):
            raise ValueError("overview preparation repeats a step")
        if self.ready_for_calculation != all(step.state is DataPrepStepState.DONE for step in self.steps):
            raise ValueError("overview preparation readiness contradicts its steps")
        return self

    @classmethod
    def from_walkthrough(cls, report: DataPrepWalkthrough) -> Self:
        """Copy only the report fields already emitted by the CLI."""
        return cls(
            modelo=report.modelo,
            filing_year=report.filing_year,
            period=report.period,
            steps=tuple(OverviewPrepareStepSnapshot.from_step(step) for step in report.steps),
            ready_for_calculation=report.ready_for_calculation,
        )

    def to_walkthrough(self) -> DataPrepWalkthrough:
        """Revalidate the captured checklist for existing output rendering."""
        return DataPrepWalkthrough(
            modelo=self.modelo,
            filing_year=self.filing_year,
            period=self.period,
            steps=tuple(step.to_step() for step in self.steps),
            ready_for_calculation=self.ready_for_calculation,
        )


__all__ = [
    "OverviewCalendarSurveySnapshot",
    "OverviewDraftSnapshot",
    "OverviewExplainSnapshot",
    "OverviewLockedProfileSnapshot",
    "OverviewNoticeSnapshot",
    "OverviewPeriodStatusSnapshot",
    "OverviewPrepareSnapshot",
    "OverviewStatusSnapshot",
]
