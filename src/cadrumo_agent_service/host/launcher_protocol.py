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

from .controller import AgentHostError, AgentHostRefusal

LAUNCHER_LANE: Final = "development"
"""The one lane this launcher serves today: an agent run from its source tree."""


class AgentLauncherRefusal(StrEnum):
    """The launcher protocol's closed refusal codes."""

    SIGNED_OUT = "agent_signed_out"
    RUNTIME_UNAVAILABLE = "agent_runtime_unavailable"
    SERVICE_ABSENT = "agent_service_absent"
    SERVICE_INCOMPATIBLE = "agent_service_incompatible"
    PROVIDER_CREDENTIAL_MISSING = "agent_provider_credential_missing"
    ROOT_UNMARKED = "agent_root_unmarked"
    SERVICE_FAILED = "agent_service_failed"


class AgentStoppedReason(StrEnum):
    """Why a served agent stopped, as the launcher reports it."""

    INPUT_CLOSED = "input_closed"
    SESSION_ENDED = "session_ended"
    RUNTIME_UNAVAILABLE = "runtime_unavailable"


# Hosting-protocol refusal codes that mean this agent build does not speak the
# contract the service offered; every other agent refusal is a failure to serve.
_INCOMPATIBLE_AGENT_CODES: Final = frozenset({"frame_malformed", "frame_too_large", "provider_unsupported"})


def launcher_refusal_for(error: AgentHostError) -> AgentLauncherRefusal:
    """Map a hosting-protocol refusal onto the launcher protocol's closed codes."""
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
