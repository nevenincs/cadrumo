"""Strict pydantic v2 records for AEAT auth readiness."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuthState(BaseModel):
    """Local AEAT access readiness state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str | None = None
    certificate_path: str | None = None
    configured_at: datetime | None = None
    authenticated_at: datetime | None = None
    subject: str | None = None
