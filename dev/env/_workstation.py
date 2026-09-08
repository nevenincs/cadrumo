"""Workstation CLI prerequisites for the non-Python audit recipes.

The two shell bodies this replaced did not do the same thing. The Windows one
INSTALLED anything missing through scoop; the unix one only reported it. That
divergence is preserved deliberately - a package manager whose install command
is known is usable, one that is not can only be reported - but it is now one
function with one list of tools, so the two cannot drift apart on WHICH tools
matter.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

#: Each required command, with the package providing it where a package
#: manager can install it.
TOOLS: tuple[tuple[str, str], ...] = (
    ("uv", "uv"),
    ("just", "just"),
    ("node", "nodejs-lts"),
    ("npx", "nodejs-lts"),
)


def _provision_with_scoop(missing: list[tuple[str, str]]) -> int:
    """Install missing tools through scoop.

    Args:
        missing: The absent ``(command, package)`` pairs.

    Returns:
        0 when every install succeeded, otherwise the first failing status.
    """
    if shutil.which("scoop") is None:
        print(
            "scoop is required for workstation tool provisioning.",
            file=sys.stderr,
            flush=True,
        )
        return 1
    worst = 0
    for command, package in missing:
        print(f"$ scoop install {package}  (for {command})", flush=True)
        code = subprocess.run(["scoop", "install", package], check=False).returncode
        if code != 0:
            worst = worst or code
    return worst


def workstation_tools() -> int:
    """Ensure every workstation CLI prerequisite is present.

    Returns:
        0 when every tool is present or was installed, otherwise 1.
    """
    missing = [(cmd, pkg) for cmd, pkg in TOOLS if shutil.which(cmd) is None]
    if not missing:
        print(
            f"All workstation tools present: {', '.join(cmd for cmd, _ in TOOLS)}",
            flush=True,
        )
        return 0

    if sys.platform == "win32":
        return _provision_with_scoop(missing)

    for command, _ in missing:
        print(
            f"{command} is required; install it with the workstation package manager.",
            file=sys.stderr,
            flush=True,
        )
    return 1
