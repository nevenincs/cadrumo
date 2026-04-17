"""Smoke tests for the cli subpackage."""

import pytest
from typer.testing import CliRunner

import aeat.cli
import aeat.errors
import aeat.logging

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

runner = CliRunner()


def test_smoke_cli() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert aeat.cli.__doc__ is not None
    assert issubclass(aeat.errors.AeatError, Exception)
    assert aeat.logging.get_logger(__name__).name == __name__


def test_hello_command() -> None:
    """Asserts the hello command executes correctly."""
    result = runner.invoke(aeat.cli.app, ["hello"])
    assert result.exit_code == 0
    assert "Hello from AEAT CLI" in result.stdout


def test_casillas_command_is_registered() -> None:
    """The root CLI must expose the casillas command group."""
    result = runner.invoke(aeat.cli.app, ["--help"])
    assert result.exit_code == 0
    assert "casillas" in result.stdout


def test_financial_command_is_registered() -> None:
    """The root CLI must expose the financial command group."""
    result = runner.invoke(aeat.cli.app, ["--help"])
    assert result.exit_code == 0
    assert "financial" in result.stdout
