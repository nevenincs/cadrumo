"""Rich + JSON emitters for the ``aeat auth`` CLI.

Rendering is isolated from control flow so the ``status`` and
``list-providers`` surfaces stay easy to unit-test against a
deterministic ``now``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from rich.table import Table

from ...auth import AEAT_SESSION_IDLE_TTL

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ...auth import AuthProviderDescription
    from ...config import Settings
    from ._registry import ProviderRegistryEntry
    from ._session import PersistedAuthSession


def _format_status(description: AuthProviderDescription, entry: ProviderRegistryEntry) -> str:
    if not entry.implemented:
        return "not yet implemented"
    if description.configured and description.available:
        return "configured, healthy"
    if description.configured and not description.available:
        return "configured, unavailable"
    return "available, not configured"


def _format_identity(description: AuthProviderDescription) -> str:
    if description.identity_nif:
        return description.identity_nif
    return "—"


def _format_expires(description: AuthProviderDescription) -> str:
    if description.expires_on is None:
        return "—"
    return description.expires_on.isoformat()


def _format_health(description: AuthProviderDescription) -> str:
    parts: list[str] = []
    if description.health_severity:
        parts.append(description.health_severity)
    if description.days_until_expiry is not None:
        parts.append(f"{description.days_until_expiry}d")
    if description.health_summary and description.health_summary not in parts:
        parts.append(description.health_summary)
    return " · ".join(parts) if parts else "—"


def render_list_providers_table(
    rows: Iterable[tuple[ProviderRegistryEntry, AuthProviderDescription]],
) -> Table:
    """Build the Rich table used by ``aeat auth list-providers``."""
    table = Table(title="AEAT auth providers", show_lines=False)
    table.add_column("PROVIDER", no_wrap=True)
    table.add_column("STATUS")
    table.add_column("IDENTITY")
    table.add_column("EXPIRES")
    table.add_column("HEALTH")
    for entry, description in rows:
        table.add_row(
            entry.label,
            _format_status(description, entry),
            _format_identity(description),
            _format_expires(description),
            _format_health(description),
        )
    return table


def render_list_providers_json(
    rows: Iterable[tuple[ProviderRegistryEntry, AuthProviderDescription]],
) -> list[dict[str, Any]]:
    """Produce the JSON payload for ``aeat auth list-providers --json``."""
    dumped: list[dict[str, Any]] = []
    for entry, description in rows:
        payload = description.model_dump(mode="json")
        payload["implemented"] = entry.implemented
        dumped.append(payload)
    return dumped


def _relative_minutes(moment: datetime, now: datetime) -> int:
    """Whole minutes between two datetimes, rounded toward zero."""
    delta_s = (now - moment).total_seconds()
    return int(delta_s // 60)


def render_status_line(session: PersistedAuthSession, now: datetime | None = None) -> str:
    """Render Kent's one-line human status string."""
    current = now or datetime.now(UTC)
    if session.is_expired(current):
        expired_ago = _relative_minutes(session.idle_deadline, current)
        return f"session expired {expired_ago}m ago; run `aeat auth login`"

    authenticated_ago = max(0, _relative_minutes(session.authenticated_at, current))
    remaining = max(timedelta(0), session.idle_deadline - current)
    remaining_minutes = int(remaining.total_seconds() // 60)
    return (
        f"active provider: {session.provider_kind.value} · "
        f"authenticated {authenticated_ago}m ago · "
        f"{remaining_minutes}m remaining before idle timeout · "
        f"identity {session.identity_nif}"
    )


def render_status_json(session: PersistedAuthSession, now: datetime | None = None) -> dict[str, Any]:
    """Render the status-JSON payload, including derived TTL fields."""
    current = now or datetime.now(UTC)
    payload = session.model_dump(mode="json")
    payload["is_expired"] = session.is_expired(current)
    remaining = max(timedelta(0), session.idle_deadline - current)
    payload["seconds_remaining"] = int(remaining.total_seconds())
    payload["idle_ttl_seconds"] = int(AEAT_SESSION_IDLE_TTL.total_seconds())
    return payload


def render_no_session_line(settings: Settings) -> str:
    """Render the friendly no-op line used by status/logout when no session exists."""
    del settings  # unused but kept for future per-provider messaging
    return "no active session; run `aeat auth login` to authenticate"
