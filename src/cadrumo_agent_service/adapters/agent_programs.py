"""Locate the service's packaged agent image, advertised programs and private roots.

The native service launch profile fixes absolute packaged program paths. An
explicit marked development lane can select an agent source environment;
installed service launches always use the bundled image. No program is
resolved by a bare name on PATH.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import shutil
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from uuid import UUID

from cadrumo.core.storage_environment import StorageMode, storage_mode

from ..host.launcher_protocol import AgentLauncherRefusal

AGENT_DIRECTORY: Final = "agent"
"""The storage root's directory that holds one opaque directory per profile's agent."""

PACKAGE_AGENT_VARIABLE: Final = "CADRUMO_PACKAGE_AGENT_EXECUTABLE"
"""The bundled agent image fixed in the service image's launch profile."""
PACKAGE_RELAY_VARIABLE: Final = "CADRUMO_PACKAGE_RELAY_EXECUTABLE"
"""The MCP relay fixed in the service image's launch profile."""
PACKAGE_AEAT_VARIABLE: Final = "CADRUMO_PACKAGE_AEAT_EXECUTABLE"
"""The AEAT command image fixed in the service image's launch profile."""
PACKAGE_PYTHON_VARIABLE: Final = "CADRUMO_PACKAGE_PYTHON_EXECUTABLE"
"""The package interpreter fixed in the service image's launch profile."""

_ROOT_KEY_NAME: Final = ".agent-root-key"
_ROOT_KEY_BYTES: Final = 32
_HOSTED_HOME: Final = "home"
"""The directory under a hosted agent's root that the agent treats as its home; the agent fixes this layout."""
_HOSTED_WORKSPACES: Final = "workspaces"
"""The directory under the hosted home that bounds every workspace a run or catalog request may name."""
_HOSTED_WORKSPACE: Final = "cadrumo"
"""The one workspace this service creates inside that boundary."""
_HOSTED_STORES: Final = ("home", "state")
"""The directory under a hosted root that holds the agent's two stores and their write-ahead logs."""
STORES_ASIDE: Final = "stores-aside"
"""The host's copy of the stores, directly under the hosted root: a name the agent's layout leaves to the host."""
_STORES_ASIDE_PARTIAL: Final = "stores-aside.partial"
AGENT_COMMAND_LINE: Final = ("-m", "cadrumo_agent.cli.main")
"""The agent's declared command-line module, which has no package-level ``__main__``; each invocation adds its verb."""
GATEWAY_ARGUMENTS: Final = (*AGENT_COMMAND_LINE, "serve")
"""The gateway invocation."""


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


def _located_program(variable: str, checkout_program: Path | None, received: Mapping[str, str] | None) -> Path:
    """Return the absolute program a package variable names, or the checkout's own; refuse any other install."""
    environment = os.environ if received is None else received
    declared = environment.get(variable)
    if declared is not None:
        program = Path(declared)
    elif storage_mode().mode is StorageMode.DEVELOPMENT and checkout_program is not None:
        program = checkout_program
    else:
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_FAILED)
    if not program.is_absolute() or not program.is_file():
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_FAILED)
    return program


def _checkout_script(name: str, interpreter: Path | None) -> Path:
    python = Path(sys.executable if interpreter is None else interpreter)
    return python.parent / (f"{name}.exe" if sys.platform == "win32" else name)


def hosted_relay(*, received: Mapping[str, str] | None = None, interpreter: Path | None = None) -> Path:
    """Locate the ``cadrumo-mcp`` relay a hosted agent mounts.

    A native package fixes it in the service's environment; a checkout runs it
    from the environment that holds this interpreter. Any other install has no
    relay to name.
    """
    return _located_program(PACKAGE_RELAY_VARIABLE, _checkout_script("cadrumo-mcp", interpreter), received)


