"""Strict pydantic v2 records for AEAT auth readiness.

:class:`AuthState` is the workflow-state auth snapshot embedded in
:class:`~aeat.application.workflow.WorkflowState` and updated by
:func:`aeat.application.auth.update_auth`. Operator-facing status and test
surfaces expose redacted readiness through
:class:`~aeat.application.state_projection.ProjectionAuthReadiness` rather than
re-reading this model independently.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG


class AuthState(BaseModel):
    """Persisted local AEAT access readiness state.

    This record stores provider selection, the certificate filesystem
    reference, and local session timestamps inside
    :class:`~aeat.application.workflow.WorkflowState`. Public CLI emit shapes
    read the canonical projection into
    :class:`~aeat.application.auth.AuthStatusResult` and
    :class:`~aeat.application.auth.AuthTestResult`.
    """

    model_config = STRICT_FROZEN_CONFIG

    provider: str | None = None
    certificate_path: str | None = None
    configured_at: datetime | None = None
    authenticated_at: datetime | None = None
    subject: str | None = None
