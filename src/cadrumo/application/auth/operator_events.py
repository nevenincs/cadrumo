"""Workflow auth event construction."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..workflow.state_models import WorkflowState


def append_auth_bucket_event(
    state: WorkflowState,
    *,
    action: str,
    object_id: str,
) -> WorkflowState:
    """Append one profile-scoped workflow event."""
    from ..workflow.review_models import WorkflowEvent

    # Auth flows can run before a profile is bound (e.g. `auth configure`
    # during initial setup). Falling back to the literal "default" silently
    # pools the unbound-session event into any operator's bucket that
    # happens to be named "default" — automation-audited as CRIT bucket-isolation
    # leak. Use a clearly system-scoped sentinel that cannot collide with
    # a real profile UUID so repair surfaces can spot + clear these.
    bucket_id = state.active_profile_bucket_id() or "__unbound_session__"
    event = WorkflowEvent(action=action, bucket_id=bucket_id, object_id=object_id)
    return state.model_copy(update={"bucket_events": (*state.bucket_events, event)})


def append_auth_bucket_events(
    state: WorkflowState,
    events: tuple[tuple[str, str], ...],
) -> WorkflowState:
    """Append workflow events in their supplied order."""
    updated = state
    for action, object_id in events:
        updated = append_auth_bucket_event(updated, action=action, object_id=object_id)
    return updated
