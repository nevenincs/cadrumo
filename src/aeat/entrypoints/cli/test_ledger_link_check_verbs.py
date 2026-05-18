"""CLI surface tests for ``aeat app ledger link`` and ``aeat app ledger check``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.entrypoints.cli import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'link-check.db').as_posix()}")
    dispose_engine()
    with EphemeralMasterKeyProvider():
        try:
            workflow_state_repository().update(
                lambda state: register_minimal_profile(state, profile_id="operator"),
            )
            yield
        finally:
            dispose_engine()


def test_link_requires_at_least_one_target(cli_runner: CliRunner) -> None:
    """Neither --invoice-id nor --evidence-id supplied surfaces as
    BadParameter; the canonical call is meant to bind something."""

    result = cli_runner.invoke(app, ["app", "ledger", "link", "--id", "0" * 64])
    assert result.exit_code != 0, result.output


def test_link_refuses_unknown_transaction_id(cli_runner: CliRunner) -> None:
    """A transaction id absent from the active bucket's catalogue is
    refused before either repository write is attempted."""

    result = cli_runner.invoke(
        app,
        ["app", "ledger", "link", "--id", "0" * 64, "--evidence-id", "ev-123"],
    )
    assert result.exit_code != 0, result.output


def test_link_help_advertises_local_only(cli_runner: CliRunner) -> None:
    """Help text must signal `local-only` so the operator cannot mistake
    the verb for an AEAT-contacting call."""

    result = cli_runner.invoke(app, ["app", "ledger", "link", "--help"])
    assert result.exit_code == 0, result.output
    assert any(
        token in result.output.lower()
        for token in ("local-only", "local;", "nunca", "csak helyi")
    ), result.output


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
    assert any(
        token in result.output.lower()
        for token in ("local-only", "local;", "nunca", "csak helyi")
    ), result.output


def test_check_accepts_explicit_bucket_id(cli_runner: CliRunner) -> None:
    """`--bucket-id` overrides the active profile bucket lookup so the
    verb can probe foreign buckets without switching profile. With no
    transactions in the supplied bucket the report is still ready."""

    result = cli_runner.invoke(
        app, ["app", "ledger", "check", "--bucket-id", "some-other-bucket"],
    )
    assert result.exit_code == 0, result.output
    assert "bucket\tsome-other-bucket" in result.output
    assert "checked\t0" in result.output
    assert "ready\ttrue" in result.output
