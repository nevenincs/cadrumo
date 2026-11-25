"""Import the modules a package manifest names, from inside the packaged interpreter.

The manifest is written by the build and lists whatever the bundle ships, so the
names are data, not a finite set the checkout can enumerate.  Modules outside the
first-party roots are imported by a fresh packaged interpreter that receives them
on standard input.  A first-party module is never imported from a name taken out of
the manifest; the package checks that precede this one load each of them through
static imports and the console-script targets, so the manifest entry is held to
having been loaded by them.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from typing import Final

#: The shipped first-party import roots.  ``dev`` and ``docs`` never reach a package.
FIRST_PARTY_ROOTS: Final[frozenset[str]] = frozenset(
    {"cadrumo", "cadrumo_client", "cadrumo_runtime", "cadrumo_mcp", "cadrumo_agent_service"}
)

_PROBE_TIMEOUT_SECONDS: Final[int] = 90


def is_first_party(module: str) -> bool:
    """Whether ``module`` belongs to a shipped first-party root."""
    return module.partition(".")[0] in FIRST_PARTY_ROOTS


def with_prerequisites(modules: Iterable[str], prerequisites: Mapping[str, Sequence[str]]) -> list[str]:
    """Order ``modules`` so that each follows the modules its import needs loaded first."""
    return [name for module in modules for name in (*prerequisites.get(module, ()), module)]


def import_bundled(modules: Iterable[str], failure: str) -> None:
    """Import each of ``modules`` in order, in one fresh interpreter of the package.

    ``failure`` heads the error raised when an import fails.  First-party modules
    are not imported here; each must already be loaded in this process.
    """
    named = list(modules)
    for module in named:
        if is_first_party(module) and module not in sys.modules:
            raise RuntimeError(f"{failure}: first-party module was not loaded by the package checks: {module}")
    outside = [module for module in named if not is_first_party(module)]
    if not outside:
        return
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib, sys\n"
            "names = sys.stdin.read().split()\n"
            "for name in names:\n"
            "    try:\n"
            "        importlib.import_module(name)\n"
            "    except BaseException as error:\n"
            "        sys.exit(f'{name}: {type(error).__name__}: {error}')\n"
            "sys.stdout.write(f'imported {len(names)}\\n')\n",
        ],
        input="\n".join(outside),
        text=True,
        capture_output=True,
        timeout=_PROBE_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{failure}: {result.stderr.strip() or f'exit {result.returncode}'}")
    if result.stdout.strip() != f"imported {len(outside)}":
        raise RuntimeError(f"{failure}: the import probe ended before importing every module")
