"""Read-only readiness probes for the developer toolchain.

This module reports the commands that the development recipes depend on. It
does not install packages, create files, start services, or resolve tools
through a package manager. Browser launch belongs to ``playwright_doctor`` and
Python package consistency belongs to the ``doctor-python`` recipe, so neither
is folded into this probe.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolProbe:
    """The read-only result for one developer command."""

    command: str
    purpose: str
    available: bool
    optional: bool = False


# The first group is required for the ordinary developer loop. Node and npx
# are optional because only the duplication scanner needs the workstation
# JavaScript toolchain; setup-workstation-tools remains the explicit provisioner.
_COMMANDS: tuple[tuple[str, str, bool], ...] = (
    ("uv", "managed Python environment convergence", False),
    ("just", "repository recipe dispatch", False),
    ("ruff", "style and format checks", False),
    ("ty", "static type checks", False),
    ("pyrefly", "static type checks", False),
    ("lint-imports", "import-boundary checks", False),
    ("deptry", "dependency declaration checks", False),
    ("vulture", "dead-code audit", False),
    ("radon", "complexity audit", False),
    ("complexipy", "cognitive-complexity audit", False),
    ("node", "duplication audit runtime", True),
    ("npx", "duplication audit launcher", True),
)


def probe_toolchain(*, which: Callable[[str], str | None] | None = None) -> tuple[ToolProbe, ...]:
    """Inspect developer commands without changing the workstation.

    Args:
        which: Optional executable resolver used by tests. Production calls
            use :func:`shutil.which`.

    Returns:
        One probe per command, in the declaration order above.
    """
    resolver = shutil.which if which is None else which
    return tuple(
        ToolProbe(command, purpose, resolver(command) is not None, optional) for command, purpose, optional in _COMMANDS
    )


def check_developer_toolchain(*, which: Callable[[str], str | None] | None = None) -> int:
    """Print developer-tool readiness and fail only for required gaps.

    Optional workstation commands are reported so their absence is visible,
    but they do not make the minimal checkout setup unusable. No probe invokes
    a command or writes a cache; PATH inspection is the entire operation.
    """
    probes = probe_toolchain(which=which)
    for probe in probes:
        status = "ok" if probe.available else ("optional-missing" if probe.optional else "missing")
        print(f"{status:16s} {probe.command:14s} {probe.purpose}")

    missing_required = [probe.command for probe in probes if not probe.available and not probe.optional]
    missing_optional = [probe.command for probe in probes if not probe.available and probe.optional]
    if missing_required:
        print("missing required developer tools: " + ", ".join(missing_required))
    if missing_optional:
        print("optional workstation tools absent: " + ", ".join(missing_optional))
    return 1 if missing_required else 0
