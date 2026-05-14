"""CLI surface tests for the descriptor-validated ``aeat config set``.

The tests use Typer's ``CliRunner`` to exercise the live command
surface: invalid choice tokens are rejected at the CLI boundary,
descriptor-validated values pass through to ``ProfileRecord.values``,
and the case-insensitive lookup resolves ``TAX.ID`` and ``tax.id`` to
the same descriptor entry.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from aeat.entrypoints.cli._config import profile_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _seed_active_profile() -> None:
    from aeat.application.user_profile._testing import register_minimal_profile
    from aeat.application.workflow._persistence import workflow_state_repository

    repo = workflow_state_repository()
    repo.update(
        lambda state: register_minimal_profile(
            state,
            profile_id="default",
            overrides={"identity.tax_id": "12345678Z", "activities.description": "software"},
        )
    )


def test_config_set_iva_regime_unknown_value_is_rejected(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    result = cli_runner.invoke(profile_app, ["set", "iva.regime", "XYZ"])
    assert result.exit_code != 0


def test_config_set_iva_regime_accepts_general(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    result = cli_runner.invoke(profile_app, ["set", "iva.regime", "GENERAL"])
    assert result.exit_code == 0
    assert "iva.regime\tGENERAL" in result.output


def test_config_set_tax_residence_ccaa_accepts_madrid(cli_runner: CliRunner) -> None:
    _seed_active_profile()
    result = cli_runner.invoke(profile_app, ["set", "tax_residence.ccaa", "madrid"])
    assert result.exit_code == 0
    assert "tax_residence.ccaa\tmadrid" in result.output


def test_config_set_tax_id_is_case_insensitive(cli_runner: CliRunner) -> None:
    """``ProfileKey.from_key`` resolves ``IDENTITY.TAX_ID`` and ``identity.tax_id`` to the same entry."""

    _seed_active_profile()
    upper = cli_runner.invoke(profile_app, ["set", "IDENTITY.TAX_ID", "12345678Z"])
    lower = cli_runner.invoke(profile_app, ["set", "identity.tax_id", "12345678Z"])
    assert upper.exit_code == 0
    assert lower.exit_code == 0
    assert "identity.tax_id\t12345678Z" in upper.output
    assert "identity.tax_id\t12345678Z" in lower.output


def test_profile_help_lists_canonical_verbs(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(profile_app, ["--help"])
    assert result.exit_code == 0
    assert "set" in result.output
    assert "get" in result.output
    assert "unset" in result.output
    assert "list" in result.output
    assert "status" in result.output
