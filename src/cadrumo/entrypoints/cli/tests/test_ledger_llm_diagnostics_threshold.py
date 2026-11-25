"""The LLM diagnostics threshold is read with the canonical decimal grammar and bounded to a share of one.

A float option admitted ``nan`` (which failed as a raw arithmetic error) and
scientific forms; the threshold is refused before the runtime is asked anything.
"""

from __future__ import annotations

import pytest
import typer
import typer.main

from ..ledger_read_commands import ledger_llm_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _context() -> typer.Context:
    app = typer.Typer()

    @app.command()
    def diagnostics() -> None:
        """Stand in for the diagnostics command whose context the boundary receives."""

    return typer.Context(typer.main.get_command(app))


@pytest.mark.parametrize("written", ["nan", "inf", "1e-1", "0,5", "1.5", "-0.1"])
def test_a_threshold_that_is_not_a_canonical_share_of_one_is_refused(written: str) -> None:
    with pytest.raises(typer.BadParameter):
        ledger_llm_diagnostics(_context(), low_confidence_below=written)
