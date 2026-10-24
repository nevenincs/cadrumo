"""CLI text line for a refusal recovered by setting up a missing component.

A refused feature that needs the browser or the local AI carries a verdict
naming that item's setup action. Text output shows the person the exact command
the live command tree resolved for the action, under the setup wording the
provisioning report already uses, instead of the action's condition and
evidence fields. JSON output keeps the typed action record.
"""

from __future__ import annotations

from ...core.i18n.render import tr
from ...core.json_contract import ResolvedPreconditionAction


def _setup_command(action: ResolvedPreconditionAction | None) -> str | None:
    """Return the exact command of an action that sets up a missing component.

    Only the recovery action a setup item declares qualifies, and only once the
    live command tree resolved its full path with nothing left to supply, so the
    printed command is the one that runs.
    """
    if action is None or action.action is None or action.action.cli_path is None:
        return None
    arguments = action.action.arguments
    if action.argument_bindings or (arguments is not None and len(arguments) > 0):
        return None
    from ...application.dependency_registry import dependency_item_declarations

    setup_actions = {declaration.recovery_action_id for declaration in dependency_item_declarations()}
    if action.action.action_id not in setup_actions:
        return None
    return " ".join(action.action.cli_path)


def component_setup_line(action: ResolvedPreconditionAction | None) -> str | None:
    """Return the localized setup line for a component setup action, or ``None`` for any other action."""
    command = _setup_command(action)
    return None if command is None else tr("cli.config.provision.fix", command=command)


__all__ = ["component_setup_line"]
