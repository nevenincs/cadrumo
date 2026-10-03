"""Closed run-health, latency and error report snapshots."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field

from ..core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .diagnostics_run_health import (
    ErrorKindCount,
    ErrorsBreakdownReport,
    LatencyPercentiles,
    LatencyReport,
    LlmRunProviderMetrics,
    RunHealthReport,
    RunRecordView,
)
from .diagnostics_timing_contracts import _native_timing_values, _public_timing_values, _TimingSnapshot
from .operations.public_scalar import PublicDecimal


class DiagnosticsRunProviderSnapshot(_TimingSnapshot):
    """Closed copy of the canonical provider timing facts."""

    provider: Annotated[str, Field(min_length=1)]

    @classmethod
    def from_metrics(cls, value: LlmRunProviderMetrics) -> DiagnosticsRunProviderSnapshot:
        """Copy canonical facts without changing decimal precision."""
        return cls.model_validate(_public_timing_values(value))

    def to_metrics(self) -> LlmRunProviderMetrics:
        """Restore the canonical timing row without calculating aggregates."""
        return LlmRunProviderMetrics.model_validate(_native_timing_values(self))


class DiagnosticsRunHealthSnapshot(BaseModel):
    """Complete canonical local auth/timing report, without broader evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    since: date | None = None
    until: date | None = None
    llm_providers: tuple[DiagnosticsRunProviderSnapshot, ...] = ()
    total_runs: Annotated[int, Field(ge=0)] = 0
    total_succeeded: Annotated[int, Field(ge=0)] = 0
    total_failed: Annotated[int, Field(ge=0)] = 0
    auth_provider: str = ""
    auth_configured: bool = False
    persisted_session_present: bool = False
    persisted_session_expired: bool | None = None
    persisted_session_state: str = ""
    probe_summary: str = ""

    @classmethod
    def from_report(cls, value: RunHealthReport) -> DiagnosticsRunHealthSnapshot:
        """Copy the complete service report, including local auth facts."""
        return cls(
            **value.model_dump(exclude={"llm_providers"}),
            llm_providers=tuple(DiagnosticsRunProviderSnapshot.from_metrics(row) for row in value.llm_providers),
        )

    def to_report(self) -> RunHealthReport:
        """Restore the existing report and its canonical derived properties."""
        return RunHealthReport(
            **self.model_dump(exclude={"llm_providers"}),
            llm_providers=tuple(row.to_metrics() for row in self.llm_providers),
        )


class DiagnosticsRunRecordSnapshot(RunRecordView):
    """Complete canonical timing/outcome row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class DiagnosticsLatencyPercentilesSnapshot(BaseModel):
    """Canonical percentiles; the existing service computes every value."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    entries: Annotated[int, Field(ge=0)] = 0
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    mean_duration_ms: PublicDecimal | None = None
    p50_duration_ms: int | None = None
    p95_duration_ms: int | None = None
    p99_duration_ms: int | None = None

    @classmethod
    def from_metrics(cls, value: LatencyPercentiles) -> DiagnosticsLatencyPercentilesSnapshot:
        """Copy percentiles produced by the canonical nearest-rank service."""
        return cls.model_validate(_public_timing_values(value))

    def to_metrics(self) -> LatencyPercentiles:
        """Restore existing percentile facts without computing any percentile."""
        return LatencyPercentiles.model_validate(_native_timing_values(self))


class DiagnosticsLatencySnapshot(BaseModel):
    """Complete canonical latency report with a closed nested schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    since: date | None = None
    until: date | None = None
    provider: str | None = None
    overall: DiagnosticsLatencyPercentilesSnapshot = Field(default_factory=DiagnosticsLatencyPercentilesSnapshot)
    by_provider: tuple[tuple[str, DiagnosticsLatencyPercentilesSnapshot], ...] = ()

    @classmethod
    def from_report(cls, value: LatencyReport) -> DiagnosticsLatencySnapshot:
        """Copy the full canonical overall and provider reports."""
        return cls(
            since=value.since,
            until=value.until,
            provider=value.provider,
            overall=DiagnosticsLatencyPercentilesSnapshot.from_metrics(value.overall),
            by_provider=tuple(
                (provider, DiagnosticsLatencyPercentilesSnapshot.from_metrics(row))
                for provider, row in value.by_provider
            ),
        )

    def to_report(self) -> LatencyReport:
        """Restore the complete canonical latency presenter model."""
        return LatencyReport(
            since=self.since,
            until=self.until,
            provider=self.provider,
            overall=self.overall.to_metrics(),
            by_provider=tuple((provider, row.to_metrics()) for provider, row in self.by_provider),
        )


class DiagnosticsErrorCountSnapshot(ErrorKindCount):
    """Canonical stable error-kind count."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class DiagnosticsErrorsSnapshot(BaseModel):
    """Complete canonical failed-run breakdown."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    since: date | None = None
    until: date | None = None
    provider: str | None = None
    total_runs: Annotated[int, Field(ge=0)] = 0
    total_failed: Annotated[int, Field(ge=0)] = 0
    by_error_kind: tuple[DiagnosticsErrorCountSnapshot, ...] = ()

    def to_report(self) -> ErrorsBreakdownReport:
        """Restore every canonical report field and its existing failure property."""
        return ErrorsBreakdownReport.model_validate(self.model_dump())
