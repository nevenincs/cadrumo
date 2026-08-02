"""Shared supplied-date boundary tests for diagnostics and ledger reporting."""

from __future__ import annotations

import pytest
import typer

from .._app_diagnostics import _parse_iso_date as parse_diagnostics_date
from .._ledger_read_cli import _parse_iso_date as parse_ledger_date

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("parser", (parse_diagnostics_date, parse_ledger_date))
def test_supplied_blank_date_bound_refuses(parser: object) -> None:
    """A blank supplied --since is never widened into an unbounded query."""
    with pytest.raises(typer.BadParameter):
        parser("", "--since")


@pytest.mark.parametrize("parser", (parse_diagnostics_date, parse_ledger_date))
def test_absent_date_bound_remains_optional(parser: object) -> None:
    """Only an omitted date option remains an unbounded query."""
    assert parser(None, "--since") is None
