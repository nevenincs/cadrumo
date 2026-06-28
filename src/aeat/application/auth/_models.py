"""Strict pydantic v2 records for AEAT auth readiness.

:class:`AuthState` is the workflow-state auth snapshot updated by
:func:`aeat.application.auth.update_auth`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG


class AuthState(BaseModel):
    """Local AEAT access readiness state."""

    model_config = STRICT_FROZEN_CONFIG

    provider: str | None = None
    certificate_path: str | None = None
    configured_at: datetime | None = None
    authenticated_at: datetime | None = None
    subject: str | None = None
