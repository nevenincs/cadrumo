"""Rich + JSON emitters for the ``aeat auth`` CLI.

Rendering is isolated from control flow so the ``status`` and
``list-providers`` surfaces stay easy to unit-test against a
deterministic ``now``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from rich.table import Table

from ....adapters.outbound.aeat.auth import AEAT_SESSION_IDLE_TTL

_CERT_RENEWAL_URL = "https://www.sede.fnmt.gob.es/certificados/persona-fisica/renovar"

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ....application.auth import AuthProviderDescription, AuthProviderKind, PersistedAuthSession
    from ....core.config import Settings
    from ._registry import ProviderRegistryEntry


def _format_status(description: AuthProviderDescription, entry: ProviderRegistryEntry) -> str:
    if description.configured and description.available:
        return "configured, healthy"
    if description.configured and not description.available:
        return "configured, unavailable"
    # The remaining case is "not configured" — there is no sensible
    # "available but not configured" state because every provider's
    # describe() only flags `available=True` when `configured=True`.
    return "not configured"


def _format_identity(description: AuthProviderDescription) -> str:
    if description.identity_nif:
        return description.identity_nif
    return "—"


def _format_expires(description: AuthProviderDescription) -> str:
    if description.expires_on is None:
        return "—"
    return description.expires_on.isoformat()


def _format_health(description: AuthProviderDescription, entry: ProviderRegistryEntry) -> str:
    """Render the HEALTH column as operator-readable prose.

    Providers either supply a prose ``health_summary``
    (Cl@ve Móvil emits "ready — requires push approval on the Cl@ve
    app") that is passed through, or the cert-provider's legacy
    ``"{severity}:{days_until_expiry}"`` sentinel token (e.g.
    ``"CRITICAL:3"``). The sentinel is translated into operator-readable
    copy here, with a renewal URL surfaced on every non-healthy
    certificate severity so the operator always has a next step.
    """
    severity = (description.health_severity or "").upper()
    days = description.days_until_expiry
    summary = description.health_summary or ""

    # Cert provider encodes health as a "SEV:days" sentinel token in
    # health_summary; strip it so we never echo it at the operator.
    # Cl@ve providers emit prose summaries that are passed through
    # untouched.
    if summary and ":" in summary and summary.split(":", 1)[0].upper() == severity:
        summary = ""

    if severity == "EXPIRED" and days is not None:
        return f"certificate expired {abs(days)}d ago — renew at {_CERT_RENEWAL_URL}"
    if severity == "CRITICAL" and days is not None and days >= 0:
        return f"certificate expires in {days}d — renew soon at {_CERT_RENEWAL_URL}"
    if severity == "WARN" and days is not None and days >= 0:
        return f"certificate expires in {days}d — renew at {_CERT_RENEWAL_URL}"
    if severity == "OK" and days is not None:
        return f"healthy — {days}d until expiry"
    if summary:
        return summary
    return "—"


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
            _format_health(description, entry),
        )
    return table


def render_list_providers_json(
    rows: Iterable[tuple[ProviderRegistryEntry, AuthProviderDescription]],
) -> list[dict[str, Any]]:
    """Produce the JSON payload for ``aeat auth list-providers --json``."""
    dumped: list[dict[str, Any]] = []
    for _entry, description in rows:
        payload = description.model_dump(mode="json")
        dumped.append(payload)
    return dumped


def _relative_minutes(moment: datetime, now: datetime) -> int:
    """Whole minutes between two datetimes, rounded toward zero."""
    delta_s = (now - moment).total_seconds()
    return int(delta_s // 60)


def _provider_label(kind: AuthProviderKind) -> str:
    """Look up the registry label for ``kind`` so output shows e.g. ``Cl@ve Móvil``."""
    # Local import avoids a circular dependency between _render and _registry.
    from . import _registry

    try:
        return _registry.get_entry(kind).label
    except KeyError:
        return kind.value


def render_status_line(session: PersistedAuthSession, now: datetime | None = None) -> str:
    """Render the operator's one-line human status string."""
    current = now or datetime.now(UTC)
    label = _provider_label(session.provider_kind)
    if session.is_expired(current):
        expired_ago = _relative_minutes(session.idle_deadline, current)
        return f"Your {label} session expired {expired_ago}m ago. Run `aeat auth login` to sign in again."

    authenticated_ago = max(0, _relative_minutes(session.authenticated_at, current))
    remaining = max(timedelta(0), session.idle_deadline - current)
    remaining_minutes = int(remaining.total_seconds() // 60)
    return (
        f"Active provider: {label} · "
        f"authenticated {authenticated_ago}m ago · "
        f"expires in {remaining_minutes}m · "
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
    del settings  # Signature stays aligned with other auth renderers.
    return "no active session; run `aeat auth login` to authenticate"
