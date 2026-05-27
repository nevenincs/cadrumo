"""CLI surface tests for the descriptor-validated profile field setter.

Field-at-a-time profile fact access lives on the engineer-only
``python -m aeat.diagnostics profile`` surface (the operator
``aeat config profile {get,set,unset}`` verbs were retired in favour
of the wizard flow). These tests exercise that diagnostics surface:
invalid choice tokens are rejected at the CLI boundary,
descriptor-validated values pass through to ``ProfileRecord.values``,
and the case-insensitive lookup resolves ``TAX.ID`` and ``tax.id`` to
the same descriptor entry.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.user_profile._orchestration import profile_create_storage_span
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.diagnostics.__main__ import app as diagnostics_app
from aeat.tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        try:
            workflow_state_repository().update(
                lambda state: register_minimal_profile(
                    state,
                    profile_id="default",
                    overrides={"identity.tax_id": "12345678Z", "activities.description": "software"},
                )
            )
            yield
        finally:
            dispose_engine()


def test_config_set_iva_regime_unknown_value_is_rejected(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(diagnostics_app, ["profile", "set", "iva.regime", "XYZ"])
    assert result.exit_code != 0


def test_config_set_iva_regime_accepts_general(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(diagnostics_app, ["profile", "set", "iva.regime", "GENERAL"])
    assert result.exit_code == 0, result.output
    assert "iva.regime\tGENERAL" in result.output


def test_config_set_tax_residence_ccaa_accepts_madrid(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(diagnostics_app, ["profile", "set", "tax_residence.ccaa", "madrid"])
    assert result.exit_code == 0, result.output
    assert "tax_residence.ccaa\tmadrid" in result.output


def test_config_set_tax_id_is_case_insensitive(cli_runner: CliRunner) -> None:
    """``ProfileKey.from_key`` resolves ``IDENTITY.TAX_ID`` and ``identity.tax_id`` to the same entry."""

    upper = cli_runner.invoke(diagnostics_app, ["profile", "set", "IDENTITY.TAX_ID", "12345678Z"])
    lower = cli_runner.invoke(diagnostics_app, ["profile", "set", "identity.tax_id", "12345678Z"])
    assert upper.exit_code == 0, upper.output
    assert lower.exit_code == 0, lower.output
    assert "identity.tax_id\t12345678Z" in upper.output
    assert "identity.tax_id\t12345678Z" in lower.output


def test_profile_help_lists_field_verbs(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(diagnostics_app, ["profile", "--help"])
    assert result.exit_code == 0
    assert "set" in result.output
    assert "get" in result.output
    assert "unset" in result.output
