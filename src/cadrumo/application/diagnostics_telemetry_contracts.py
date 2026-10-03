"""Consent-gated diagnostics telemetry request and retained result contracts."""

from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ..core.identity.digest import ContentDigest
from ..core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..core.telemetry.tier import TelemetryTier
from .diagnostics_telemetry import TelemetryFlushPreview
from .operations.models import CredentialFreeOperationRequest


class DiagnosticsTelemetryFlushRequest(CredentialFreeOperationRequest):
    """Per-invocation consent and explicit worker telemetry overrides."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    dry_run: bool = True
    acknowledged: bool = False
    opt_in: bool | None = None
    tier: TelemetryTier | None = None
    endpoint: str | None = None


class DiagnosticsTelemetryCountersSnapshot(BaseModel):
    """The exact three counters produced by the canonical diagnostics flush."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    runs: Annotated[int, Field(ge=0)]
    succeeded: Annotated[int, Field(ge=0)]
    failed: Annotated[int, Field(ge=0)]


class DiagnosticsTelemetryTimingsSnapshot(BaseModel):
    """Flush reports no timings; an undeclared metric is refused, never dropped."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class DiagnosticsTelemetryPayloadSnapshot(BaseModel):
    """Closed complete copy of the canonical flush payload, with identical JSON."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    schema_version: Literal[1] = 1
    workspace_hash: ContentDigest
    command: Literal["diagnostics.llm_run"]
    counters: DiagnosticsTelemetryCountersSnapshot
    timings_ms: DiagnosticsTelemetryTimingsSnapshot
    succeeded: bool
    error_kind: None = None
    captured_at: Annotated[str, Field(min_length=1)]


class DiagnosticsTelemetryPreviewSnapshot(BaseModel):
    """Complete canonical allowlisted payload and current consent verdict."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    payload: DiagnosticsTelemetryPayloadSnapshot
    gate_permits: bool
    endpoint_configured: bool
    would_send: bool

    def to_preview(self) -> TelemetryFlushPreview:
        """Restore the canonical presenter model without recomputing any value."""
        return TelemetryFlushPreview.model_validate(self.model_dump())


class DiagnosticsTelemetryFlushProjection(BaseModel):
    """Legacy sent flag means attempted handoff, never confirmed delivery."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    dry_run: bool
    preview: DiagnosticsTelemetryPreviewSnapshot
    sent: bool

    @model_validator(mode="after")
    def _send_facts(self) -> Self:
        if self.preview.would_send != (self.preview.gate_permits and self.preview.endpoint_configured):
            raise ValueError("telemetry preview gate facts are inconsistent")
        if self.sent != (not self.dry_run and self.preview.would_send):
            raise ValueError("telemetry attempted handoff differs from its preview")
        return self


class DiagnosticsTelemetryFlushExecutionResult(BaseModel):
    """Encrypted retained preview and its settled external-attempt fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: DiagnosticsTelemetryFlushProjection
