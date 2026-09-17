"""Proofs for the independent installed TUI entrypoint."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import run_audited_process

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SCRIPT_NAME = "aeat"
_RETIRED_SCRIPT_NAME = "aeat-tui"
_SESSION_MODULE = "cadrumo.entrypoints.tui"
_STARTUP_GRACE_SECONDS = 45.0
_REPO_ROOT = Path(__file__).parents[5]


def test_the_packaging_declares_one_console_entry_point_and_no_tui_alias() -> None:
    """The TUI has no separate console-script spelling."""
    from ....core.toml import parse_toml

    spec = parse_toml((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = spec["project"]["scripts"]

    assert scripts.get(_SCRIPT_NAME) == "cadrumo.entrypoints.cli.bootstrap:main"
    assert _RETIRED_SCRIPT_NAME not in scripts


def test_the_tui_module_imports_no_cli_internals() -> None:
    """The TUI root remains an outermost entrypoint in a fresh process.

    ``__main__`` defers its imports until it runs as a script, so the probe
    also imports the launcher that script executes.
    """
    probe = (
        "import json, sys\n"
        f"sys.modules.pop({_SESSION_MODULE!r}, None)\n"
        f"__import__({_SESSION_MODULE!r} + '.__main__')\n"
        f"__import__({_SESSION_MODULE!r} + '.launcher')\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.startswith('cadrumo.entrypoints.'))))\n"
    )
    completed = run_audited_process(
        [sys.executable, "-c", probe],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=_STARTUP_GRACE_SECONDS,
    )

    imported = json.loads(completed.stdout.splitlines()[-1])
    cli_modules = [name for name in imported if name.startswith("cadrumo.entrypoints.cli")]

    for required in (".__main__", ".launcher"):
        assert f"{_SESSION_MODULE}{required}" in imported, (
            f"the probe never reached {required}, so it proves nothing: {imported}"
        )
    assert not cli_modules, f"starting the TUI pulled in CLI internals: {cli_modules}"


def test_the_tui_module_refuses_retired_destination_session_arguments(tmp_path: Path) -> None:
    """An obsolete child-session request fails visibly before a root session starts."""
    outcome_file = tmp_path / "outcome.json"

    completed = run_audited_process(
        [
            sys.executable,
            "-m",
            _SESSION_MODULE,
            "--destination",
            "modelo.work.invented",
            "--outcome-file",
            str(outcome_file),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=_STARTUP_GRACE_SECONDS,
    )

    assert completed.returncode == 2
    assert isinstance(completed.stderr, str)
    assert "unrecognised TUI module arguments" in completed.stderr
    assert "Traceback (most recent call last)" not in completed.stderr
    assert not outcome_file.exists()
