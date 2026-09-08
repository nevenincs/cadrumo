"""The ``python -m dev.env`` entry point.

Usage::

    python -m dev.env init-venv
    python -m dev.env install
    python -m dev.env workstation-tools
    python -m dev.env setup

Each action replaced a pair of `[windows]`/`[unix]` justfile recipe bodies that
implemented one rule in two shell dialects.
"""

from __future__ import annotations

import argparse

from dev.env._dotenv import env_setup
from dev.env._install import install
from dev.env._venv import ensure
from dev.env._workstation import workstation_tools

ACTIONS = {
    "init-venv": ensure,
    "install": install,
    "workstation-tools": workstation_tools,
    "setup": env_setup,
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
