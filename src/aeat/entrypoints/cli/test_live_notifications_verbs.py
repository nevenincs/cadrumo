"""CLI surface tests for `aeat app live notifications {list, show}`."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.entrypoints.cli._app_live import notifications_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'notifications.db').as_posix()}")
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_NOTIFICATIONS_DIR", str(tmp_path / "notifications"))
    dispose_engine()
    try:
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
        yield
    finally:
        dispose_engine()


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def test_notifications_list_is_empty_on_fresh_bucket(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(notifications_app, ["list"])
    assert result.exit_code == 0, result.output
    assert "count\t0" in result.output


def test_notifications_show_refuses_unknown_snapshot(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(notifications_app, ["show", "no-such-snapshot"])
    assert result.exit_code != 0
