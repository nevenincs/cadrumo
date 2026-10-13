"""The environment an agent tree starts with: named operating-system values, nothing else.

The agent's credentials travel only on its standard-input frame. Its environment
is built from an allow-list rather than by clearing names from the launcher's
own, because a cleared list cannot know every provider's variable: an inherited
``ANTHROPIC_API_KEY`` or ``AWS_SECRET_ACCESS_KEY`` would otherwise reach the
agent and every process it starts.

The agent is also handed no way to act as the person. Cadrumo's command line
resumes the person's stored sign-in, and an interpreter or shell can drive
anything, so neither is named to the agent: the ``cadrumo-mcp`` relay is the
only Cadrumo program it may start, and its search path keeps no directory that
holds Cadrumo's programs, an interpreter or a shell.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ...core.storage_environment import ChildEnvironmentProfile, child_environment

HOSTED_ROOT_VARIABLE: Final = "CADRUMO_AGENT_HOSTED_ROOT"
GATEWAY_PORT_VARIABLE: Final = "CADRUMO_AGENT_PORT"
WORKER_PORT_VARIABLE: Final = "CADRUMO_AGENT_WORKER_PORT"
HOSTED_RELAY_VARIABLE: Final = "CADRUMO_AGENT_HOSTED_RELAY_EXECUTABLE"
"""The absolute path of the bundle's ``cadrumo-mcp``, the relay a hosted run mounts.

cadrumo-agent's hosting contract does not yet name this value; until it does,
the agent looks the relay up by name, and this value is what it must adopt.
"""


@dataclass(frozen=True, slots=True)
class AgentHostedPrograms:
    """The one Cadrumo program a hosted agent may start, by absolute path: the ``cadrumo-mcp`` relay.

    Never the command line, which resumes the person's sign-in, and never an
    interpreter.
    """

    relay: Path


_FORBIDDEN_PROGRAM_STEMS: Final = ("aeat", "cadrumo", "python", "pythonw", "py", "cmd", "powershell", "pwsh")
_FORBIDDEN_PROGRAM_STEMS_MORE: Final = ("wscript", "cscript", "mshta", "bash", "sh", "wsl", "conhost")
FORBIDDEN_PROGRAM_STEMS: Final = frozenset(_FORBIDDEN_PROGRAM_STEMS + _FORBIDDEN_PROGRAM_STEMS_MORE)
"""Program names the agent's search path may not reach: Cadrumo's programs, interpreters and shells.

A name matches its stem exactly or as a prefix followed by ``-`` or a digit
(``cadrumo-mcp``, ``python3``), with any executable extension.
"""


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


def agent_launch_environment(
    *,
    storage_root: Path,
    agent_root: Path,
    received: Mapping[str, str],
    programs: AgentHostedPrograms | None = None,
    sys_platform: str | None = None,
) -> dict[str, str]:
    """Return the agent's whole environment: allow-listed system values, the pinned root and its hosted root.

    ``agent_root`` is the profile's opaque agent directory that Cadrumo derived;
    the agent receives that one path and no profile identity. ``programs``
    adds the hosting contract's nonsecret launch values. The pinned storage
    root reaches every process the agent starts, the relay included.
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
    if "PATH" in environment:
        environment["PATH"] = agent_search_path(environment["PATH"], sys_platform=platform)
    environment[HOSTED_ROOT_VARIABLE] = str(agent_root)
    if programs is not None:
        # The agent binds ephemeral ports and reports the real one on its ready line.
        environment[GATEWAY_PORT_VARIABLE] = "0"
        environment[WORKER_PORT_VARIABLE] = "0"
        environment[HOSTED_RELAY_VARIABLE] = str(programs.relay)
    return environment


def agent_search_path(value: str, *, sys_platform: str) -> str:
    """Keep only the search-path directories that hold none of the forbidden programs."""
    separator = ";" if sys_platform == "win32" else ":"
    kept = [entry for entry in value.split(separator) if entry and not _holds_forbidden_program(Path(entry))]
    return separator.join(kept)


def forbidden_program(name: str) -> bool:
    """Whether a file name is one of Cadrumo's programs, an interpreter or a shell."""
    stem = name.lower().split(".", 1)[0]
    return any(
        stem == forbidden or (stem.startswith(forbidden) and stem[len(forbidden)] in "-0123456789")
        for forbidden in FORBIDDEN_PROGRAM_STEMS
    )


def _holds_forbidden_program(directory: Path) -> bool:
    try:
        return any(forbidden_program(entry.name) for entry in directory.iterdir() if entry.is_file())
    except OSError:
        # A directory that cannot be listed cannot be shown to hold nothing forbidden.
        return True
