"""Shared CLI test runner helpers."""

from __future__ import annotations

from collections.abc import Sequence
from functools import cache
from typing import Any

import click
from click.testing import CliRunner, Result
from typer.main import get_command

from aeat.entrypoints.cli import app

_RUNNER = CliRunner()


@cache
def aeat_click_command() -> click.Command:
    """Materialize the Typer app once for default-locale CLI tests."""

    return get_command(app)


def invoke_cached_cli(args: Sequence[str], **kwargs: Any) -> Result:
    """Invoke the cached AEAT Click command.

    Typer's test runner rebuilds the full Click command tree on every
    invocation. The AEAT tree is large enough that repeated materialization
    dominates test runtime for default-locale CLI smoke tests.

    ``**kwargs: Any``: forwarded verbatim to ``CliRunner.invoke``; the Click
    stubs accept many heterogeneous optional kwargs so a delegation wrapper
    correctly uses ``Any`` here.
    """

    return _RUNNER.invoke(aeat_click_command(), list(args), **kwargs)
