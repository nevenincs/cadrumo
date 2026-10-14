"""The launcher protocol: between the desktop host and ``aeat app agent serve``.

Two protocols meet at the agent, and each has its own vocabulary:

* The **hosting protocol** runs between the runtime and cadrumo-agent. The
  runtime writes one credential frame on the agent's standard input and reads
  one line back, ``agent_ready`` or ``refused`` with one of the agent's five
  codes (:mod:`.controller` owns it).
* The **launcher protocol**, declared here, runs between the desktop host and
  the thin client ``aeat app agent serve``. The client reads one bearer line on
  its standard input and writes JSON lines on its standard output:
  ``agent_ready``, ``agent_refused`` with one of the seven codes below, and
  ``agent_stopped``.

The launcher never sees a provider credential: the runtime resolves it and
writes it only into the hosting protocol's frame.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from .controller import AgentHostError, AgentHostRefusal

LAUNCHER_LANE: Final = "development"
"""The one lane this launcher serves today: an agent run from its source tree."""

HOSTED_ASSISTANT_PROVIDERS: Final[tuple[str, ...]] = ("claude_api", "claude_cli")
"""The catalog lanes hosting contract 1 admits for a hosted gateway: Claude by key and by token.

cadrumo-agent's hosting contract owns this list; listing a lane in the
profile's settings does not widen it. Only these lanes' credentials are ever
resolved for the frame, and only an API key is written into it, keyed by the
catalog's ``agent_credential_id``: a lane's token or provider-owned sign-in
contributes nothing.
"""


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
# contract the runtime offered; every other agent refusal is a failure to serve.
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
