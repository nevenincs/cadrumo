"""Real proofs that the INSTALLED ``aeat --tui`` request starts a session.

The sibling module-execution proofs cover ``python -m cadrumo.entrypoints.tui``.
This file covers the other installed shape: the root console script resolved
and executed the way a shell resolves it, carrying the full-screen request.
Calling the root callback in-process cannot stand in for it — a request that
works in a test process and fails from a console wrapper is exactly the defect
these exist to catch.

The dedicated ``aeat-tui`` console script this file once covered is retired.
One surface reaches the session now, and the first test below is what keeps a
second spelling from coming back.

Nothing here asserts on rendered prose. The prose is locale data read from the
same catalogue the app reads, so asserting it would prove only that one file
was consulted twice. The assertions are against process behaviour, against the
packaging declaration, and against the child's own import graph.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ...full_screen_session_protocol import (
    FullScreenDestination,
    FullScreenSessionRequest,
    parse_request_arguments,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SCRIPT_NAME = "aeat"
_RETIRED_SCRIPT_NAME = "aeat-tui"
_SESSION_MODULE = "cadrumo.entrypoints.tui"
_STARTUP_GRACE_SECONDS = 45.0

_REPO_ROOT = Path(__file__).parents[5]


def _console_script() -> Path:
    """Locate the installed console script beside the running interpreter."""
    scripts_dir = Path(sys.executable).parent
    for candidate in (scripts_dir / f"{_SCRIPT_NAME}.exe", scripts_dir / _SCRIPT_NAME):
        if candidate.exists():
            return candidate
    pytest.fail(
        f"no installed {_SCRIPT_NAME!r} console script beside {sys.executable}; "
        "the packaging declaration is not installed in this environment"
    )


def test_the_packaging_declares_one_console_entry_point_and_no_tui_alias() -> None:
    """The root script is the only console entry; the TUI has no second spelling."""
    import tomllib

    spec = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = spec["project"]["scripts"]

    assert scripts.get(_SCRIPT_NAME) == "cadrumo.entrypoints._cli_main:main"
    assert _RETIRED_SCRIPT_NAME not in scripts, (
        f"{_RETIRED_SCRIPT_NAME} is retired; the full-screen session is reached through `aeat --tui`"
    )


def test_the_installed_script_routes_the_tui_flag_to_the_session_not_a_refusal() -> None:
    """`aeat --tui` reaches the frontend-capability gate, which is as far as a pipe goes.

    A piped stdout is not a terminal, so the honest outcome here is the
    console-capability refusal, and the session itself is proven by the sibling
    module-execution suite that starts it directly. What this asserts is the
    ROUTING: the request must no longer die at the root node's TUI posture.
    Before the root became a routing target it refused with the
    not-implemented identity, so that string reappearing is the regression.
    """
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, installed console script
        [str(_console_script()), "--tui"],
        cwd=_REPO_ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=_STARTUP_GRACE_SECONDS,
    )

    rendered = (completed.stdout + completed.stderr).decode("utf-8", errors="replace")

    assert completed.returncode != 0, f"a non-terminal cannot host a session, so this must refuse:\n{rendered[:2000]}"
    assert "root.status" not in rendered, (
        f"the root still refuses the request as unrouted rather than reaching the session:\n{rendered[:2000]}"
    )
    assert "Traceback (most recent call last)" not in rendered, rendered[:2000]


def test_the_session_is_started_out_of_process_through_module_execution() -> None:
    """The CLI reaches the TUI by executing it, never by importing it.

    The architecture forbids a CLI entrypoint from importing the TUI and names
    out-of-process execution as the sanctioned alternative, so the command the
    CLI builds is part of that contract rather than an implementation detail.
    """
    from ...cli._tui_session import TUI_SESSION_MODULE, tui_session_command

    command = tui_session_command("/usr/bin/python3")

    assert TUI_SESSION_MODULE == _SESSION_MODULE
    assert command == ["/usr/bin/python3", "-m", _SESSION_MODULE]


def test_a_requested_destination_is_executed_rather_than_constructed() -> None:
    """A command whose destination is a full-screen surface still executes it.

    The two commands that open a modelo work surface once constructed the
    Textual applications in their own process, which made the frontend a
    library for a sibling entrypoint. They now spawn the same
    module-execution surface, carrying the subject as arguments the shared
    session protocol defines, and the destination request this asserts is what
    the child would actually receive.
    """
    from ...cli._tui_session import destination_session_command

    request = FullScreenSessionRequest(
        destination=FullScreenDestination.MODELO_WORK_REVIEW,
        outcome_file=Path("outcome.json"),
        work_unit_id="f" * 64,
    )

    command = destination_session_command(request, "/usr/bin/python3")

    assert command[:3] == ["/usr/bin/python3", "-m", _SESSION_MODULE]
    assert parse_request_arguments(command[3:]) == request


def test_the_session_child_imports_no_cli_internals() -> None:
    """The TUI stays an outermost entrypoint even though the CLI now starts it.

    The CLI reaches the session by executing this module in a child
    interpreter, never by importing it, so the started session's import graph
    must still contain no CLI module. Observed in a fresh process running the
    same ``-m`` surface the CLI spawns.
    """
    probe = (
        "import json, sys, runpy\n"
        f"sys.modules.pop({_SESSION_MODULE!r}, None)\n"
        f"__import__({_SESSION_MODULE!r} + '.launcher')\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.startswith('cadrumo.entrypoints.'))))\n"
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and literal probe
        [sys.executable, "-c", probe],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=_STARTUP_GRACE_SECONDS,
    )

    imported = json.loads(completed.stdout.splitlines()[-1])
    cli_modules = [name for name in imported if name.startswith("cadrumo.entrypoints.cli")]

    assert f"{_SESSION_MODULE}.launcher" in imported, f"the session module did not import its launcher: {imported}"
    assert not cli_modules, f"starting the TUI pulled in CLI internals: {cli_modules}"
