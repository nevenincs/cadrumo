"""Where the generated window projections live: the host's native build tree.

A projection is build output, so it sits beside the other outputs of the build
tree the host configures, ``build/<preset>/fixtures/window``, and is never
committed. The preset is the one the repository enrols for the machine
running the tooling; a host with no enrolled preset has no projection tree.
"""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT

#: The configure preset the repository enrols for each host, by operating system and machine.
HOST_PRESETS: Final[dict[tuple[str, str], str]] = {
    ("Windows", "AMD64"): "windows-x64",
    ("Linux", "x86_64"): "linux-x86-64",
    ("Linux", "aarch64"): "linux-aarch64",
    ("Darwin", "arm64"): "macos-arm64",
}

#: The window projections' directory below a build tree.
WINDOW_BELOW_BUILD: Final[str] = "fixtures/window"


def host_preset() -> str:
    """The configure preset this host builds with.

    Raises:
        RuntimeError: When the repository enrols no preset for this host.
    """
    key = (platform.system(), platform.machine())
    try:
        return HOST_PRESETS[key]
    except KeyError:
        raise RuntimeError(f"No configure preset is enrolled for host {key}") from None


def window_projections() -> str:
    """The window projections' directory relative to the repository root, in the host's build tree."""
    return f"build/{host_preset()}/{WINDOW_BELOW_BUILD}"


def family_directory(family: str) -> Path:
    """The directory a window family's projections are written into: its own folder in the projection directory."""
    return REPO_ROOT / window_projections() / family
