"""Closed, locale-neutral snapshots of persisted workflow run read facts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Self, cast

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from ...core.errors.hierarchy import SiteHealthState
from ...core.identifier_grammar import NamespacedId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ..operations.public_period import PublicPeriod
from ..operations.public_scalar import (
    PublicNamedScalar,
    project_scalar,
    restore_scalar,
)
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.projection import PreconditionVerdictSnapshot
from .abort import WorkflowAbortReason
from .obligation_snapshot import WorkflowObligationSnapshot
from .run_models import (
    SiteHealthAlert,
    WorkflowAlreadyFiledDetails,
    WorkflowDeadlineContextDetails,
    WorkflowResult,
    WorkflowSiteHealthFacts,
    WorkflowStage,
    WorkflowStep,
    WorkflowStepDetails,
)

_DETAIL_ADAPTER: TypeAdapter[WorkflowStepDetails] = TypeAdapter(WorkflowStepDetails)


def _detail_snapshot_keys(snapshot: WorkflowDetailSnapshot) -> tuple[str, ...]:
    return (
        *[item.key for item in snapshot.scalars],
        *[item.key for item in snapshot.dates],
        *[item.key for item in snapshot.strings],
    )


def _validate_detail_snapshot_keys(keys: tuple[str, ...]) -> None:
    if len(set(keys)) != len(keys) or set(keys) & {"kind", "period", "auth_check"}:
        raise ValueError("workflow detail repeats a fact name")


def _restore_detail_snapshot_values(snapshot: WorkflowDetailSnapshot) -> dict[str, object]:
    values: dict[str, object] = {"kind": snapshot.kind}
    values.update({item.key: restore_scalar(item.value) for item in snapshot.scalars})
    values.update({item.key: item.value for item in snapshot.dates})
    values.update({item.key: item.values for item in snapshot.strings})
    if snapshot.period is not None:
        values["period"] = snapshot.period.to_period()
    if snapshot.auth_check is not None:
        values["auth_check"] = snapshot.auth_check.to_detail()
    return values


class WorkflowNamedDate(BaseModel):
    """One named date in a closed terminal-detail variant."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    key: str
    value: date


class WorkflowNamedStrings(BaseModel):
    """One named immutable string sequence in a terminal-detail variant."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    key: str
    values: tuple[str, ...]


class WorkflowDetailSnapshot(BaseModel):
    """One canonical terminal detail encoded as typed, schema-visible fields."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: str
    scalars: tuple[PublicNamedScalar, ...] = ()
    dates: tuple[WorkflowNamedDate, ...] = ()
    strings: tuple[WorkflowNamedStrings, ...] = ()
    period: PublicPeriod | None = None
    auth_check: WorkflowDetailSnapshot | None = None

    @classmethod
    def from_detail(cls, detail: WorkflowStepDetails) -> Self:
        """Copy only facts declared by the canonical discriminated detail model."""
        scalars: list[PublicNamedScalar] = []
        dates: list[WorkflowNamedDate] = []
        strings: list[WorkflowNamedStrings] = []
        period = None
        auth_check = None
        for key, value in detail.__dict__.items():
            if key == "kind" or value is None:
                continue
            if key == "period":
                period = PublicPeriod.from_period(cast(Period, value))
            elif key == "auth_check":
                auth_check = cls.from_detail(value)
            elif isinstance(value, date):
                dates.append(WorkflowNamedDate(key=key, value=value))
            elif isinstance(value, tuple):
                strings.append(WorkflowNamedStrings(key=key, values=cast("tuple[str, ...]", value)))
            else:
                scalars.append(PublicNamedScalar(key=key, value=project_scalar(value)))
        return cls(
            kind=detail.kind,
            scalars=tuple(scalars),
            dates=tuple(dates),
            strings=tuple(strings),
            period=period,
            auth_check=auth_check,
        )

    def to_detail(self) -> WorkflowStepDetails:
        """Restore the discriminated canonical variant and reject extra facts."""
        _validate_detail_snapshot_keys(_detail_snapshot_keys(self))
        return _DETAIL_ADAPTER.validate_python(_restore_detail_snapshot_values(self))

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_detail()
        return self


