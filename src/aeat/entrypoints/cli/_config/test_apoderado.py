from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.entrypoints.cli import app as root_app
from aeat.entrypoints.cli._config.__init__ import app
from aeat.entrypoints.cli._errors import CliRefusedBoundaryError
from aeat.tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def _per_bucket_backend(tmp_path: Path) -> Iterator[Path]:
    """Per-bucket storage with the production file-backed custody path.

    Each profile bucket resolves its own SQLite file from the
    active-profile pointer chain — the production cold-start path.
    """
    dispose_engine()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        try:
            yield storage_root
        finally:
            dispose_engine()


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


def test_apoderado_happy_path_against_active_profile(_per_bucket_backend: Path) -> None:
    """status/configure/clear succeed against the active profile.

    The active-profile pointer carries the immutable UUID identity; the
    apoderado verbs must resolve that UUID directly, not feed it to the
    label-based ``read_profile_bucket`` resolver. This exercises the
    normal active-profile path the no-active-profile test cannot reach.
    """
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    runner = CliRunner()
    create = runner.invoke(
        root_app,
        [
            "config", "profile", "create", "myco",
            "--quiet",
            "--tax-id", "12345678Z",
            "--name", "MyCo",
            "--activity", "design",
            "--iva-regime", "GENERAL",
        ],
    )
    assert create.exit_code == 0, f"create failed: {create.output}"

    # status: exit 0 on the active profile (previously crashed with
    # AttributeError because the UUID never matched a label).
    dispose_engine()
    status = runner.invoke(root_app, ["config", "auth", "apoderado", "status"])
    assert status.exit_code == 0, f"apoderado status failed: {status.output}"
    assert "configured\tFalse" in status.output

    # configure: exit 0, persists the apoderado config.
    dispose_engine()
    configure = runner.invoke(
        root_app,
        [
            "config", "auth", "apoderado", "configure",
            "--represented-nif", "87654321X",
            "--scope", "RENT",
        ],
    )
    assert configure.exit_code == 0, f"apoderado configure failed: {configure.output}"
    assert "represented_nif\t87654321X" in configure.output
    assert "RENT" in configure.output

    # status now reflects the configured state.
    dispose_engine()
    status_after = runner.invoke(root_app, ["config", "auth", "apoderado", "status"])
    assert status_after.exit_code == 0, status_after.output
    assert "configured\tTrue" in status_after.output

    # clear: exit 0, retires the apoderado config.
    dispose_engine()
    clear = runner.invoke(root_app, ["config", "auth", "apoderado", "clear"])
    assert clear.exit_code == 0, f"apoderado clear failed: {clear.output}"
    assert "cleared\tTrue" in clear.output
