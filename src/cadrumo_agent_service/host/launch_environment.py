"""The environment the service composes for its gateway: system values and launch slots.

The agent's credentials travel only on its standard-input frame. Its environment
is built from an allow-list rather than by clearing names from the service's
own, because a cleared list cannot know every provider's variable: an inherited
a provider key or ``AWS_SECRET_ACCESS_KEY`` would otherwise reach the
agent and every process it starts.

The service fills the gateway's launch slots: the hosted root, the two ports
and the admitted runtime's storage root, which the agent forwards to the programs it
starts so that they serve the runtime's root and never resolve a default of
their own. It also tells the agent, in plain variables, what Cadrumo supplies:
the programs the agent may run, the tool server it may mount with its
arguments, the directories of Cadrumo's skills and rules, and the
names it forwards. The agent reads those variables; Cadrumo keeps no list of the
agent's providers or lanes, and the agent reads each tool's trust from the tool
server's own declarations. In a package the agent image's host defines the rest
of the gateway's environment, its search path included, from the image's launch
profile.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import Final

from cadrumo.core.storage_environment import (
    STORAGE_ROOT,
    ChildEnvironmentProfile,
    child_environment,
    normalize_storage_path,
)
from cadrumo_harness.mcp.surfaces import DEFAULT_MCP_SURFACE

HOSTED_ROOT_VARIABLE: Final = "CADRUMO_AGENT_HOSTED_ROOT"
GATEWAY_PORT_VARIABLE: Final = "CADRUMO_AGENT_PORT"
WORKER_PORT_VARIABLE: Final = "CADRUMO_AGENT_WORKER_PORT"
AGENT_LOG_LEVEL_VARIABLE: Final = "CADRUMO_AGENT_LOG_LEVEL"
DIAGNOSTIC_VARIABLES: Final = frozenset({AGENT_LOG_LEVEL_VARIABLE})
"""Capture agent diagnostics independently of the operator view filter."""

AGENT_SLOTS: Final = frozenset({HOSTED_ROOT_VARIABLE, GATEWAY_PORT_VARIABLE, WORKER_PORT_VARIABLE})
"""The agent's own launch parameters the service fills."""
GATEWAY_SLOTS: Final = AGENT_SLOTS | {STORAGE_ROOT.variable}
"""Every launch slot the service fills for the gateway."""

PROGRAM_AEAT_VARIABLE: Final = "CADRUMO_AGENT_PROGRAM_AEAT"
"""The absolute path of the ``aeat`` command line the agent may run."""
PROGRAM_PYTHON_VARIABLE: Final = "CADRUMO_AGENT_PROGRAM_PYTHON"
"""The absolute path of the package's Python interpreter the agent may run."""
TOOL_SERVER_VARIABLE: Final = "CADRUMO_AGENT_TOOL_SERVER_CADRUMO"
"""The absolute path of the ``cadrumo-mcp`` tool server the agent may mount."""
TOOL_SERVER_ARGUMENTS_VARIABLE: Final = "CADRUMO_AGENT_TOOL_SERVER_ARGS_CADRUMO"
"""The JSON array of arguments the agent gives that tool server."""
SKILLS_DIRECTORY_VARIABLE: Final = "CADRUMO_AGENT_SKILLS_DIR"
"""The directory of Cadrumo's agent skills."""
RULES_DIRECTORY_VARIABLE: Final = "CADRUMO_AGENT_RULES_DIR"
"""The directory of Cadrumo's agent rules."""
FORWARD_VARIABLE: Final = "CADRUMO_AGENT_FORWARD"
"""The comma-separated names the agent forwards to the tool servers and programs it starts."""
ADVERTISED_VARIABLES: Final = frozenset(
    {
        PROGRAM_AEAT_VARIABLE,
        PROGRAM_PYTHON_VARIABLE,
        TOOL_SERVER_VARIABLE,
        TOOL_SERVER_ARGUMENTS_VARIABLE,
        SKILLS_DIRECTORY_VARIABLE,
        RULES_DIRECTORY_VARIABLE,
        FORWARD_VARIABLE,
    }
)
"""What the service advertises to the gateway under the agent's prefix."""

