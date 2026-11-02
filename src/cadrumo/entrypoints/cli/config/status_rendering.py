"""Pure result construction for configuration-status refusal states."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cadrumo_client.commands.output import precondition_action_lines
from cadrumo_client.commands.payloads import ConfigStatusResult

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from ....core.json_contract import ResolvedPreconditionAction


def blocked_readiness_status(
    *,
    active_profile: str | None,
    profile_id: str | None,
    values: Mapping[str, str],
    precondition_action: ResolvedPreconditionAction | None,
    missing_required: Sequence[str] = (),
) -> tuple[ConfigStatusResult, tuple[str, ...]]:
    """Build the payload and rows for a registered profile that is not filing-ready.

    Both blocked rungs — the profile whose wizard is incomplete, and the one
    missing the modelo filing baseline — report the same readiness token and
    the same two baseline facts, and were two hand-kept-in-step copies of the
    same rendering. ``missing_required`` is the incomplete rung's extra
    per-path rows; the two rungs still differ in whether the payload carries
    ``profile_id`` and a typed precondition action, so those stay explicit.
    """
    result = ConfigStatusResult(
        active_profile=active_profile,
        profile_id=profile_id,
        tax_id_present=bool(values.get("identity.tax_id")),
        activity_present=bool(values.get("activities.description")),
        configured=False,
        precondition_action=precondition_action,
    )
    lines = [
        f"profile\t{active_profile}",
        "readiness\tblocked",
        f"identity.tax_id\t{_presence(values, 'identity.tax_id')}",
        f"activities.description\t{_presence(values, 'activities.description')}",
    ]
    lines.extend(f"{path}\tmissing" for path in missing_required)
    lines.extend(precondition_action_lines(precondition_action))
    return result, tuple(lines)


def _presence(values: Mapping[str, str], path: str) -> str:
    """Render one fact path as the presence token the status report prints."""
    return "present" if bool(values.get(path)) else "missing"


__all__ = ["blocked_readiness_status"]
