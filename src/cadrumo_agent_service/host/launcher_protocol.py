"""Closed launcher refusals used by the separate agent service's host adapters.

The service's hosting controller starts cadrumo-agent, writes its credential
frame and reads its readiness or refusal. The service owns provider credential
interpretation; the runtime supplies admitted opaque profile custody.

The desktop starts the dedicated ``cadrumo-agent-service serve`` entrypoint.
Its startup, administration and lifecycle frames are defined by the service,
independently of these host-adapter refusal codes.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from .controller import AgentHostError, AgentHostRefusal


class AgentLauncherRefusal(StrEnum):
    """The launcher protocol's closed refusal codes."""

    SIGNED_OUT = "agent_signed_out"
    RUNTIME_UNAVAILABLE = "agent_runtime_unavailable"
    SERVICE_ABSENT = "agent_service_absent"
    SERVICE_INCOMPATIBLE = "agent_service_incompatible"
    PROVIDER_CREDENTIAL_MISSING = "agent_provider_credential_missing"
    SERVICE_FAILED = "agent_service_failed"
    EMERGENCY_CUTOFF = "agent_emergency_cutoff"


# Hosting-protocol refusal codes that mean this agent build does not speak the
# contract the service offered; every other agent refusal is a failure to serve.
_INCOMPATIBLE_AGENT_CODES: Final = frozenset({"frame_malformed", "frame_too_large", "provider_unsupported"})

# Runtime transport refusals that mean no runtime is there to serve the service yet;
# every other runtime refusal, including an untrusted endpoint or peer, is a failure.
_RUNTIME_UNAVAILABLE_CODES: Final = frozenset(
    {RefusalCode.UNAVAILABLE, RefusalCode.ENDPOINT_NOT_READY, RefusalCode.DRAINING}
)


def launcher_refusal_for(error: AgentHostError) -> AgentLauncherRefusal:
    """Map a hosting-protocol refusal onto the launcher protocol's closed codes."""
    if error.reason is AgentHostRefusal.EMERGENCY_CUTOFF:
        return AgentLauncherRefusal.EMERGENCY_CUTOFF
    if error.reason is AgentHostRefusal.SIGNED_OUT or error.reason is AgentHostRefusal.STALE_GENERATION:
        return AgentLauncherRefusal.SIGNED_OUT
    if error.reason in {AgentHostRefusal.CREDENTIALS_UNAVAILABLE, AgentHostRefusal.CREDENTIALS_INVALID}:
        return AgentLauncherRefusal.PROVIDER_CREDENTIAL_MISSING
    if error.reason is AgentHostRefusal.AGENT_REFUSED and error.agent_code in _INCOMPATIBLE_AGENT_CODES:
        return AgentLauncherRefusal.SERVICE_INCOMPATIBLE
    if error.reason in {AgentHostRefusal.AGENT_INCOMPATIBLE, AgentHostRefusal.STORES_NEWER}:
        # A downgrade: the agent build is older than the stores it would serve.
        return AgentLauncherRefusal.SERVICE_INCOMPATIBLE
    # Includes the native host's launch-profile refusal and every store step that did not reach current stores.
    return AgentLauncherRefusal.SERVICE_FAILED


def runtime_launcher_refusal_for(error: RefusalError) -> AgentLauncherRefusal | None:
    """Retain emergency cutoff or runtime unavailability; other runtime refusals have no launcher mapping."""
    if error.reason is RefusalCode.EMERGENCY_CUTOFF:
        return AgentLauncherRefusal.EMERGENCY_CUTOFF
    return AgentLauncherRefusal.RUNTIME_UNAVAILABLE if error.reason in _RUNTIME_UNAVAILABLE_CODES else None
