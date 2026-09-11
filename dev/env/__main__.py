"""The ``python -m dev.env`` entry point.

Usage::

    python -m dev.env install
    python -m dev.env workstation-tools
    python -m dev.env setup
    python -m dev.env doctor

Provisioning actions mutate only the checkout's managed environment. The
``doctor`` action is a PATH-only readiness probe and never provisions anything.
"""

from __future__ import annotations

import argparse

from ._dotenv import env_setup
from ._install import install
from ._workstation import workstation_tools
from .doctor import check_developer_toolchain

ACTIONS = {
    "install": install,
    "workstation-tools": workstation_tools,
    "setup": env_setup,
    "doctor": check_developer_toolchain,
}


def main(argv: list[str] | None = None) -> int:
    """Dispatch one environment action and return its exit code.

    Args:
        argv: The argument vector, or ``None`` to read :data:`sys.argv`.

    Returns:
        The exit code of the selected action.
    """
    parser = argparse.ArgumentParser(
        prog="python -m dev.env",
        description="Provision this checkout's Python environment.",
    )
    parser.add_argument("action", choices=[*ACTIONS])
    args = parser.parse_args(argv)
    return ACTIONS[args.action]()


if __name__ == "__main__":
    raise SystemExit(main())
