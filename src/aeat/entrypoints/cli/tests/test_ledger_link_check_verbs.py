"""CLI surface tests for ``aeat app ledger link`` and ``aeat app ledger check``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="operator"),
        )
        yield


def test_link_requires_at_least_one_target(cli_runner: CliRunner) -> None:
    """Neither --invoice-id nor --evidence-id supplied surfaces as
    BadParameter; the canonical call is meant to bind something."""

    result = cli_runner.invoke(app, ["app", "ledger", "link", "0" * 64])
    assert result.exit_code != 0, result.output


def test_link_refuses_unknown_transaction_id(cli_runner: CliRunner) -> None:
    """A transaction id absent from the active bucket's catalogue is
    refused before either repository write is attempted."""

    result = cli_runner.invoke(
        app,
        ["app", "ledger", "link", "0" * 64, "--evidence-id", "ev-123"],
    )
    assert result.exit_code != 0, result.output


def test_link_help_advertises_local_only(cli_runner: CliRunner) -> None:
    """Help text must signal `local-only` so the operator cannot mistake
    the verb for an AEAT-contacting call."""

    result = cli_runner.invoke(app, ["app", "ledger", "link", "--help"])
    assert result.exit_code == 0, result.output
    assert any(token in result.output.lower() for token in ("local-only", "local;", "nunca", "csak helyi")), (
        result.output
    )


def test_check_empty_catalogue_is_ready(cli_runner: CliRunner) -> None:
    """An active bucket with no transactions reports ready=true via the
    no-period audit branch and emits zero issues."""

    result = cli_runner.invoke(app, ["app", "ledger", "check"])
    assert result.exit_code == 0, result.output
    assert "checked\t0" in result.output
    assert "issues\t0" in result.output
    assert "ready\ttrue" in result.output


def test_check_help_advertises_local_only(cli_runner: CliRunner) -> None:
    """Help text must signal `local-only`."""

    result = cli_runner.invoke(app, ["app", "ledger", "check", "--help"])
    assert result.exit_code == 0, result.output
    assert any(token in result.output.lower() for token in ("local-only", "local;", "nunca", "csak helyi")), (
        result.output
    )


def test_check_refuses_foreign_bucket_id_without_unlocked_session(cli_runner: CliRunner) -> None:
    """`--bucket-id` must not bypass the active profile storage session."""

    result = cli_runner.invoke(
        app,
        ["app", "ledger", "check", "--bucket-id", "some-other-bucket"],
    )
    assert result.exit_code != 0, result.output
    assert "Storage runtime is not ready" in result.output
