import pytest
from typer.testing import CliRunner

from aeat.entrypoints.cli._config.__init__ import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_apoderado_status_fails_without_profile(runner: CliRunner) -> None:
    result = runner.invoke(app, ["auth", "apoderado", "status"])
    assert result.exit_code == 1
    assert result.exception is not None
    assert "no_active_profile" in str(result.exception) or "No active profile" in str(result.exception)


def test_apoderado_scopes_list(runner: CliRunner) -> None:
    result = runner.invoke(app, ["auth", "apoderado", "scopes", "list"])
    assert result.exit_code == 0
    assert "GENERAL" in result.output
