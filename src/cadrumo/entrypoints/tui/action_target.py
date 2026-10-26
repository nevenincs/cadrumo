"""The check every injected workspace action passes before it is wired to a surface."""

from __future__ import annotations

from ...application.operator_actions.catalogue import lookup_action
from ...application.operator_actions.models import ActionReference


def require_action_target(action: ActionReference, command_key: str, refusal: str) -> None:
    """Refuse an injected action whose catalogue entry targets a command other than ``command_key``.

    Raises:
        ValueError: ``refusal``, when the action resolves to a different command.
    """
    if lookup_action(action.action_id).target_command_key != command_key:
        raise ValueError(refusal)