def hosted_aeat(*, received: Mapping[str, str] | None = None, interpreter: Path | None = None) -> Path | None:
    """Locate the ``aeat`` command line a hosted agent may run, as :func:`hosted_relay` locates the relay.

    A checkout's command line sits inside its virtual environment, which the
    agent refuses to run as a program; the answer is then ``None``.
    """
    checkout = _checkout_script("aeat", interpreter)
    environment = os.environ if received is None else received
    if PACKAGE_AEAT_VARIABLE not in environment and inside_virtual_environment(checkout):
        return None
    return _located_program(PACKAGE_AEAT_VARIABLE, checkout, received)


def inside_virtual_environment(program: Path) -> bool:
    """Whether the program's folder or any parent holds a ``pyvenv.cfg``, which the agent refuses to run."""
    return (
        any((folder / "pyvenv.cfg").exists() for folder in program.parent.parents)
        or (program.parent / "pyvenv.cfg").exists()
    )


def hosted_python(*, received: Mapping[str, str] | None = None, interpreter: Path | None = None) -> Path | None:
    """Locate the Python interpreter a hosted agent may run: the package's image, or this checkout's interpreter.

    A checkout's interpreter that sits inside a virtual environment is not
    advertised, because the agent refuses such a program; the answer is then
    ``None``. The package's interpreter is never inside one.
    """
    checkout = Path(sys.executable if interpreter is None else interpreter)
    if received is None:
        received = os.environ
    if PACKAGE_PYTHON_VARIABLE not in received and inside_virtual_environment(checkout):
        return None
    return _located_program(PACKAGE_PYTHON_VARIABLE, checkout, received)


def agent_image(agent_source: str | None, *, agent_root: Path, received: Mapping[str, str] | None = None) -> AgentImage:
    """Return how to start the agent gateway: the package's agent image, or a named source tree's environment.

    The installed form runs the bundled ``bin/cadrumo-agent`` image the
    service's environment names, with the gateway invocation, in the agent's
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
    if storage_mode().mode is not StorageMode.DEVELOPMENT:
        raise AgentProgramRefusalError(AgentLauncherRefusal.SERVICE_ABSENT)
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


class HostedStoresAside:
    """The host's one copy of a hosted agent's stores, kept beside them under the same hosted root.

    The copy stays inside the profile's opaque agent root, with the same scope
    and permissions as the stores it copies, and outside the agent's state
    home, its workspaces and the directories the agent empties at start. It is
    written under a partial name and renamed once every file is flushed, so a
    complete copy is never confused with an interrupted one.
    """

    def __init__(self, hosted_root: Path) -> None:
        """Bind the hosted root whose stores this copy is of."""
        self._stores = hosted_root.joinpath(*_HOSTED_STORES)
        self._aside = hosted_root / STORES_ASIDE
        self._partial = hosted_root / _STORES_ASIDE_PARTIAL

    def clear_partial(self) -> None:
        """Remove an unfinished copy left by an interrupted start; no migrate ran after it."""
        if self._partial.exists() or self._partial.is_symlink():
            shutil.rmtree(self._partial)

    def kept(self) -> bool:
        """Whether a complete copy exists."""
        return self._aside.exists() or self._aside.is_symlink()

    def keep(self) -> None:
        """Copy the stores aside, flush every file, and publish the copy under its complete name."""
        if self.kept():
            raise FileExistsError(STORES_ASIDE)
        if not self._stores.is_dir() or self._stores.is_symlink():
            raise NotADirectoryError(_HOSTED_STORES[-1])
        # A link inside the store directory is copied as a link, never followed out of the profile's tree.
        shutil.copytree(self._stores, self._partial, symlinks=True, copy_function=_copy_durably)
        self._partial.rename(self._aside)

    def discard(self) -> None:
        """Remove the complete copy."""
        if self.kept():
            shutil.rmtree(self._aside)


def _copy_durably(source: str, destination: str) -> str:
    copied = shutil.copy2(source, destination)
    with open(copied, "rb+") as handle:
        os.fsync(handle.fileno())
    return str(copied)
