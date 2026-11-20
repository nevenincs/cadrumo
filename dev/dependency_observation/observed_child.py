"""Start an observed process's Python ``-m`` child under observation, then run its module unchanged.

An observed process starts ``python [options] -m <module> [arguments]`` children
of checkout modules as ``python [options] <this copy> <token> <module>
[arguments]``. The copy sits beside the journals, with a file naming the
checkout. It installs the dependency observer before the module is imported,
journals as ``<token>.journal``, and runs the
module as ``__main__`` with the arguments and the module search path that
``-m`` would have given it.

It runs only a module the checkout's load census declares
(:mod:`~dev.dependency_observation.census_admission`). Any other module is
refused: the refusal is journalled, so the parent's observation is incomplete,
and the child exits without running it.

This file uses the standard library only until the observer is installed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: Named in ``observation``, which is unimportable before the path is set.
_CHECKOUT_ROOT_FILE = "checkout-root.txt"
#: Present in an inherited run's journals: the observer's checkout, then the observed one.
_INHERITED_ROOTS_FILE = "observer-roots.txt"


def _main() -> None:
    journals = Path(__file__).resolve().parent
    token, module, *arguments = sys.argv[1:]
    # A missing pointer is a fault, never an unobserved child: the parent
    # records this child's reads from its journal alone.
    root = Path((journals / _CHECKOUT_ROOT_FILE).read_text(encoding="utf-8").strip())
    roots = journals / _INHERITED_ROOTS_FILE
    tooling = roots.read_text(encoding="utf-8").splitlines()[0] if roots.is_file() else str(root)
    sys.path.insert(0, tooling)
    # Last, so a child without site packages (``-S``) still finds the census loader, and any other child resolves
    # the product as its module will.
    product = str(Path(tooling) / "src")
    sys.path.append(product)
    from dev.dependency_observation.census_admission import CensusRefusalError, run_census_module
    from dev.dependency_observation.observation import active_observation, allow_observer_outside, observe_child

    del sys.path[len(sys.path) - 1 - sys.path[::-1].index(product)]
    observe_child(root, journals, token)
    observation = active_observation()
    if observation is not None:
        allow_observer_outside(observation, journals)
    sys.path.remove(tooling)
    # ``-m`` puts the working directory first on the path, where a script puts its own directory.
    sys.path[0] = os.getcwd()
    sys.argv = [sys.argv[0], *arguments]
    try:
        run_census_module(root, module)
    except CensusRefusalError as error:
        if observation is not None:
            observation.note_incomplete(f"observed child {token} refused: {error}")
        raise SystemExit(f"observed child {token} refused: {error}") from None


if __name__ == "__main__":
    _main()
