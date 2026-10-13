"""The runtime door by which a person's session asks for its hosted agent.

The request names no credential and carries no secret field: the gateway
bearer follows on the one secret frame the runtime authorizes after its
preflight, and the provider credentials never leave the runtime's own worker
channel and the agent's standard input.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..agent_host.launcher_protocol import AgentLauncherRefusal

AGENT_SOURCE_MAX_CHARACTERS = 1024


class RuntimeAgentStart(BaseModel):
    """Start the agent bound to this connection's own session.

    ``agent_source`` is the absolute path of a cadrumo-agent source tree: the
    runtime starts the agent from that tree's own environment. ``None`` starts
    the agent packaged with this runtime, under the runtime's own interpreter.
    Neither is a secret. The launcher serves the development lane only, so
    either form runs only on a storage root marked for the lane.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["agent_start"] = "agent_start"
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    agent_source: Annotated[str, Field(min_length=1, max_length=AGENT_SOURCE_MAX_CHARACTERS)] | None = None


class RuntimeAgentStarted(BaseModel):
    """The session's agent is serving; only its loopback port and version leave the runtime."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["agent_started"] = "agent_started"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    gateway_port: Annotated[int, Field(ge=1, le=65535)]
    agent_version: Annotated[str, Field(min_length=1, max_length=64)]
    workspace_root: Annotated[str, Field(min_length=1, max_length=AGENT_SOURCE_MAX_CHARACTERS)]
    """The existing workspace inside the boundary the agent admits, where the session's runs work."""


class RuntimeAgentRefused(BaseModel):
    """The agent is not served, for one of the launcher protocol's closed reasons."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["agent_refused"] = "agent_refused"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    code: AgentLauncherRefusal
