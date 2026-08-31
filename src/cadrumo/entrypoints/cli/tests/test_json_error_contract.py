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
  (:mod:`cadrumo.entrypoints.cli._terminal_errors`) now re-implements the
  standalone handling with a JSON-aware branch.

Honest boundary (documented, not hidden): an argv so malformed that the
flag probe cannot recognise the JSON request (e.g. ``--format`` with no
value at the very end) falls back to text rendering — the format wish is
itself part of the unparseable input.

Real-behavior only: the real ``cadrumo`` app object through
the shared CLI runner over a real isolated profile, plus a real subprocess for
the crash funnel (the only honest way to observe a terminal traceback
replacement).

The ``"logs"`` literal is deliberate: the crash subprocess sets only
``CADRUMO_LOCAL_STORAGE_ROOT``, no log-directory override, so
``state_root / "logs" / "cadrumo.log"`` is the real DEFAULT-derived
diagnostic-log location, not an injected value.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Final

import pytest

from ....core.json_contract import ENVELOPE_SCHEMA_VERSION
from ....tests.cli_envelope import require_error_document
from ....tests.cli_runner import invoke_cached_cli
from ._isolated_profile_storage_fixtures import active_profile_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["active_profile_isolated_backend"]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"logs", "cadrumo.log"})
"""Taxonomy-vocabulary literals this module deliberately pins.

``state_root / "logs" / "cadrumo.log"`` is the real diagnostic-log location a
crash's traceback must reach; both the directory and the leaf filename are
asserted directly against the real DEFAULT-derived path, not an injected
value.
"""


def _object_member(document: dict[str, object], key: str) -> dict[str, object]:
    """Return a JSON-object member of ``document``, re-keyed for string lookup.

    ``json.loads`` yields untyped mappings, so rebuilding the member here gives
    callers a ``dict[str, object]`` they can index by name.
    """
    value = document[key]
    assert isinstance(value, dict), f"{key!r} is not a JSON object: {value!r}"
    return {str(name): member for name, member in value.items()}


def _assert_shared_spine(document: dict[str, object]) -> dict[str, object]:
    assert document["schema_version"] == ENVELOPE_SCHEMA_VERSION
    assert document["status"] == "error"
    assert "command" in document
    assert document["notices"] == []
    error = _object_member(document, "error")
    for field in ("code", "category", "message", "suggestion", "retryable", "context"):
        assert field in error, f"error member missing {field!r}"
    return error


def test_json_usage_error_emits_shared_spine_document() -> None:
    """A parse-time bad value emits the error document, exit 2 preserved."""
    result = invoke_cached_cli(["--format", "json", "app", "ledger", "view", "not-hex!"])
    assert result.exit_code == 2, result.output
    error = _assert_shared_spine(require_error_document(result.output))
    assert error["category"] == "REFUSED"
    assert "Usage:" not in result.output


def test_json_unknown_command_emits_shared_spine_document() -> None:
    """An unknown subcommand emits the error document, exit 2 preserved."""
    result = invoke_cached_cli(["--format", "json", "config", "nosuchcmd"])
    assert result.exit_code == 2, result.output
    error = _assert_shared_spine(require_error_document(result.output))
    assert "nosuchcmd" in str(error["message"])


def test_json_boundary_refusal_emits_shared_spine_document() -> None:
    """An CadrumoError refusal inside a callback renders JSON, not prose.

    This is the vendored-context-stack regression: the probe used to
    consult upstream click's (empty) stack and render text for every
    refusal even under ``--format json``. The vehicle is the durable
    all-profile reset's retention-override guard, which raises a
    ``CliRefusedBoundaryError`` carrying a typed ``context`` (the
    offending option) from inside the command callback.
    """
    result = invoke_cached_cli(
        ["--format", "json", "config", "reset", "start", "--yes", "--override-retention"],
    )
    assert result.exit_code == 2, result.output
    error = _assert_shared_spine(require_error_document(result.output))
    assert error["code"] == "REFUSED_CLI_BOUNDARY"
    context = _object_member(error, "context")
    assert context["option"] == "--reason"


def test_text_mode_usage_error_keeps_human_rendering() -> None:
    """Anti-regression: without --format json the human rendering survives."""
    result = invoke_cached_cli(["app", "ledger", "view", "not-hex!"])
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
    def probe(json_out: bool = typer.Option(False, "--json")) -> None:
        observed.append(json_output_requested())

    assert probe.__name__ == "probe"

    command = typer.main.get_command(probe_app)
    command.main(args=["--json"], standalone_mode=False)
    assert observed == [True]


def test_crash_funnel_replaces_traceback_with_error_document(tmp_path: Path) -> None:
    """An unexpected exception emits the INTERNAL document (exit 6), not a traceback.

    Runs a real subprocess over a minimal app mounted on the production
    :class:`CadrumoTyperGroup` so the terminal funnel is observed exactly as
    an operator would: stderr payload, no traceback, registered exit code.
    """
    script = tmp_path / "crash_probe.py"
    script.write_text(
        textwrap.dedent(
            """
            import typer
            from cadrumo.entrypoints.cli.command_suggestions import CadrumoTyperGroup

            app = typer.Typer(cls=CadrumoTyperGroup)


            @app.callback()
            def root() -> None:
                "Force group materialisation so CadrumoTyperGroup.main runs."


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
    error = _assert_shared_spine(require_error_document(json_run.stderr))
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

    # The traceback is suppressed on stderr but MUST survive in the diagnostic
    # log, because the document above tells the operator to go read it. Without
    # this half, the stderr assertions above could be satisfied by deleting the
    # log call outright and the crash would become untriageable.
    state_root = tmp_path / "state"
    logged_run = subprocess.run(
        [sys.executable, str(script), "boom", "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
        env=os.environ | {"CADRUMO_LOCAL_STORAGE_ROOT": str(state_root)},
    )
    assert logged_run.returncode == 6, logged_run.stderr
    assert "Traceback" not in logged_run.stderr
    diagnostic_log = state_root / "logs" / "cadrumo.log"
    assert diagnostic_log.is_file(), f"no diagnostic log under {state_root}"
    logged = diagnostic_log.read_text(encoding="utf-8", errors="replace")
    assert "Traceback" in logged, "the crash traceback must reach the diagnostic log"
    assert "synthetic crash for the terminal funnel" in logged
