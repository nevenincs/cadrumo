"""Closed, locale-neutral snapshots of persisted workflow run read facts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Self, cast

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from ...core.errors.hierarchy import SiteHealthState
from ...core.identifier_grammar import NamespacedId
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ...domain.deadlines.models import ObligationStatus
from ..operations.public_period import PublicPeriod
from ..operations.public_scalar import (
    PublicDecimal,
    PublicNamedScalar,
    project_scalar,
    restore_scalar,
)
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.projection import PreconditionVerdictSnapshot
from .abort import WorkflowAbortReason
from .run_models import (
    SiteHealthAlert,
    WorkflowAlreadyFiledDetails,
    WorkflowDeadlineContextDetails,
    WorkflowDeadlineRecoveryFacts,
    WorkflowObligationFacts,
    WorkflowResult,
    WorkflowSiteHealthFacts,
    WorkflowStage,
    WorkflowStepDetails,
)

_DETAIL_ADAPTER: TypeAdapter[WorkflowStepDetails] = TypeAdapter(WorkflowStepDetails)


class WorkflowDeadlineRecoverySnapshot(BaseModel):
    """Schema-safe legal and amount facts for one overdue obligation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    still_filable: bool
    recargo_band_id: str
    min_completed_months: int = Field(ge=0)
    max_completed_months: int | None = Field(default=None, ge=0)
    surcharge_pct: PublicDecimal
    interest_applies: bool
    legal_ref: str

    @classmethod
    def from_recovery(cls, recovery: WorkflowDeadlineRecoveryFacts) -> Self:
        """Copy a validated canonical recovery record."""
        return cls(
            still_filable=recovery.still_filable,
            recargo_band_id=recovery.recargo_band_id,
            min_completed_months=recovery.min_completed_months,
            max_completed_months=recovery.max_completed_months,
            surcharge_pct=PublicDecimal(decimal=str(recovery.surcharge_pct)),
            interest_applies=recovery.interest_applies,
            legal_ref=recovery.legal_ref,
        )

    def to_recovery(self) -> WorkflowDeadlineRecoveryFacts:
        """Restore and validate the canonical recovery invariant."""
        return WorkflowDeadlineRecoveryFacts(
            still_filable=self.still_filable,
            recargo_band_id=self.recargo_band_id,
            min_completed_months=self.min_completed_months,
            max_completed_months=self.max_completed_months,
            surcharge_pct=Decimal(self.surcharge_pct.decimal),
            interest_applies=self.interest_applies,
            legal_ref=self.legal_ref,
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_recovery()
        return self


class WorkflowObligationSnapshot(BaseModel):
    """Lossless public-schema copy of canonical filing obligation facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    modelo: str
    period: PublicPeriod
    opens_on: date
    closes_on: date
    payment_cutoff_on: date | None = None
    status: ObligationStatus
    boe_references: tuple[str, ...] = ()
    recovery: WorkflowDeadlineRecoverySnapshot | None = None

    @classmethod
    def from_obligation(cls, obligation: WorkflowObligationFacts) -> Self:
        """Copy persisted obligation facts without prose or raw commands."""
        return cls(
            modelo=str(obligation.modelo),
            period=PublicPeriod.from_period(obligation.period),
            opens_on=obligation.opens_on,
            closes_on=obligation.closes_on,
            payment_cutoff_on=obligation.payment_cutoff_on,
            status=obligation.status,
            boe_references=obligation.boe_references,
            recovery=(
                WorkflowDeadlineRecoverySnapshot.from_recovery(obligation.recovery)
                if obligation.recovery is not None
                else None
            ),
        )

    def to_obligation(self) -> WorkflowObligationFacts:
        """Reconstruct the canonical obligation for existing resume/render code."""
        return WorkflowObligationFacts(
            modelo=Modelo(self.modelo),
            period=self.period.to_period(),
            opens_on=self.opens_on,
            closes_on=self.closes_on,
            payment_cutoff_on=self.payment_cutoff_on,
            status=self.status,
            boe_references=self.boe_references,
            recovery=self.recovery.to_recovery() if self.recovery is not None else None,
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_obligation()
        return self


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
        keys = (
            *[item.key for item in self.scalars],
            *[item.key for item in self.dates],
            *[item.key for item in self.strings],
        )
        if len(set(keys)) != len(keys) or set(keys) & {"kind", "period", "auth_check"}:
            raise ValueError("workflow detail repeats a fact name")
        values: dict[str, object] = {"kind": self.kind}
        values.update({item.key: restore_scalar(item.value) for item in self.scalars})
        values.update({item.key: item.value for item in self.dates})
        values.update({item.key: item.values for item in self.strings})
        if self.period is not None:
            values["period"] = self.period.to_period()
        if self.auth_check is not None:
            values["auth_check"] = self.auth_check.to_detail()
        return _DETAIL_ADAPTER.validate_python(values)

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

    @classmethod
    def from_run(cls, run: WorkflowResult) -> Self:
        """Capture only the terminal step and existing CLI-visible top facts."""
        final_step = run.steps[-1] if run.steps else None
        detail = final_step.details if final_step is not None else run.summary_details
        return cls(
            run_id=run.run_id,
            started_at=run.started_at,
            final_stage=run.final_stage,
            aborted_reason=run.aborted_reason,
            obligation=WorkflowObligationSnapshot.from_obligation(run.obligation)
            if run.obligation is not None
            else None,
            summary_stage=final_step.stage if final_step is not None else None,
            summary_locale_key=final_step.summary_locale_key if final_step is not None else run.summary_locale_key,
            summary_details=WorkflowDetailSnapshot.from_detail(detail) if detail is not None else None,
            site_health_alert=(
                WorkflowSiteHealthSnapshot.from_alert(final_step.site_health_alert)
                if final_step is not None and final_step.site_health_alert is not None
                else None
            ),
            precondition_verdict=(
                PreconditionVerdictSnapshot.from_verdict(final_step.precondition_verdict)
                if final_step is not None and final_step.precondition_verdict is not None
                else None
            ),
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
    "WorkflowObligationSnapshot",
    "WorkflowRunSnapshot",
    "validate_run_period_facts",
]
