"""Cached, application-owned CLI invocation helpers for tax CLI tests."""

from __future__ import annotations

from collections.abc import Sequence
from functools import cache
from typing import Unpack, cast

import click
from click.testing import CliRunner, Result
from typer import Typer
from typer.main import get_command

from cadrumo.tests.cli_fixture_ports import ClickInvokeKwargs

_RUNNER = CliRunner()


@cache
def cadrumo_click_command() -> click.Command:
    """Materialize the public AEAT Typer app once for direct CLI tests."""
    from ..main import cli_app

    return cast(click.Command, get_command(cli_app()))


@cache
def click_command_for_typer_app(typer_app: Typer) -> click.Command:
    """Materialize any Typer app once for focused application tests."""
    return cast(click.Command, get_command(typer_app))


def invoke_typer_app(typer_app: Typer, args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    return _RUNNER.invoke(click_command_for_typer_app(typer_app), list(args), **kwargs)


def invoke_uncached_typer_app(typer_app: Typer, args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    return _RUNNER.invoke(cast(click.Command, get_command(typer_app)), list(args), **kwargs)


def invoke_cached_cli(args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    """Invoke the tax command tree without assuming any host-side runtime."""
    return invoke_unbound_cli(args, **kwargs)


def invoke_unbound_cli(args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    """Invoke the public AEAT command app exactly as supplied."""
    return _RUNNER.invoke(cadrumo_click_command(), list(args), **kwargs)


def semantic_cli_output(result: Result) -> str:
    """Return CLI output without terminal styling for semantic assertions."""
    return semantic_cli_text(result.output)


def semantic_cli_text(text: str) -> str:
    """Return one CLI stream without terminal styling."""
    return click.unstyle(text)
