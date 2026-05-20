import pytest
from typer.testing import CliRunner

from aeat.entrypoints.cli._config.__init__ import app
from aeat.entrypoints.cli._errors import CliRefusedBoundaryError

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_apoderado_status_fails_without_profile(runner: CliRunner) -> None:
    result = runner.invoke(app, ["auth", "apoderado", "status"])
    # Must refuse — any non-zero exit code is acceptable (boundary maps
    # refusals to its own exit category).
    assert result.exit_code != 0
    # The _config sub-app is invoked directly so the error boundary
    # (applied only to the root CLI app) is absent. CliRefusedBoundaryError
    # leaks as result.exception. Pin the exception type so an unrelated
    # leaked exception cannot satisfy the check vacuously.
    assert isinstance(result.exception, CliRefusedBoundaryError), (
        f"expected CliRefusedBoundaryError, got {type(result.exception).__name__}: {result.exception}"
    )
    assert "No active profile" in str(result.exception)


def test_apoderado_scopes_list(runner: CliRunner) -> None:
    result = runner.invoke(app, ["auth", "apoderado", "scopes", "list"])
    assert result.exit_code == 0
    assert "GENERAL" in result.output
