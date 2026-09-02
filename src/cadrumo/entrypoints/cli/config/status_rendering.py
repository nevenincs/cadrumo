"""Pure result construction for configuration-status refusal states."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..config_payloads import ConfigStatusResult

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from ....core.json_contract import ResolvedPreconditionAction


def unavailable_profile_record_status(
    *,
    active_profile: str | None,
    status: str,
    profile_record_error: str | None,
    precondition_action: ResolvedPreconditionAction | None,
) -> tuple[ConfigStatusResult, tuple[str, ...]]:
    """Build the stable payload and text rows for an unavailable profile record."""
    result = ConfigStatusResult(
        active_profile=active_profile,
        registered_profile=True,
        profile_record_present=False,
        configured=False,
        profile_record_error=profile_record_error,
        precondition_action=precondition_action,
    )
    record_state = "unreadable" if status == "profile_record_unreadable" else "missing"
    lines = [
        f"profile\t{active_profile}",
        f"readiness\t{status}",
        "registered_profile\tpresent",
        f"profile_record\t{record_state}",
    ]
    if profile_record_error:
        lines.append(f"profile_record_error\t{profile_record_error}")
    lines.extend(precondition_action_lines(precondition_action))
    return result, tuple(lines)


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


def precondition_action_lines(action: ResolvedPreconditionAction | None) -> tuple[str, ...]:
    """Render the exact resolved action DTO without synthesising recovery prose."""
    if action is None:
        return ()
    document = action.model_dump(mode="json")
    fields = (
        "failed_condition_id",
        "evidence",
        "action",
        "argument_bindings",
        "missing_argument_names",
        "conditionality",
        "no_recovery_outcome",
    )
    return tuple(
        f"precondition_action.{field_name}\t"
        f"{json.dumps(document[field_name], ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
        for field_name in fields
    )


def _presence(values: Mapping[str, str], path: str) -> str:
    """Render one fact path as the presence token the status report prints."""
    return "present" if values.get(path) else "missing"


__all__ = ["blocked_readiness_status", "precondition_action_lines", "unavailable_profile_record_status"]
