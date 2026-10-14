"""Where the runtime finds the agent image it hosts, the relay the agent mounts, and the agent's root.

Every path is located, never spelled by a caller. In a native package the
runtime image's launch profile fixes the agent image and the relay as package
values in the runtime's own environment; the runtime reads no package file. In
a checkout the relay runs from the checkout's environment, and the agent only
from a source tree the development lane names. Nothing here is looked up by
bare name on ``PATH``.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from uuid import UUID

from ...application.agent_host.launcher_protocol import AgentLauncherRefusal
from ...core.storage_environment import StorageMode, storage_mode

AGENT_DIRECTORY: Final = "agent"
"""The storage root's directory that holds one opaque directory per profile's agent."""

PACKAGE_AGENT_VARIABLE: Final = "CADRUMO_PACKAGE_AGENT_EXECUTABLE"
"""The package value naming the bundled agent image, ``bin/cadrumo-agent``, fixed in the runtime image's profile."""
PACKAGE_RELAY_VARIABLE: Final = "CADRUMO_PACKAGE_RELAY_EXECUTABLE"
"""The package value naming the ``cadrumo-mcp`` relay, fixed in the runtime image's profile."""

_ROOT_KEY_NAME: Final = ".agent-root-key"
_ROOT_KEY_BYTES: Final = 32
_HOSTED_HOME: Final = "home"
"""The directory under a hosted agent's root that the agent treats as its home; the agent fixes this layout."""
_HOSTED_WORKSPACES: Final = "workspaces"
"""The directory under the hosted home that bounds every workspace a run or catalog request may name."""
_HOSTED_WORKSPACE: Final = "cadrumo"
"""The one workspace this runtime creates inside that boundary."""
GATEWAY_ARGUMENTS: Final = ("-m", "cadrumo_agent.cli.main", "serve")
"""The gateway invocation: the agent's declared command-line module, which has no package-level ``__main__``."""


class AgentProgramRefusalError(Exception):
    """The agent or one of the programs it needs cannot be located; carries only a launcher code."""

    def __init__(self, code: AgentLauncherRefusal) -> None:
        """Keep the closed launcher code."""
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True, slots=True)
class AgentImage:
    """The program that runs the agent gateway, its arguments, and the directory it starts in."""

    executable: Path
    arguments: tuple[str, ...]
    directory: Path


def hosted_relay(*, received: Mapping[str, str] | None = None, interpreter: Path | None = None) -> Path:
    """Locate the ``cadrumo-mcp`` relay a hosted agent mounts.

    A native package fixes it in the runtime's environment; a checkout runs it
    from the environment that holds this interpreter. Any other install has no
    relay to name.
    """
    environment = os.environ if received is None else received
    declared = environment.get(PACKAGE_RELAY_VARIABLE)
    if declared is not None:
        relay = Path(declared)
    elif storage_mode().mode is StorageMode.DEVELOPMENT:
        python = Path(sys.executable if interpreter is None else interpreter)
        relay = python.parent / ("cadrumo-mcp.exe" if sys.platform == "win32" else "cadrumo-mcp")
    else:
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_FAILED)
    if not relay.is_absolute() or not relay.is_file():
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_FAILED)
    return relay


def agent_image(agent_source: str | None, *, agent_root: Path, received: Mapping[str, str] | None = None) -> AgentImage:
    """Return how to start the agent gateway: the package's agent image, or a named source tree's environment.

    The installed form runs the bundled ``bin/cadrumo-agent`` image the
    runtime's environment names, with the gateway invocation, in the agent's
    root. Outside a package there is no bundled agent. The development lane
    names an absolute cadrumo-agent source tree instead, and the agent runs
    from that tree's own environment.
    """
    if agent_source is None:
        environment = os.environ if received is None else received
        declared = environment.get(PACKAGE_AGENT_VARIABLE)
        if declared is None:
            raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_ABSENT)
        image = Path(declared)
        if not image.is_absolute() or not image.is_file():
            raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_FAILED)
        return AgentImage(image, GATEWAY_ARGUMENTS, agent_root)
    source = Path(agent_source)
    if not source.is_absolute():
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_ABSENT)
    interpreter = (
        source / ".venv" / "Scripts" / "python.exe" if sys.platform == "win32" else source / ".venv" / "bin" / "python"
    )
    if not source.is_dir() or not interpreter.is_file():
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_ABSENT)
    return AgentImage(interpreter, GATEWAY_ARGUMENTS, source)


def profile_agent_root(storage_root: Path, profile_id: UUID) -> Path:
    """Return, creating it, the profile's opaque agent directory under the storage root.

    The directory name is a keyed digest of the profile identifier under a
    random key kept at this storage root, so it neither reveals nor can be
    recomputed from the profile identifier alone.
    """
    base = storage_root / AGENT_DIRECTORY
    base.mkdir(exist_ok=True)
    opaque = hmac.new(_root_key(base), b"cadrumo.agent-root.v1\0" + profile_id.bytes, hashlib.sha256).hexdigest()
    root = base / opaque[:32]
    root.mkdir(exist_ok=True)
    return root


def profile_agent_workspace(agent_root: Path) -> Path:
    """Return, creating it, the profile's one workspace inside the boundary a hosted agent admits.

    A hosted agent derives its workspace boundary from its hosted root alone,
    as ``<root>/home/workspaces``; a run or catalog request names a directory
    that exists inside it.
    """
    workspace = agent_root / _HOSTED_HOME / _HOSTED_WORKSPACES / _HOSTED_WORKSPACE
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve(strict=True)


def _root_key(base: Path) -> bytes:
    path = base / _ROOT_KEY_NAME
    try:
        with path.open("xb") as handle:
            key = secrets.token_bytes(_ROOT_KEY_BYTES)
            handle.write(key)
            return key
    except FileExistsError:
        key = path.read_bytes()
    if len(key) != _ROOT_KEY_BYTES:
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_FAILED)
    return key
