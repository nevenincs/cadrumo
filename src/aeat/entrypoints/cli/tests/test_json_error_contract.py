"""JSON-mode failures emit the shared-spine error document.

Operator testimony across three rounds found that under ``--format json``
every failure printed human prose (or a Rich usage box, or a raw
traceback) to stderr with an empty stdout — the shared-spine
``ErrorEnvelope`` document mandated by the
cli-envelope-notice-standardisation contract never appeared on any reachable
failure. Two structural causes, both fixed and pinned here:

- ``json_output_requested()`` resolved the current context from upstream
  ``click``, but Typer runs on its own vendored Click fork
  (``typer._click``) whose context stack is a different contextvar — the
  probe was always ``None``, so EVERY error rendered text
  (``test_vendored_context_stack_is_visible_to_json_probe``).
- Click usage errors and crashes never reached the error boundary at all:
  Typer's standalone ``main`` rendered them as Rich text / raw
  tracebacks. The root group's terminal funnel
  (:mod:`aeat.entrypoints.cli._terminal_errors`) now re-implements the
  standalone handling with a JSON-aware branch.

Honest boundary (documented, not hidden): an argv so malformed that the
flag probe cannot recognise the JSON request (e.g. ``--format`` with no
value at the very end) falls back to text rendering — the format wish is
itself part of the unparseable input.

Real-behavior only: the real ``aeat`` app object through
``CliRunner`` over a real isolated profile, plus a real subprocess for
the crash funnel (the only honest way to observe a terminal traceback
replacement).
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.json_contract import ENVELOPE_SCHEMA_VERSION
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
        yield


def _error_document(output: str) -> dict[str, object]:
    """Parse the single-line shared-spine error document from CLI output."""
    for line in output.splitlines():
        candidate = line.strip()
        if candidate.startswith("{"):
            parsed = json.loads(candidate)
            assert isinstance(parsed, dict)
            return parsed
    raise AssertionError(f"no JSON document found in output:\n{output}")


def _assert_shared_spine(document: dict[str, object]) -> dict[str, object]:
    assert document["schema_version"] == ENVELOPE_SCHEMA_VERSION
    assert document["status"] == "error"
    assert "command" in document
    assert document["notices"] == []
    error = document["error"]
    assert isinstance(error, dict)
    for field in ("code", "category", "message", "suggestion", "retryable", "context"):
        assert field in error, f"error member missing {field!r}"
    return error


def test_json_usage_error_emits_shared_spine_document(cli_runner: CliRunner) -> None:
    """A parse-time bad value emits the error document, exit 2 preserved."""
    result = cli_runner.invoke(app, ["--format", "json", "app", "ledger", "view", "not-hex!"])
    assert result.exit_code == 2, result.output
    error = _assert_shared_spine(_error_document(result.output))
    assert error["category"] == "REFUSED"
    assert "Usage:" not in result.output


def test_json_unknown_command_emits_shared_spine_document(cli_runner: CliRunner) -> None:
    """An unknown subcommand emits the error document, exit 2 preserved."""
    result = cli_runner.invoke(app, ["--format", "json", "config", "nosuchcmd"])
    assert result.exit_code == 2, result.output
    error = _assert_shared_spine(_error_document(result.output))
    assert "nosuchcmd" in str(error["message"])


def test_json_boundary_refusal_emits_shared_spine_document(cli_runner: CliRunner) -> None:
    """An AeatError refusal inside a callback renders JSON, not prose.

    This is the vendored-context-stack regression: the probe used to
    consult upstream click's (empty) stack and render text for every
    refusal even under ``--format json``.
    """
    result = cli_runner.invoke(app, ["--format", "json", "config", "reset"])
    assert result.exit_code == 2, result.output
    error = _assert_shared_spine(_error_document(result.output))
    assert error["code"] == "REFUSED_CLI_BOUNDARY"
    context = error["context"]
    assert isinstance(context, dict)
    assert "accepted_scopes" in context


def test_text_mode_usage_error_keeps_human_rendering(cli_runner: CliRunner) -> None:
    """Anti-regression: without --format json the human rendering survives."""
    result = cli_runner.invoke(app, ["app", "ledger", "view", "not-hex!"])
    assert result.exit_code == 2, result.output
    assert "Usage:" in result.output
    assert not result.output.lstrip().startswith("{")


def test_vendored_context_stack_is_visible_to_json_probe() -> None:
    """``json_output_requested`` reads Typer's vendored context stack.

    The root-cause regression test: a command running under Typer's
    vendored Click runtime with ``--json`` in its params must be seen by
    the probe even though upstream ``click.get_current_context`` is None.
    """
    import typer

    from ....core.click_context import json_output_requested

    observed: list[bool] = []
    probe_app = typer.Typer()

    @probe_app.command()
    def probe(json_out: bool = typer.Option(False, "--json")) -> None:  # pyright: ignore[reportUnusedFunction]  # reason: registered via decorator
        observed.append(json_output_requested())

    runner = CliRunner()
    result = runner.invoke(probe_app, ["--json"])
    assert result.exit_code == 0, result.output
    assert observed == [True]


def test_crash_funnel_replaces_traceback_with_error_document(tmp_path: Path) -> None:
    """An unexpected exception emits the INTERNAL document (exit 6), not a traceback.

    Runs a real subprocess over a minimal app mounted on the production
    :class:`AeatTyperGroup` so the terminal funnel is observed exactly as
    an operator would: stderr payload, no traceback, registered exit code.
    """
    script = tmp_path / "crash_probe.py"
    script.write_text(
        textwrap.dedent(
            """
            import typer
            from aeat.entrypoints.cli._command_suggestions import AeatTyperGroup

            app = typer.Typer(cls=AeatTyperGroup)


            @app.callback()
            def root() -> None:
                "Force group materialisation so AeatTyperGroup.main runs."


            @app.command()
            def boom(json_out: bool = typer.Option(False, "--json")) -> None:
                raise ValueError("synthetic crash for the terminal funnel")


            app()
            """,
        ),
        encoding="utf-8",
    )
    json_run = subprocess.run(
        [sys.executable, str(script), "boom", "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert json_run.returncode == 6, json_run.stderr
    assert "Traceback" not in json_run.stderr
    error = _assert_shared_spine(_error_document(json_run.stderr))
    assert error["code"] == "INTERNAL_CLI_UNEXPECTED_BOUNDARY"

    text_run = subprocess.run(
        [sys.executable, str(script), "boom"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert text_run.returncode == 6, text_run.stderr
    assert "Traceback" not in text_run.stderr
    assert not text_run.stderr.lstrip().startswith("{")
