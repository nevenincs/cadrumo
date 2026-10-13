"""The environment an agent tree starts with: named operating-system values, nothing else.

The agent's credentials travel only on its standard-input frame. Its environment
is built from an allow-list rather than by clearing names from the launcher's
own, because a cleared list cannot know every provider's variable: an inherited
``ANTHROPIC_API_KEY`` or ``AWS_SECRET_ACCESS_KEY`` would otherwise reach the
agent and every process it starts.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from ...core.storage_environment import ChildEnvironmentProfile, child_environment

HOSTED_ROOT_VARIABLE: Final = "CADRUMO_AGENT_HOSTED_ROOT"

# Values the operating system and the interpreter need to run at all. None of
# them can carry a credential.
_WINDOWS_NAMES: Final = frozenset(
    {
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "COMSPEC",
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


def agent_launch_environment(
    *, storage_root: Path, agent_root: Path, received: Mapping[str, str], sys_platform: str | None = None
) -> dict[str, str]:
    """Return the agent's whole environment: allow-listed system values, the pinned root and its hosted root.

    ``agent_root`` is the profile's opaque agent directory that Cadrumo derived;
    the agent receives that one path and no profile identity.
    """
    platform = sys.platform if sys_platform is None else sys_platform
    names = _WINDOWS_NAMES if platform == "win32" else _POSIX_NAMES
    if platform == "win32":
        folded = {name.upper(): value for name, value in received.items()}
        base = {name: folded[name] for name in names if name in folded}
    else:
        base = {name: received[name] for name in names if name in received}
    environment = child_environment(
        ChildEnvironmentProfile.STRICT, storage_root, received=received, base=base, sys_platform=platform
    )
    environment[HOSTED_ROOT_VARIABLE] = str(agent_root)
    return environment
