"""State transitions for workflow-owned authentication readiness.

:func:`update_auth` returns a new :class:`application.workflow.WorkflowState`
whose :class:`application.workflow.AuthState` snapshot reflects provider
configuration, authentication, or subject changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.time import now as utc_now
from .models import AuthState

if TYPE_CHECKING:
    from ..workflow import WorkflowState


def update_auth(
    state: WorkflowState,
    *,
    provider: str | None = None,
    certificate_path: str | None = None,
    authenticated: bool | None = None,
    subject: str | None = None,
) -> WorkflowState:
    """Update local auth readiness state.

    Returns a :class:`WorkflowState`.
    """
    auth = state.auth
    if isinstance(auth, dict):
        auth = AuthState.model_validate(auth)

    update: dict[str, object] = {}
    if provider is not None:
        update["provider"] = provider.strip().lower()
        update["configured_at"] = utc_now()
    if certificate_path is not None:
        update["certificate_path"] = certificate_path.strip() or None
        update["configured_at"] = utc_now()
    if authenticated is not None:
        update["authenticated_at"] = utc_now() if authenticated else None
    if subject is not None:
        update["subject"] = subject.strip() or None

    return state.model_copy(update={"auth": auth.model_copy(update=update), "updated_at": utc_now()})


__all__ = ["update_auth"]
