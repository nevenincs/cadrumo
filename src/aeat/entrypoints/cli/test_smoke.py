"""Smoke tests for the cli subpackage."""

import pytest
from typer.testing import CliRunner

from ... import cli, errors, logging

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

runner = CliRunner()


def test_smoke_cli() -> None:
    """Asserts the subpackage is importable and conventions hold."""
    assert cli.__doc__ is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__


def test_hello_command() -> None:
    """Asserts the hello command executes correctly."""
    result = runner.invoke(cli.app, ["hello"])
    assert result.exit_code == 0
    assert "Hello from AEAT CLI" in result.stdout


def test_casillas_command_is_registered() -> None:
    """The root CLI must expose the casillas command group."""
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    assert "casillas" in result.stdout
    assert "produce, verify, and export" in result.stdout


def test_financial_command_is_registered() -> None:
    """The root CLI must expose the financial command group."""
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    assert "financial" in result.stdout


def test_auth_help_has_no_unrelated_registry_logs() -> None:
    """`aeat auth --help` must not leak unrelated import-time registry logs."""
    result = runner.invoke(cli.app, ["auth", "--help"])
    assert result.exit_code == 0
    assert "Kent-first auth setup" in result.stdout
    assert "loaded 42 portal entries" not in result.stdout
    assert "loaded 21 modelo entries" not in result.stdout
