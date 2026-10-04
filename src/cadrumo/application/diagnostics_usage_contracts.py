"""Closed LLM usage snapshots with unchanged canonical derived values."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field

from ..core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .diagnostics_run_health import LlmRunHealthProviderMetrics, LlmUsageModelMetrics, LlmUsageReport
from .diagnostics_timing_contracts import TimingSnapshot, native_timing_values, public_timing_values


class DiagnosticsUsageModelSnapshot(TimingSnapshot):
    """Canonical per-model metrics, restored for existing success-rate calculation."""

    model: str = ""
    total_duration_ms: Annotated[int, Field(ge=0)] = 0

    @classmethod
    def from_metrics(cls, value: LlmUsageModelMetrics) -> DiagnosticsUsageModelSnapshot:
        """Copy the complete model row without recomputing metrics."""
        return cls.model_validate(public_timing_values(value))

    def to_metrics(self) -> LlmUsageModelMetrics:
        """Restore the existing per-model metrics and derived success rate."""
        return LlmUsageModelMetrics.model_validate(native_timing_values(self))


class DiagnosticsUsageProviderSnapshot(TimingSnapshot):
    """Canonical per-provider/model metrics with closed nested schemas."""

    provider: Annotated[str, Field(min_length=1)]
    total_duration_ms: Annotated[int, Field(ge=0)] = 0
    models: tuple[DiagnosticsUsageModelSnapshot, ...] = ()

    @classmethod
    def from_metrics(cls, value: LlmRunHealthProviderMetrics) -> DiagnosticsUsageProviderSnapshot:
        """Copy the complete canonical provider row and its ordered model rows."""
        return cls.model_validate(
            {
                **public_timing_values(value, exclude={"models"}),
                "models": tuple(DiagnosticsUsageModelSnapshot.from_metrics(row) for row in value.models),
            }
        )

    def to_metrics(self) -> LlmRunHealthProviderMetrics:
        """Restore existing provider metrics and their canonical derived properties."""
        return LlmRunHealthProviderMetrics.model_validate(
            {
                **native_timing_values(self, exclude={"models"}),
                "models": tuple(row.to_metrics() for row in self.models),
            }
        )


class DiagnosticsUsageSnapshot(BaseModel):
    """Complete canonical usage report, restored for existing summary properties."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    since: date | None = None
    until: date | None = None
    by_provider: tuple[DiagnosticsUsageProviderSnapshot, ...] = ()
    total_runs: Annotated[int, Field(ge=0)] = 0
    total_succeeded: Annotated[int, Field(ge=0)] = 0
    total_failed: Annotated[int, Field(ge=0)] = 0

    @classmethod
    def from_report(cls, value: LlmUsageReport) -> DiagnosticsUsageSnapshot:
        """Copy the full service report and ordered provider/model breakdowns."""
        return cls(
            **value.model_dump(exclude={"by_provider"}),
            by_provider=tuple(DiagnosticsUsageProviderSnapshot.from_metrics(row) for row in value.by_provider),
        )

    def to_report(self) -> LlmUsageReport:
        """Restore the complete existing usage presenter contract."""
        return LlmUsageReport(
            **self.model_dump(exclude={"by_provider"}),
            by_provider=tuple(row.to_metrics() for row in self.by_provider),
        )
