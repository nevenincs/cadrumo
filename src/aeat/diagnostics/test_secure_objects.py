"""Smoke tests for the engineer-only `python -m aeat.diagnostics` entrypoint.

The secure-objects subcommand re-homes the previous
`aeat config repair list NAMESPACE` operator verb. These tests
exercise the Typer CLI end-to-end against the real
`build_repair_list_report` application service so a future
regression that breaks the diagnostics surface surfaces here, not
in production.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.adapters.persistence.storage.sql.engine import create_engine_from_settings, dispose_engine
from aeat.core.config import Settings
from aeat.diagnostics.__main__ import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Wire the diagnostics CLI at a fresh per-test SQLite database."""

    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{tmp_path / 'diag.db'}")
    override_master_key_provider(EphemeralMasterKeyProvider())
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{tmp_path / 'diag.db'}"))
    Base.metadata.create_all(engine)
    SecureObjectRepository(engine=engine)
    try:
        yield
    finally:
        engine.dispose()
        override_master_key_provider(None)
        dispose_engine()


def test_secure_objects_list_namespace_argument_required(runner: CliRunner) -> None:
    """Calling `secure-objects list` with no namespace surfaces a usage error."""

    result = runner.invoke(app, ["secure-objects", "list"])

    assert result.exit_code != 0
    assert "namespace" in result.output.lower() or "missing" in result.output.lower()


def test_secure_objects_list_empty_namespace_emits_zero_count(runner: CliRunner) -> None:
    """An empty namespace surfaces a zero-row count without raising."""

    result = runner.invoke(app, ["secure-objects", "list", "aeat.test.empty"])

    assert result.exit_code == 0
    assert "namespace\taeat.test.empty" in result.output
    assert "count\t0" in result.output


def test_secure_objects_list_rejects_conflicting_flags(runner: CliRunner) -> None:
    """`--all` and `--unreadable` cannot be combined."""

    result = runner.invoke(
        app,
        ["secure-objects", "list", "aeat.test.empty", "--all", "--unreadable"],
    )

    assert result.exit_code != 0
    assert "all" in result.output.lower() and "unreadable" in result.output.lower()