class WorkflowSiteHealthSnapshot(BaseModel):
    """Only the terminal site's stable state and numeric diagnostics."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    stage: WorkflowStage
    run_id: str
    alert_code: str
    state: SiteHealthState
    observed_at: datetime
    http_status: int
    retry_after_seconds: int | None
    detected_marker_count: int

    @classmethod
    def from_alert(cls, alert: SiteHealthAlert) -> Self:
        """Copy the already-redacted canonical health observation."""
        status = alert.status
        return cls(
            stage=alert.stage,
            run_id=alert.run_id,
            alert_code=status.alert_code,
            state=status.state,
            observed_at=status.observed_at,
            http_status=status.http_status,
            retry_after_seconds=status.retry_after_seconds,
            detected_marker_count=status.detected_marker_count,
        )

    def to_alert(self) -> SiteHealthAlert:
        """Restore the canonical alert for established CLI rendering."""
        return SiteHealthAlert(
            stage=self.stage,
            run_id=self.run_id,
            status=WorkflowSiteHealthFacts(
                alert_code=self.alert_code,
                state=self.state,
                observed_at=self.observed_at,
                http_status=self.http_status,
                retry_after_seconds=self.retry_after_seconds,
                detected_marker_count=self.detected_marker_count,
            ),
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_alert()
        return self


class WorkflowRunSnapshot(BaseModel):
    """One terminal-only workflow record shared by run and run-details."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    run_id: str = Field(min_length=16, max_length=16, pattern=r"^[0-9a-f]{16}$")
    started_at: datetime
    final_stage: WorkflowStage
    aborted_reason: WorkflowAbortReason | None
    obligation: WorkflowObligationSnapshot | None
    summary_stage: WorkflowStage | None
    summary_locale_key: NamespacedId
    summary_details: WorkflowDetailSnapshot | None
    site_health_alert: WorkflowSiteHealthSnapshot | None
    precondition_verdict: PreconditionVerdictSnapshot | None

    @staticmethod
    def _summary_detail(run: WorkflowResult, final_step: WorkflowStep | None) -> WorkflowStepDetails | None:
        return final_step.details if final_step is not None else run.summary_details

    @staticmethod
    def _summary_stage(final_step: WorkflowStep | None) -> WorkflowStage | None:
        return final_step.stage if final_step is not None else None

    @staticmethod
    def _summary_locale_key(run: WorkflowResult, final_step: WorkflowStep | None) -> NamespacedId:
        return final_step.summary_locale_key if final_step is not None else run.summary_locale_key

    @staticmethod
    def _obligation_snapshot(run: WorkflowResult) -> WorkflowObligationSnapshot | None:
        return WorkflowObligationSnapshot.from_obligation(run.obligation) if run.obligation is not None else None

    @staticmethod
    def _site_health_snapshot(final_step: WorkflowStep | None) -> WorkflowSiteHealthSnapshot | None:
        if final_step is None or final_step.site_health_alert is None:
            return None
        return WorkflowSiteHealthSnapshot.from_alert(final_step.site_health_alert)

    @staticmethod
    def _verdict_snapshot(final_step: WorkflowStep | None) -> PreconditionVerdictSnapshot | None:
        if final_step is None or final_step.precondition_verdict is None:
            return None
        return PreconditionVerdictSnapshot.from_verdict(final_step.precondition_verdict)

    @classmethod
    def from_run(cls, run: WorkflowResult) -> Self:
        """Capture only the terminal step and existing CLI-visible top facts."""
        final_step = run.steps[-1] if run.steps else None
        detail = cls._summary_detail(run, final_step)
        return cls(
            run_id=run.run_id,
            started_at=run.started_at,
            final_stage=run.final_stage,
            aborted_reason=run.aborted_reason,
            obligation=cls._obligation_snapshot(run),
            summary_stage=cls._summary_stage(final_step),
            summary_locale_key=cls._summary_locale_key(run, final_step),
            summary_details=WorkflowDetailSnapshot.from_detail(detail) if detail is not None else None,
            site_health_alert=cls._site_health_snapshot(final_step),
            precondition_verdict=cls._verdict_snapshot(final_step),
        )

    def validate_period_facts(self) -> None:
        """Refuse contradiction between obligation and CLI-visible detail periods."""
        if self.final_stage not in {WorkflowStage.DONE, WorkflowStage.ABORTED}:
            raise ValueError("workflow snapshot must be terminal")
        if (self.final_stage is WorkflowStage.ABORTED) != (self.aborted_reason is not None):
            raise ValueError("workflow snapshot abort reason contradicts terminal stage")
        obligation_period = self.obligation.period if self.obligation is not None else None
        detail_period = self.summary_details.period if self.summary_details is not None else None
        if detail_period is not None and (obligation_period is None or detail_period != obligation_period):
            raise ValueError("workflow run has contradictory period facts")
        if self.site_health_alert is not None and self.site_health_alert.run_id != self.run_id:
            raise ValueError("workflow site-health alert belongs to another run")

    def to_terminal_details(self) -> WorkflowStepDetails | None:
        """Restore only the detail currently used by run and run-details renderers."""
        return self.summary_details.to_detail() if self.summary_details is not None else None

    def to_terminal_verdict(self) -> PreconditionVerdict | None:
        """Restore terminal action evidence for the existing CLI resolver."""
        return self.precondition_verdict.to_verdict() if self.precondition_verdict is not None else None

    def to_terminal_site_health(self) -> SiteHealthAlert | None:
        """Restore the terminal site-health observation for CLI rendering."""
        return self.site_health_alert.to_alert() if self.site_health_alert is not None else None

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.validate_period_facts()
        return self


def validate_run_period_facts(run: WorkflowResult) -> None:
    """Reject contradictory period-bearing summary and terminal details."""
    obligation_period = run.obligation.period if run.obligation is not None else None
    final_step = run.steps[-1] if run.steps else None
    for detail in (run.summary_details, final_step.details if final_step is not None else None):
        if not isinstance(detail, (WorkflowDeadlineContextDetails, WorkflowAlreadyFiledDetails)):
            continue
        detail_period = detail.period
        if obligation_period is None or detail_period != obligation_period:
            raise ValueError("workflow run has contradictory period facts")


__all__ = [
    "WorkflowRunSnapshot",
    "validate_run_period_facts",
]
