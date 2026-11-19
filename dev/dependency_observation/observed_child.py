"""Start an observed process's Python ``-m`` child under observation, then run its module unchanged.

An observed process starts ``python [options] -m <module> [arguments]`` children
of checkout modules as ``python [options] <this copy> <token> <module>
[arguments]``. The copy sits beside the journals, with a file naming the
checkout. It installs the dependency observer before the module is imported,
journals as ``<token>.journal``, and runs the
module as ``__main__`` with the arguments and the module search path that
``-m`` would have given it.

This file uses the standard library only until the observer is installed.
"""

from __future__ import annotations

import os
import runpy
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
    from dev.dependency_observation.observation import active_observation, allow_observer_outside, observe_child

    observe_child(root, journals, token)
    observation = active_observation()
    if observation is not None:
        allow_observer_outside(observation, journals)
    sys.path.remove(tooling)
    # ``-m`` puts the working directory first on the path, where a script puts its own directory.
    sys.path[0] = os.getcwd()
    sys.argv = [sys.argv[0], *arguments]
    runpy.run_module(module, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    _main()
