"""Where the runtime finds the agent it hosts, Cadrumo's programs the agent may start, and the agent's root.

Every path is located, never spelled by a caller: in a native package from the
package inventory the runtime's own interpreter carries, and in a checkout from
the checkout's environment. Nothing here is looked up by bare name on ``PATH``.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from uuid import UUID

from ...application.agent_host.launch_environment import AgentHostedPrograms
from ...application.agent_host.launcher_protocol import AgentLauncherRefusal
from ...core.storage_environment import StorageMode, storage_mode
from .boot_record import runtime_package_directory

AGENT_DIRECTORY: Final = "agent"
"""The storage root's directory that holds one opaque directory per profile's agent."""

_ROOT_KEY_NAME: Final = ".agent-root-key"
_ROOT_KEY_BYTES: Final = 32
_PACKAGE_MANIFEST: Final = ("data", "package-manifest.json")
_AGENT_MODULE: Final = "cadrumo_agent"


class AgentProgramRefusalError(Exception):
    """The agent or one of the programs it needs cannot be located; carries only a launcher code."""

    def __init__(self, code: AgentLauncherRefusal) -> None:
        """Keep the closed launcher code."""
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True, slots=True)
class AgentImage:
    """The program that runs the agent, and the directory it starts in."""

    executable: Path
    arguments: tuple[str, ...]
    directory: Path


def hosted_programs(*, interpreter: Path | None = None) -> AgentHostedPrograms:
    """Locate the ``cadrumo-mcp`` relay this runtime runs beside: the only Cadrumo program the agent may start.

    A native package names its console entrypoints in its own inventory; a
    checkout runs them from the environment that holds this interpreter.
    """
    python = Path(sys.executable if interpreter is None else interpreter)
    mode = storage_mode().mode
    package = runtime_package_directory(python, mode=mode)
    if package is not None:
        relay = _package_relay(Path(package))
    elif mode is StorageMode.DEVELOPMENT:
        relay = python.parent / ("cadrumo-mcp.exe" if sys.platform == "win32" else "cadrumo-mcp")
    else:
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_FAILED)
    if not relay.is_absolute() or not relay.is_file():
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_FAILED)
    return AgentHostedPrograms(relay=relay)


def _package_relay(package: Path) -> Path:
    """Map the declared ``cadrumo-mcp`` entrypoint through the package's own inventory."""
    try:
        manifest = json.loads(package.joinpath(*_PACKAGE_MANIFEST).read_text(encoding="utf-8"))
        layout = manifest["layout"]
        startup = set(manifest["startup_files"])
        native, suffix, declared = layout["paths"]["native"], layout["entrypoint_suffix"], layout["entrypoints"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_FAILED) from error
    relative = f"{native}/cadrumo-mcp{suffix}"
    if "cadrumo-mcp" not in declared or relative not in startup:
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_FAILED)
    return package / relative


def agent_image(agent_source: str | None, *, agent_root: Path) -> AgentImage:
    """Return how to start the agent: from a source tree's environment, or bundled in this package.

    The development lane names an absolute cadrumo-agent source tree, and the
    agent runs from that tree's own environment. The installed form runs the
    agent package bundled beside this runtime with this runtime's interpreter.
    """
    if agent_source is None:
        if importlib.util.find_spec(_AGENT_MODULE) is None:
            raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_ABSENT)
        return AgentImage(Path(sys.executable), ("-m", _AGENT_MODULE, "serve"), agent_root)
    source = Path(agent_source)
    if not source.is_absolute():
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_ABSENT)
    interpreter = (
        source / ".venv" / "Scripts" / "python.exe" if sys.platform == "win32" else source / ".venv" / "bin" / "python"
    )
    if not source.is_dir() or not interpreter.is_file():
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_ABSENT)
    return AgentImage(interpreter, ("-m", _AGENT_MODULE, "serve"), source)


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
    workspace = agent_root / "home" / "workspaces" / "cadrumo"
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
