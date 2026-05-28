"""Shared CLI test runner helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import cache
from typing import Any

import click
from click.testing import CliRunner, Result
from typer.main import get_command
from typing_extensions import NotRequired, TypedDict, Unpack

from aeat.entrypoints.cli import app

_RUNNER = CliRunner()


class ClickInvokeKwargs(TypedDict, total=False):
    """Typed surface for ``CliRunner.invoke`` keyword arguments.

    Covers the kwargs that AEAT tests legitimately pass.  Any kwarg
    not listed here is a caller mistake and will be caught by the
    type-checker.
    """

    env: NotRequired[Mapping[str, str] | None]
    color: NotRequired[bool]
    catch_exceptions: NotRequired[bool]
    input: NotRequired[str | bytes | None]


@cache
def aeat_click_command() -> click.Command:
    """Materialize the Typer app once for default-locale CLI tests."""

    return get_command(app)


def invoke_cached_cli(args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    """Invoke the cached AEAT Click command.

    Typer's test runner rebuilds the full Click command tree on every
    invocation. The AEAT tree is large enough that repeated materialization
    dominates test runtime for default-locale CLI smoke tests.

    Only kwargs declared in :class:`ClickInvokeKwargs` are accepted; unknown
    kwargs are a static type error, catching accidental misuse at author time.
    """

    return _RUNNER.invoke(aeat_click_command(), list(args), **kwargs)
