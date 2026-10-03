"""Independent contract tests for diagnostics CommandSpec authority."""

from __future__ import annotations

import pytest
import typer.core
from typer.testing import CliRunner

from ....core.config import override_settings
from .._app_diagnostics_command_specs import DIAGNOSTICS_COMMAND_SPECS
from .._command_runtime import build_command_subtree
from .._command_shared_contracts import SchemaState
from .._command_target import resolve_deferred_target
from .._root_command_specs import ROOT_COMMAND_SPECS
from .._stdio import disable_rich_cli_rendering
from ..command_graph import CommandSpecGraph

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _production_cli_help_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(typer.core, "HAS_RICH", typer.core.HAS_RICH)
    disable_rich_cli_rendering()


def _graph() -> CommandSpecGraph:
    return CommandSpecGraph((*ROOT_COMMAND_SPECS, *DIAGNOSTICS_COMMAND_SPECS))


def _plain_help_text(output: str) -> str:
    borders_removed = output.translate(str.maketrans("", "", "│┌┐└┘─"))
    return " ".join(borders_removed.split())


def test_diagnostics_specs_match_the_independent_operator_path_set() -> None:
    expected = {
        ("aeat", "app", "diagnostics"),
        ("aeat", "app", "diagnostics", "errors"),
        ("aeat", "app", "diagnostics", "latency"),
        ("aeat", "app", "diagnostics", "llm-usage"),
        ("aeat", "app", "diagnostics", "run-health"),
        ("aeat", "app", "diagnostics", "runs"),
        ("aeat", "app", "diagnostics", "telemetry"),
        ("aeat", "app", "diagnostics", "telemetry", "flush"),
        ("aeat", "app", "diagnostics", "telemetry", "status"),
    }

    actual = {node.path for node in _graph().nodes() if node.path[1:3] == ("app", "diagnostics")}

    assert actual == expected


def test_diagnostics_leaf_targets_and_schemas_are_public_and_resolvable() -> None:
    leaves = [spec for spec in DIAGNOSTICS_COMMAND_SPECS if spec.kind == "leaf"]
    assert len(leaves) == 7
    for spec in leaves:
        assert spec.handler is not None
        assert spec.handler.target is not None
        assert resolve_deferred_target(spec.handler.target)
        assert spec.result_schema.state is SchemaState.TARGET
        assert spec.result_schema.target is not None
        assert resolve_deferred_target(spec.result_schema.target)


def test_diagnostics_runtime_compiles_representative_nested_help() -> None:
    app = build_command_subtree(_graph(), "app_diagnostics")

    runs = CliRunner().invoke(app, ["runs", "--help"])
    flush = CliRunner().invoke(app, ["telemetry", "flush", "--help"])

    assert runs.exit_code == 0, runs.output
    assert "--limit" in runs.output
    assert flush.exit_code == 0, flush.output
    assert "--dry-run / --no-dry-run" in flush.output
    assert "--acknowledge-remote-telemetry" in flush.output


@pytest.mark.parametrize(
    ("language", "expected_since_help"),
    (
        (
            "ca",
            "Data ISO (AAAA-MM-DD) inferior inclusiva per als registres d'execució de l'LLM.",
        ),
        ("en", "Inclusive lower ISO date (YYYY-MM-DD) bound on LLM run records."),
        (
            "es",
            "Fecha ISO (AAAA-MM-DD) inferior inclusiva para los registros de ejecución del LLM.",
        ),
        (
            "hu",
            "Az LLM-futásnaplók alsó (befogadó) ISO dátumhatára (ÉÉÉÉ-HH-NN).",
        ),
    ),
)
def test_since_help_is_shared_and_rendered_in_every_supported_locale(
    language: str,
    expected_since_help: str,
) -> None:
    with override_settings(cadrumo_output_language=language):
        app = build_command_subtree(_graph(), "app_diagnostics")
        run_health = CliRunner().invoke(app, ["run-health", "--help"])
        runs = CliRunner().invoke(app, ["runs", "--help"])

    assert run_health.exit_code == 0, run_health.output
    assert runs.exit_code == 0, runs.output
    assert expected_since_help in _plain_help_text(run_health.output)
    assert expected_since_help in _plain_help_text(runs.output)
