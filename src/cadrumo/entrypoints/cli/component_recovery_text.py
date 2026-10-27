"""Read-free wording for component actions and already-observed component facts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ...application.dependency_contracts import DEPENDENCY_SETUP_RECOVERIES
from ...application.dependency_registry import BROWSER_DECLARATION, LOCAL_AI_DECLARATION
from ...application.dependency_wording import dependency_desktop_pointer
from ...application.operator_actions.catalogue import lookup_action, next_action
from ...application.operator_surface.action_targets import ACTION_TARGETS
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity

if TYPE_CHECKING:
    from ...core.json_contract import ResolvedPreconditionAction

_ROW_CONDITIONS = frozenset({"preflight.setup.item_usable", "diagnostics.setup.item_usable"})


def component_status_command() -> str:
    """Resolve the canonical status-report command from the operator action catalogue."""
    target_key = lookup_action("operator.provision.status").target_command_key
    target = next(row for row in ACTION_TARGETS if row.command_key == target_key)
    return " ".join((target.program.executable_name, *target.cli_path))


def _recovery_kind(
    action: ResolvedPreconditionAction | None,
) -> Literal["desktop", "blocked", "setup", "status"] | None:
    if action is None:
        return None
    reference = action.action
    action_id = None if reference is None else reference.action_id
    rows = tuple(evidence.values for evidence in action.evidence if evidence.condition_id in _ROW_CONDITIONS)
    local_row = any(row.get("item") == LOCAL_AI_DECLARATION.item_id for row in rows)
    if action_id == LOCAL_AI_DECLARATION.recovery_action_id or local_row:
        return "desktop"
    browser_rows = tuple(row for row in rows if row.get("item") == BROWSER_DECLARATION.item_id)
    if action_id != BROWSER_DECLARATION.recovery_action_id and not browser_rows:
        return None
    if any(row.get("state") == "blocked" and row.get("reason") == "not_in_this_build" for row in browser_rows):
        return "blocked"
    if (
        reference is not None
        and action_id == BROWSER_DECLARATION.recovery_action_id
        and not action.argument_bindings
        and reference.cli_path is not None
        and (reference.arguments is None or len(reference.arguments) == 0)
        and any(
            row.get("state") != "blocked"
            and row.get("recovery") in {item.value for item in DEPENDENCY_SETUP_RECOVERIES}
            for row in browser_rows
        )
    ):
        return "setup"
    return "status"


def component_recovery_lines(action: ResolvedPreconditionAction | None) -> tuple[str, ...] | None:
    """Word component recovery from supplied facts, without making a status read."""
    kind = _recovery_kind(action)
    if kind is None:
        return None
    if kind == "desktop":
        return (dependency_desktop_pointer(),)
    if kind == "blocked":
        return (tr("application.provisioning.blocked.not_in_this_build"),)
    if kind == "setup":
        if action is None or action.action is None or action.action.cli_path is None:
            raise ValueError("component setup requires a resolved command")
        return (tr("cli.config.provision.fix", command=" ".join(action.action.cli_path)),)
    return (tr("cli.config.provision.check_status", command=component_status_command()),)


def component_recovery_notice(action: ResolvedPreconditionAction | None) -> Notice | None:
    """Expose the same guidance through a typed notice without command prose in its message."""
    kind = _recovery_kind(action)
    if kind is None:
        return None
    if kind == "desktop":
        message, target = dependency_desktop_pointer(), None
    elif kind == "blocked":
        message, target = tr("application.provisioning.blocked.not_in_this_build"), None
    elif kind == "setup":
        message, target = tr("application.provisioning.action.set_up"), next_action("operator.provision.browser")
    else:
        message, target = tr("cli.config.provision.status.help"), next_action("operator.provision.status")
    return Notice(severity=NoticeSeverity.INFO, code="config.provision.recovery", message=message, action=target)
