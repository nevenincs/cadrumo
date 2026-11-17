"""Sign one cli lane's provider out through the logout the bundled agent declares for it.

Only the agent signs a provider out: the service runs the agent's own logout
and never opens a provider home. A lane whose catalogue entry declares no
logout cannot be signed out from the window, so the act is refused before
anything runs. Every refusal is logged with its closed cause and served with
the reference of that log line.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .adapters.agent_provider_auth_status import AgentProviderAuthStatusProbe
from .host.sign_in_refusal import refuse
from .providers.application.contracts import ProviderSettingsRefusal, ServiceRefusalCode
from .providers.application.ports import ProviderCatalogSource
from .providers.application.service import ProviderSettingsService
from .providers.domain.catalog import ProviderCatalogEntry


class ProviderSignOutError(Exception):
    """The agent's logout did not sign the provider out; it carries no provider output."""


def signed_out_refusal(action: str) -> dict[str, Any]:
    """Refuse ``action`` for a signed-out profile; a refused sign-out reaches the person, so it is logged."""
    if action == "sign_out":
        return refuse(ServiceRefusalCode.SIGNED_OUT, cause="profile_signed_out")
    return {"kind": "refused", "code": "signed_out"}


def answer_sign_out(
    *,
    lane: str,
    expected_revision: str,
    catalog: ProviderCatalogSource,
    providers: ProviderSettingsService,
    login_context: Callable[[], tuple[Path, str] | None],
    login_status: AgentProviderAuthStatusProbe,
    forget: Callable[[], None],
) -> dict[str, Any]:
    """Run the agent's logout for ``lane`` and answer with its refreshed entry, or a logged refusal.

    ``login_context`` names the signed-in profile's agent root, ``None`` when no
    profile is signed in or a sign-in attempt holds it; ``login_status`` runs the
    agent's logout there; ``forget`` drops every kept read, so the entry served
    afterwards is read fresh.
    """
    try:
        entry = catalog.catalog().entry(lane)
    except Exception as error:
        return refuse(ServiceRefusalCode.SERVICE_FAILED, cause="settings_change_failed", provider=lane, error=error)
    if entry is None or not entry.logout:
        return refuse(ServiceRefusalCode.SIGN_IN_UNAVAILABLE, cause="lane_not_signable", provider=lane)
    context = login_context()
    if context is None:
        return refuse(ServiceRefusalCode.SIGNED_OUT, cause="profile_signed_out", provider=lane)
    root = context[0]

    def signed_out(target: ProviderCatalogEntry) -> None:
        succeeded = login_status.log_out(target.provider, root=root)
        forget()
        if not succeeded:
            raise ProviderSignOutError

    try:
        result = providers.sign_out(lane, expected_revision=expected_revision, log_out=signed_out)
    except Exception as error:
        return refuse(ServiceRefusalCode.SERVICE_FAILED, cause="settings_change_failed", provider=lane, error=error)
    if isinstance(result, ProviderSettingsRefusal):
        dumped = result.model_dump(mode="json")
        return refuse(dumped["code"], cause="settings_refused", provider=lane, base=dumped)
    return result.model_dump(mode="json")


__all__ = ["ProviderSignOutError", "answer_sign_out", "signed_out_refusal"]