_AGENT_DATA: Final = ("_data", "agent")


def _agent_data_directory(name: str) -> Path:
    """Return the absolute directory of the harness's packaged agent material ``name``."""
    root = resources.files("cadrumo_harness")
    return Path(str(root.joinpath(*_AGENT_DATA, name))).resolve()


# Values the operating system and the interpreter need to run at all. None of
# them can carry a credential.
_WINDOWS_NAMES: Final = frozenset(
    {
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "PATHEXT",
        "NUMBER_OF_PROCESSORS",
        "PROCESSOR_ARCHITECTURE",
        "OS",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "APPDATA",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "COMMONPROGRAMFILES",
        "USERNAME",
        "USERDOMAIN",
        "PATH",
    }
)
_POSIX_NAMES: Final = frozenset({"HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "PATH"})


def system_environment(received: Mapping[str, str], *, sys_platform: str | None = None) -> dict[str, str]:
    """Return only the allow-listed operating-system values of ``received``; none can carry a credential."""
    platform = sys.platform if sys_platform is None else sys_platform
    names = _WINDOWS_NAMES if platform == "win32" else _POSIX_NAMES
    if platform == "win32":
        folded = {name.upper(): value for name, value in received.items()}
        return {name: folded[name] for name in names if name in folded}
    return {name: received[name] for name in names if name in received}


def agent_launch_environment(
    *,
    storage_root: Path,
    agent_root: Path,
    relay: Path,
    aeat: Path | None,
    python: Path | None,
    received: Mapping[str, str],
    sys_platform: str | None = None,
) -> dict[str, str]:
    """Return the gateway's whole environment: allow-listed system values, the pinned root and the gateway slots.

    ``agent_root`` is the profile's opaque agent directory that Cadrumo derived;
    the agent receives that one path and no profile identity. ``relay`` is the
    ``cadrumo-mcp`` tool server a hosted run mounts, ``aeat`` the command line and
    ``python`` the interpreter the agent may run. Either is ``None`` when only a
    virtual environment holds it, because the agent refuses to run a program there. The pinned storage root reaches
    the gateway, and the agent forwards it to the programs and tool servers it starts.
    """
    platform = sys.platform if sys_platform is None else sys_platform
    base = system_environment(received, sys_platform=platform)
    environment = child_environment(
        ChildEnvironmentProfile.STRICT, storage_root, received=received, base=base, sys_platform=platform
    )
    environment[STORAGE_ROOT.variable] = str(normalize_storage_path(storage_root))
    environment[HOSTED_ROOT_VARIABLE] = str(agent_root)
    # The agent binds ephemeral ports and reports the real one on its ready line.
    environment[GATEWAY_PORT_VARIABLE] = "0"
    environment[WORKER_PORT_VARIABLE] = "0"
    # Keep DEBUG available in the application viewer. An explicit agent override
    # can reduce producer output without changing the app's INFO default view.
    level = next(
        (value for name, value in received.items() if name.upper() == AGENT_LOG_LEVEL_VARIABLE), "debug"
    ).lower()
    environment[AGENT_LOG_LEVEL_VARIABLE] = (
        level if level in {"debug", "info", "warning", "error", "critical"} else "debug"
    )
    if aeat is not None:
        environment[PROGRAM_AEAT_VARIABLE] = str(aeat)
    if python is not None:
        environment[PROGRAM_PYTHON_VARIABLE] = str(python)
    environment[TOOL_SERVER_VARIABLE] = str(relay)
    environment[TOOL_SERVER_ARGUMENTS_VARIABLE] = json.dumps(["--surface", DEFAULT_MCP_SURFACE.value])
    environment[SKILLS_DIRECTORY_VARIABLE] = str(_agent_data_directory("skills"))
    environment[RULES_DIRECTORY_VARIABLE] = str(_agent_data_directory("rules"))
    environment[FORWARD_VARIABLE] = ",".join([STORAGE_ROOT.variable])
    return environment
