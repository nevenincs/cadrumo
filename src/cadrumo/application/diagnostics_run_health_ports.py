"""Application-owned contract for local diagnostic run telemetry.

The run-health use cases aggregate timing and outcome facts, but they do not
choose where those facts are stored.  ``DiagnosticRunTelemetryPort`` keeps the
application independent of the outbound LLM recorder while
``DiagnosticRunRecord`` gives every diagnostic projection one validated shape.
The outbound adapter translates its storage record and failures at the
composition boundary.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from pydantic import BaseModel, Field, NonNegativeInt

from ..core.models import STRICT_FROZEN_CONFIG
from ..core.time.utc import UtcInstant


class DiagnosticRunRecord(BaseModel):
    """One timing/outcome fact supplied to the diagnostic run-health service."""

    model_config = STRICT_FROZEN_CONFIG

    run_id: str = Field(min_length=1)
    caller: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = ""
    duration_ms: NonNegativeInt
    succeeded: bool
    error_kind: str = ""
    started_at: UtcInstant


class DiagnosticRunTelemetryError(RuntimeError):
    """A diagnostic telemetry read failed at the outbound boundary."""


class DiagnosticRunTelemetryPort(Protocol):
    """Read-only local run telemetry required by diagnostic projections."""

    def load_records(
        self,
        *,
        since: date | None,
        until: date | None,
    ) -> tuple[DiagnosticRunRecord, ...]:
        """Return validated run facts within the inclusive date window."""


__all__ = [
    "DiagnosticRunRecord",
    "DiagnosticRunTelemetryError",
    "DiagnosticRunTelemetryPort",
]
