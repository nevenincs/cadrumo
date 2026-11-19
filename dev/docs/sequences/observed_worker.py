"""The observed docs profile worker script: journal what the worker reads, then run the fixture's worker.

The runtime starts each profile worker as ``python -I -B <script>`` with a
launch environment the docs fixture does not control, so the observed check
hands its workers their journal directory through the script's own location.
:func:`~dev.docs.sequences.dependency_observation.prepare_worker_journals`
copies this file into the sandbox's journal directory beside a file naming the
checkout. The copy installs the dependency observer before any product module
is imported, then runs :mod:`dev.docs.sequences.runtime_fixture` as the
``__main__`` program it has always been.

This file uses the standard library only until the observer is installed.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from typing import Final

#: The file, beside the worker script copy, that names the checkout root.
CHECKOUT_ROOT_FILE: Final[str] = "checkout-root.txt"


def _main() -> None:
    journals = Path(__file__).resolve().parent
    # A missing pointer is a fault, never an unobserved worker: the check
    # records this sequence's product inputs from the journals alone.
    root = Path((journals / CHECKOUT_ROOT_FILE).read_text(encoding="utf-8").strip())
    # Isolated mode omits the checkout root; the observer is a dev-only sibling.
    sys.path.insert(0, str(root))
    from dev.docs.sequences.dependency_observation import observe_worker

    observe_worker(root, journals)
    runpy.run_path(str(root / "dev" / "docs" / "sequences" / "runtime_fixture.py"), run_name="__main__")


if __name__ == "__main__":
    _main()
