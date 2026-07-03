"""Shared CLI test runner helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import cache
from typing import NotRequired, Unpack, cast

import click
from click.testing import CliRunner, Result
from typer import Typer
from typer.main import get_command
from typing_extensions import TypedDict

_RUNNER = CliRunner()


class ClickInvokeKwargs(TypedDict, total=False):
    """Typed surface for ``CliRunner.invoke`` keyword arguments.

    Covers the kwargs that AEAT tests legitimately pass.  Any kwarg
    not listed here is a caller mistake and will be caught by the
    type-checker.
    """

    env: NotRequired[Mapping[str, str | None] | None]
    color: NotRequired[bool]
    catch_exceptions: NotRequired[bool]
    input: NotRequired[str | bytes | None]


@cache
def aeat_click_command() -> click.Command:
    """Materialize the Typer app once for default-locale CLI tests."""

    from ..entrypoints.cli import app

    # Typer vendors its own Click fork, so typer.main.get_command is typed to
    # return typer._click.core.Command; it is the same object family at runtime
    # as the upstream click.Command the CliRunner consumes. The cast bridges the
    # static vendored/upstream duality only.
    return cast(click.Command, get_command(app))


@cache
def click_command_for_typer_app(typer_app: Typer) -> click.Command:
    """Materialize any Typer app once for direct app-surface tests."""

    return cast(click.Command, get_command(typer_app))


def invoke_typer_app(
    typer_app: Typer,
    args: Sequence[str],
    **kwargs: Unpack[ClickInvokeKwargs],
) -> Result:
    """Invoke a Typer app through the shared cached Click runner."""

    return _RUNNER.invoke(click_command_for_typer_app(typer_app), list(args), **kwargs)


def invoke_uncached_typer_app(
    typer_app: Typer,
    args: Sequence[str],
    **kwargs: Unpack[ClickInvokeKwargs],
) -> Result:
    """Invoke a Typer app without reusing a cached command tree."""

    return _RUNNER.invoke(cast(click.Command, get_command(typer_app)), list(args), **kwargs)


def invoke_cached_cli(args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    """Invoke the cached AEAT Click command.

    Typer's test runner rebuilds the full Click command tree on every
    invocation. The AEAT tree is large enough that repeated materialization
    dominates test runtime for default-locale CLI smoke tests.

    Only kwargs declared in :class:`ClickInvokeKwargs` are accepted; unknown
    kwargs are a static type error, catching accidental misuse at author time.
    """

    return _RUNNER.invoke(aeat_click_command(), list(args), **kwargs)
