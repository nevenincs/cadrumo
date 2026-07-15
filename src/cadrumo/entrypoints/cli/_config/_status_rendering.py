"""Pure result construction for configuration-status refusal states."""

from __future__ import annotations

from .._config_payloads import ConfigStatusResult


def unavailable_profile_record_status(
    *,
    active_profile: str | None,
    status: str,
    profile_record_error: str | None,
    next_action: str | None,
) -> tuple[ConfigStatusResult, tuple[str, ...]]:
    """Build the stable payload and text rows for an unavailable profile record."""
    result = ConfigStatusResult(
        active_profile=active_profile,
        registered_profile=True,
        profile_record_present=False,
        configured=False,
        profile_record_error=profile_record_error,
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
    lines.append(f"next_action\t{next_action}")
    return result, tuple(lines)


__all__ = ["unavailable_profile_record_status"]
