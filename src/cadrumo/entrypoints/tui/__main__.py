"""Module execution for the dedicated TUI.

The CLI is not imported here, and must not be: the TUI is an outermost
process entrypoint, so a full-screen session starts through this module or
through the installed console script, never by a sibling entrypoint reaching
across.

Two invocation shapes reach this module. Without a destination it starts the
root session and nothing else. With one it runs that destination as the whole
session, which is how a sibling entrypoint opens a full-screen surface whose
subject and result cannot cross a process boundary as live objects; the
argument surface and the outcome record are defined by the shared session
protocol beside this package, owned by neither entrypoint.

``--self-test`` runs one session headless to a clean exit, which is how an
installed artifact proves its full-screen surface starts without a terminal.
"""

from __future__ import annotations

import sys

from ..full_screen_session_protocol import SELF_TEST_FLAG, parse_request_arguments
from .launcher import InstalledWorkbenchRootInputsProviderV1, main


def run(
    arguments: list[str],
    *,
    workbench_root_inputs_provider: InstalledWorkbenchRootInputsProviderV1 | None = None,
) -> int:
    """Start whichever session these arguments request, and report its status."""
    request = parse_request_arguments(arguments)
    if request is None:
        if workbench_root_inputs_provider is None:
            sys.stderr.write("workbench.root.composition_required\n")
            return 2
        return main(
            headless=SELF_TEST_FLAG in arguments,
            workbench_root_inputs_provider=workbench_root_inputs_provider,
        )
    from .destination_session import run_requested_destination

    return run_requested_destination(request)


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
