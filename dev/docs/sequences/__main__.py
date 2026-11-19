"""Run the public sequence CLI module for ``python -m dev.docs.sequences``."""

import sys
from pathlib import Path

from .dependency_observation import observe_process


def _run() -> int:
    if sys.argv[1:2] == ["check"]:
        # Before the CLI imports any product module, so every product file the
        # check's sequences read is observed for their verdict records.
        observe_process(Path(__file__).resolve().parents[3])
    from .cli import main

    return main()


if __name__ == "__main__":
    raise SystemExit(_run())
