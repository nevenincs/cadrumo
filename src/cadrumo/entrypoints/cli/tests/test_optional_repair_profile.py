"""The tax CLI requests optional repair admission from its owning host."""

from collections.abc import Callable
from inspect import BoundArguments

import pytest
import typer

from cadrumo_client.commands.graph import CommandSpecGraph
from cadrumo_client.commands.spec import CommandSpec

from ..command_lifecycle import dispatch_cli_behavior
from ..main import cli_app
from .cli_runner import invoke_typer_app

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("host_supplied", (False, True))
def test_repair_requests_only_the_supplied_optional_admission(
    monkeypatch: pytest.MonkeyPatch, host_supplied: bool
) -> None:
    admitted: list[typer.Context] = []

    def admit(ctx: typer.Context) -> None:
        admitted.append(ctx)

    def report(ctx: typer.Context) -> None:
        assert admitted == ([ctx] if host_supplied else [])
        typer.echo("repair-bootstrap-reached")

    def dispatch(
        graph: CommandSpecGraph,
        spec: CommandSpec,
        bound: BoundArguments,
        behavior: Callable[[], object],
    ) -> object:
        return dispatch_cli_behavior(
            graph, spec, bound, behavior, bind_optional_profile=admit if host_supplied else None
        )

    monkeypatch.setattr("cadrumo.entrypoints.cli.config.repair_commands.repair", report)
    result = invoke_typer_app(cli_app(dispatcher=dispatch), ["config", "repair"])
    assert result.exit_code == 0, result.output
    assert "repair-bootstrap-reached" in result.output
