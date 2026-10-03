"""Exact-profile diagnostics read request and result contracts."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..core.time.date_range import validate_inclusive_date_range
from .diagnostics_run_report_contracts import (
    DiagnosticsErrorsSnapshot,
    DiagnosticsLatencySnapshot,
    DiagnosticsRunHealthSnapshot,
    DiagnosticsRunRecordSnapshot,
)
from .diagnostics_usage_contracts import DiagnosticsUsageSnapshot
from .operations.models import CredentialFreeOperationRequest

type DiagnosticsReadKind = Literal["run_health", "runs", "latency", "errors", "llm_usage"]


class DiagnosticsReadRequest(CredentialFreeOperationRequest):
    """Only exact routing and the existing inclusive report filters."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    kind: DiagnosticsReadKind
    since: date | None = None
    until: date | None = None
    provider: str | None = None
    limit: Annotated[int, Field(ge=1)] | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _filters(self) -> Self:
        validate_inclusive_date_range(self.since, self.until)
        if self.limit is not None and self.kind != "runs":
            raise ValueError("limit belongs only to diagnostics runs")
        return self


class DiagnosticsReadProjection(DiagnosticsReadRequest):
    """One complete canonical report and the exact selection that produced it."""

    run_health: DiagnosticsRunHealthSnapshot | None = None
    runs: tuple[DiagnosticsRunRecordSnapshot, ...] | None = None
    latency: DiagnosticsLatencySnapshot | None = None
    errors: DiagnosticsErrorsSnapshot | None = None
    llm_usage: DiagnosticsUsageSnapshot | None = None

    def _validate_selected_report(self) -> None:
        selected = {
            "run_health": self.run_health,
            "runs": self.runs,
            "latency": self.latency,
            "errors": self.errors,
            "llm_usage": self.llm_usage,
        }
        if any((value is not None) != (kind == self.kind) for kind, value in selected.items()):
            raise ValueError("diagnostics result does not match its report kind")

    def _validate_report_windows(self) -> None:
        reports = (self.run_health, self.latency, self.errors, self.llm_usage)
        if any(report is not None and (report.since != self.since or report.until != self.until) for report in reports):
            raise ValueError("diagnostics report window differs from the request")

    def _validate_report_provider(self) -> None:
        reports = (self.latency, self.errors)
        if any(report is not None and report.provider != self.provider for report in reports):
            raise ValueError("diagnostics report provider differs from the request")

    def _validate_run_limit(self) -> None:
        if self.runs is not None and self.limit is not None and len(self.runs) > self.limit:
            raise ValueError("diagnostics run rows exceed the requested limit")

    @model_validator(mode="after")
    def _one_report(self) -> Self:
        self._validate_selected_report()
        self._validate_report_windows()
        self._validate_report_provider()
        self._validate_run_limit()
        return self


class DiagnosticsReadExecutionResult(BaseModel):
    """Encrypted retained report until current destination authorization."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: DiagnosticsReadProjection
