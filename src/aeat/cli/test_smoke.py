"""Smoke tests for the cli subpackage."""

import pytest
from typer.testing import CliRunner

import aeat.cli
import aeat.errors
import aeat.logging

runner = CliRunner()


@pytest.mark.unit
def test_smoke_cli() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert aeat.cli.__doc__ is not None
    assert issubclass(aeat.errors.AeatError, Exception)
    assert aeat.logging.get_logger(__name__).name == __name__


@pytest.mark.unit
def test_hello_command() -> None:
    """Asserts the hello command executes correctly."""
    result = runner.invoke(aeat.cli.app, ["hello"])
    assert result.exit_code == 0
    assert "Hello from AEAT CLI" in result.stdout
