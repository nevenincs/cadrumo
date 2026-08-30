"""Real proofs that the INSTALLED console script starts a full-screen session.

The sibling module-execution proofs cover ``python -m cadrumo.entrypoints.tui``.
This file covers the other installed shape: the console script packaging
declares, resolved and executed the way a shell resolves it. Running the
launcher's ``main`` in-process cannot stand in for either — an entry point
that resolves in a test process and fails from a console wrapper is exactly
the defect these exist to catch.

Nothing here asserts on rendered prose. The prose is locale data read from
the same catalogue the app reads, so asserting it would prove only that one
file was consulted twice. The assertions are against the terminal control
sequence a started Textual session emits, against process behaviour, and
against the child's own import graph.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SCRIPT_NAME = "aeat-tui"
_ENTRY_POINT = "cadrumo.entrypoints.tui.launcher:main"
_ALTERNATE_SCREEN = b"?1049h"
"""The control sequence a Textual session emits when it takes the terminal."""

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


def test_the_packaging_declares_the_dedicated_console_entry_point() -> None:
    """The declaration targets the launcher directly, never a CLI bootstrap."""
    import tomllib

    spec = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = spec["project"]["scripts"]

    assert scripts.get(_SCRIPT_NAME) == _ENTRY_POINT, (
        f"{_SCRIPT_NAME} must target the launcher directly; found {scripts.get(_SCRIPT_NAME)!r}"
    )


def test_the_installed_console_script_starts_a_session() -> None:
    """The console wrapper runs a real full-screen session rather than raising."""
    process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell, installed console script
        [str(_console_script())],
        cwd=_REPO_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        output, _ = process.communicate(timeout=_STARTUP_GRACE_SECONDS)
        status: int | None = int(process.returncode)
    except subprocess.TimeoutExpired:
        process.kill()
        output, _ = process.communicate()
        status = None

    rendered = output.decode("utf-8", errors="replace")
    assert status is None, (
        f"the session ended by itself with status {status}; a started TUI holds the terminal:\n{rendered[:2000]}"
    )
    assert _ALTERNATE_SCREEN in output, f"no session took the terminal:\n{rendered[:2000]}"
    assert "Traceback (most recent call last)" not in rendered, rendered[:2000]


def test_starting_through_the_entry_point_imports_no_cli_internals() -> None:
    """The TUI is an outermost entrypoint: it never reaches across to the CLI.

    Resolved through :mod:`importlib.metadata` in a fresh process, which is
    the mechanism the console wrapper itself uses, so this observes the real
    import graph of the real entry point rather than a hand-built import.
    """
    probe = (
        "import json, sys\n"
        "from importlib.metadata import EntryPoint\n"
        f"ep = EntryPoint(name={_SCRIPT_NAME!r}, value={_ENTRY_POINT!r}, group='console_scripts')\n"
        "ep.load()\n"
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

    assert "cadrumo.entrypoints.tui.launcher" in imported, (
        f"the entry point did not import the launcher it names: {imported}"
    )
    assert not cli_modules, f"starting the TUI pulled in CLI internals: {cli_modules}"
