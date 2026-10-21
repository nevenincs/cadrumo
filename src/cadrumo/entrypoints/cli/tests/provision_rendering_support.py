"""Render a ``config provision`` leaf from the settled result of its real operation.

The operation runs through the real registry, supervisor, journal and operand
store, exactly as a profile worker runs it, and the leaf's own emitter renders
the public result it settled with. Only the transport between the two is
absent, which the native runtime suites cover.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import pytest
import typer
import typer.main

__all__ = ["RenderedLeaf", "render_leaf"]


@dataclass(frozen=True, slots=True)
class RenderedLeaf:
    """What one leaf wrote to standard output and the exit code it ended with."""

    exit_code: int
    output: str

    @property
    def envelope(self) -> dict[str, object]:
        """Return the JSON envelope a ``--format json`` run emitted."""
        return cast(dict[str, object], json.loads(self.output))

    @property
    def result(self) -> dict[str, object]:
        """Return the envelope's result document."""
        return cast(dict[str, object], self.envelope["result"])

    @property
    def cells(self) -> dict[str, str]:
        """Return a ``--format text`` run's tab-separated lines by their first cell."""
        return dict(line.split("\t", 1) for line in self.output.splitlines() if "\t" in line)


def render_leaf(
    emit: Callable[[typer.Context], None], *, output_format: str, capsys: pytest.CaptureFixture[str]
) -> RenderedLeaf:
    """Run ``emit`` under a context requesting ``output_format`` and capture what it wrote."""
    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    context = typer.Context(typer.main.get_command(app), obj={"format": output_format})
    capsys.readouterr()
    try:
        emit(context)
    except typer.Exit as stopped:
        exit_code = stopped.exit_code
    else:
        exit_code = 0
    return RenderedLeaf(exit_code=exit_code, output=capsys.readouterr().out)
