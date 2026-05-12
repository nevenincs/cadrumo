"""CLI surface tests for the descriptor-validated ``aeat config set``.

The tests use Typer's ``CliRunner`` to exercise the live command
surface: invalid choice tokens are rejected at the CLI boundary,
descriptor-validated values pass through to ``ProfileRecord.values``,
and the eventual case-insensitive lookup (closed in W12) is gated as
an ``xfail`` until that Step lands.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from aeat.entrypoints.cli._config import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _seed_active_profile() -> None:
    from aeat.application.profile._actions import set_active_profile, set_profile_values
    from aeat.application.workflow._persistence import workflow_state_repository

    repo = workflow_state_repository()
    repo.update(lambda state: set_active_profile(state, "default"))
    repo.update(lambda state: set_profile_values(state, "default", {"tax.id": "12345678Z", "activity": "software"}))


def test_config_set_iva_regime_unknown_value_is_rejected(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    result = cli_runner.invoke(app, ["set", "iva.regime", "XYZ"])
    assert result.exit_code != 0


def test_config_set_iva_regime_accepts_general(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    result = cli_runner.invoke(app, ["set", "iva.regime", "GENERAL"])
    assert result.exit_code == 0
    assert "iva.regime\tGENERAL" in result.output


def test_config_set_tax_residence_ccaa_accepts_madrid(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    result = cli_runner.invoke(app, ["set", "tax.residence.ccaa", "madrid"])
    assert result.exit_code == 0
    assert "tax.residence.ccaa\tmadrid" in result.output


@pytest.mark.xfail(reason="case-insensitive ProfileKey.from_key lands in W12", strict=True)
def test_config_set_tax_id_is_case_insensitive(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    upper = cli_runner.invoke(app, ["set", "TAX.ID", "12345678Z"])
    lower = cli_runner.invoke(app, ["set", "tax.id", "12345678Z"])
    assert upper.exit_code == 0
    assert lower.exit_code == 0
    assert "tax.id\t12345678Z" in upper.output
    assert "tax.id\t12345678Z" in lower.output


def test_config_help_lists_the_new_surfaces(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "setup" in result.output
    assert "status" in result.output
    assert "reset" in result.output
    assert "auth" in result.output
