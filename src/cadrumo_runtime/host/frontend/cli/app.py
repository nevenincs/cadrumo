"""Inject runtime admission into the independently owned AEAT command graph."""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from inspect import BoundArguments
from typing import cast

import typer

from cadrumo.entrypoints.cli.command_lifecycle import dispatch_cli_behavior
from cadrumo.entrypoints.cli.invocation_services import CliInvocationServices, bind_invocation_services
from cadrumo.entrypoints.cli.main import cli_app
from cadrumo_client.commands.graph import CommandSpecGraph
from cadrumo_client.commands.spec import CommandSpec

from .tui_launcher import launch_tui


def _dispatch(
    graph: CommandSpecGraph,
    spec: CommandSpec,
    bound: BoundArguments,
    behavior: Callable[[], object],
) -> object:
    from cadrumo_client.commands.profile_admission import activate_profile

    from .profile_services import delete_profile

    context = bound.arguments.get(spec.invocation.context_parameter or "")
    if context is not None and callable(getattr(context, "find_root", None)):
        bind_invocation_services(
            cast(typer.Context, context), CliInvocationServices(launch_tui=launch_tui, delete_profile=delete_profile)
        )
    return dispatch_cli_behavior(graph, spec, bound, behavior, activate_connection=activate_profile)


@cache
def aeat_cli_app() -> typer.Typer:
    """Compose the product CLI with its managing runtime's admission service."""
    return cli_app(dispatcher=_dispatch)
