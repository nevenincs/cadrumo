from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from .....tests.secure_sql import isolated_profile_storage_root
from ... import app as root_app
from ..._errors import CliRefusedBoundaryError
from ..__init__ import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def _per_bucket_backend(tmp_path: Path) -> Iterator[Path]:
    """Per-bucket storage with the production file-backed custody path.

    Each profile bucket resolves its own SQLite file from the
    active-profile pointer chain — the production cold-start path.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


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
    # CliRefusedBoundaryError carries the operator-facing copy via its
    # translated_message key; str(exception) is intentionally empty
    # because the rendering happens in the boundary, not on the exception.
    assert result.exception.translated_message == "cli.config.profile.no_active_profile"


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
    from .....adapters.persistence.storage.sql.engine import dispose_engine

    runner = CliRunner()
    create = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "myco",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--name",
            "MyCo",
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
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
            "config",
            "auth",
            "apoderado",
            "configure",
            "--represented-nif",
            "87654321X",
            "--scope",
            "RENT",
        ],
    )
    assert configure.exit_code == 0, f"apoderado configure failed: {configure.output}"
    # NIF is identity-class data: the CLI success-output redactor rewrites
    # any 8-digits+letter NIF span via SHA256_PREFIX, so the rendered line
    # carries the fingerprint, not the raw NIF. Pin both the field label
    # and the fingerprint shape so an unintended raw leak would still fail.
    assert "represented_nif\tsha256:" in configure.output
    assert "87654321X" not in configure.output, f"raw NIF leaked into CLI output: {configure.output!r}"
    assert "RENT" in configure.output

    # status now reflects the configured state.
    dispose_engine()
    status_after = runner.invoke(root_app, ["config", "auth", "apoderado", "status"])
    assert status_after.exit_code == 0, status_after.output
    assert "configured\tTrue" in status_after.output

    # check: refuses. It is the live-verification verb and the live AEAT-read
    # path is sealed, so it must NOT silently re-read the stored config and
    # present it as a live result — it refuses with the registered REFUSED
    # copy instead. Any non-zero exit is acceptable; the refusal carries the
    # operator-facing message.
    dispose_engine()
    check = runner.invoke(root_app, ["config", "auth", "apoderado", "check"])
    assert check.exit_code != 0, f"apoderado check should refuse, got: {check.output}"
    assert "configured\tTrue" not in check.output, (
        f"check leaked a stored-config status as a live result: {check.output!r}"
    )

    # clear: exit 0, retires the apoderado config.
    dispose_engine()
    clear = runner.invoke(root_app, ["config", "auth", "apoderado", "clear"])
    assert clear.exit_code == 0, f"apoderado clear failed: {clear.output}"
    assert "cleared\tTrue" in clear.output
