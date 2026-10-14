"""The environment the runtime composes for the agent gateway it starts: named system values and its launch slots.

The agent's credentials travel only on its standard-input frame. Its environment
is built from an allow-list rather than by clearing names from the runtime's
own, because a cleared list cannot know every provider's variable: an inherited
``ANTHROPIC_API_KEY`` or ``AWS_SECRET_ACCESS_KEY`` would otherwise reach the
agent and every process it starts.

The runtime fills only the gateway's launch slots: the hosted root, the two
ports, the relay and the runtime's own storage root, which the gateway forwards
to the relay so that the relay serves the runtime's root and never resolves a
default of its own. In a package the agent image's host defines the rest of the
gateway's environment, its search path included, from the image's launch
profile.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from ...core.storage_environment import (
    STORAGE_ROOT,
    ChildEnvironmentProfile,
    child_environment,
    normalize_storage_path,
)

HOSTED_ROOT_VARIABLE: Final = "CADRUMO_AGENT_HOSTED_ROOT"
GATEWAY_PORT_VARIABLE: Final = "CADRUMO_AGENT_PORT"
WORKER_PORT_VARIABLE: Final = "CADRUMO_AGENT_WORKER_PORT"
HOSTED_RELAY_VARIABLE: Final = "CADRUMO_AGENT_HOSTED_RELAY_EXECUTABLE"
"""The absolute path of the ``cadrumo-mcp`` relay a hosted run mounts."""

AGENT_SLOTS: Final = frozenset(
    {HOSTED_ROOT_VARIABLE, GATEWAY_PORT_VARIABLE, WORKER_PORT_VARIABLE, HOSTED_RELAY_VARIABLE}
)
"""The agent's own settings the runtime supplies; it supplies no other name under the agent's prefix."""
GATEWAY_SLOTS: Final = AGENT_SLOTS | {STORAGE_ROOT.variable}
"""Every value the runtime supplies to the gateway: exactly the gateway's declared launch slots."""


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
    received: Mapping[str, str],
    sys_platform: str | None = None,
) -> dict[str, str]:
    """Return the gateway's whole environment: allow-listed system values, the pinned root and the gateway slots.

    ``agent_root`` is the profile's opaque agent directory that Cadrumo derived;
    the agent receives that one path and no profile identity. ``relay`` is the
    ``cadrumo-mcp`` program a hosted run mounts. The pinned storage root reaches
    every process the agent starts, the relay included.
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
    environment[HOSTED_RELAY_VARIABLE] = str(relay)
    return environment
