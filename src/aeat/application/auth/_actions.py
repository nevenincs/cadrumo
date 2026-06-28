"""Application services for AEAT auth readiness.

:func:`update_auth` rewrites the workflow state's :class:`AuthState` snapshot
after provider configuration, authentication, or subject updates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.time import now as utc_now
from ._models import AuthState

if TYPE_CHECKING:
    from ..workflow._models import WorkflowState


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
