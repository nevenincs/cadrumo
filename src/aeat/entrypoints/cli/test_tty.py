"""Unit tests for the TTY helpers."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
import typer
from typer.testing import CliRunner

import aeat.entrypoints.cli as cli
from ...core.config import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _run_probe(script: str, *, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run a small Python probe with piped stdin/stdout/stderr."""

    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    project_pythonpath = str(PROJECT_ROOT / "src")
    env["PYTHONPATH"] = (
        f"{project_pythonpath}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else project_pythonpath
    )
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(  # noqa: S603 - trusted interpreter invocation for pipe-behavior coverage
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        env=env,
        input="",
        text=True,
    )


def test_tty_probes_report_false_when_all_streams_are_piped() -> None:
    """Subprocess pipes should present as non-TTY streams to the helpers."""

    script = """
import json
from aeat.entrypoints.cli import is_stderr_tty, is_stdin_tty, is_stdout_tty, should_show_rich_progress
print(json.dumps({
    "stdout": is_stdout_tty(),
    "stderr": is_stderr_tty(),
    "stdin": is_stdin_tty(),
    "rich_progress": should_show_rich_progress(),
}))
"""
    completed = _run_probe(script)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload == {
        "stdout": False,
        "stderr": False,
        "stdin": False,
        "rich_progress": False,
    }


def test_no_color_env_is_honored_even_when_force_color_is_absent() -> None:
    """``NO_COLOR`` must disable colour resolution."""

    script = """
import json
from aeat.entrypoints.cli import should_use_color
print(json.dumps({"color": should_use_color()}))
"""
    completed = _run_probe(script, env_overrides={"NO_COLOR": "1", "AEAT_FORCE_COLOR": ""})
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"color": False}


def test_force_color_env_overrides_non_tty_stdout() -> None:
    """``AEAT_FORCE_COLOR`` should enable colour even through a pipe."""

    script = """
import json
from aeat.entrypoints.cli import should_use_color
print(json.dumps({"color": should_use_color()}))
"""
    completed = _run_probe(script, env_overrides={"AEAT_FORCE_COLOR": "1", "NO_COLOR": ""})
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"color": True}


def test_refuse_if_stdin_non_tty_raises_typed_refusal_with_suggestion() -> None:
    """Non-interactive stdin should raise the dedicated refusal error."""

    script = """
import json
from aeat.entrypoints.cli import NonTtyRefusedError, refuse_if_stdin_non_tty
try:
    refuse_if_stdin_non_tty("-> Re-run in a TTY or pass --profile FILE")
except NonTtyRefusedError as exc:
    print(json.dumps({
        "error_type": type(exc).__name__,
        "message": str(exc),
        "suggestion": exc.suggestion,
    }))
"""
    completed = _run_probe(script)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["error_type"] == "NonTtyRefusedError"
    assert "Interactive stdin is unavailable" in payload["message"]
    assert payload["suggestion"] == "-> Re-run in a TTY or pass --profile FILE"


def test_root_no_color_flag_overrides_leaf_default_false() -> None:
    """Root ``--no-color`` should beat a leaf's default ``False`` parameter."""

    app = typer.Typer()

    @app.callback()
    def root(
        ctx: typer.Context,
        no_color: bool = typer.Option(False, "--no-color"),
    ) -> None:
        state = ctx.ensure_object(dict)
        state["no_color"] = no_color

    @app.command()
    def probe() -> None:
        typer.echo(json.dumps({"color": cli.should_use_color(no_color=False)}))

    runner = CliRunner()
    env = dict(os.environ)
    env["AEAT_FORCE_COLOR"] = "1"
    env["NO_COLOR"] = ""
    result = runner.invoke(app, ["--no-color", "probe"], env=env)

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"color": False}
