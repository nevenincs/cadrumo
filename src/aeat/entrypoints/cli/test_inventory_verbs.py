"""CLI surface tests for `aeat app ledger inventory {list, create, movement add, valuation preview}`."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.entrypoints.cli._ledger import inventory_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'inventory-verbs.db').as_posix()}")
    monkeypatch.setenv("AEAT_LEDGERS_DIR", str(tmp_path / "ledgers"))
    dispose_engine()
    with EphemeralMasterKeyProvider():
        try:
            workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
            yield
        finally:
            dispose_engine()


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def test_inventory_list_starts_empty(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(inventory_app, ["list"])
    assert result.exit_code == 0, result.output
    assert "count\t0" in result.output


def test_inventory_create_persists(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(
        inventory_app,
        ["create", "act-1", "--year", "2026", "--valuation-method", "fifo", "--opening-stock", "100.00"],
    )
    assert result.exit_code == 0, result.output
    assert "actividad_id\tact-1" in result.output
    assert "valuation_method\tfifo" in result.output
    assert "opening_stock\t100.00" in result.output

    list_result = cli_runner.invoke(inventory_app, ["list"])
    assert list_result.exit_code == 0, list_result.output
    assert "act-1\t2026\tfifo" in list_result.output


def test_inventory_create_refuses_duplicate(cli_runner: CliRunner) -> None:
    cli_runner.invoke(
        inventory_app,
        ["create", "act-1", "--year", "2026", "--valuation-method", "fifo", "--opening-stock", "0"],
    )
    result = cli_runner.invoke(
        inventory_app,
        ["create", "act-1", "--year", "2026", "--valuation-method", "fifo", "--opening-stock", "0"],
    )
    assert result.exit_code != 0


def test_inventory_movement_add_records_against_existing_ledger(cli_runner: CliRunner) -> None:
    cli_runner.invoke(
        inventory_app,
        ["create", "act-1", "--year", "2026", "--valuation-method", "fifo", "--opening-stock", "0"],
    )
    result = cli_runner.invoke(
        inventory_app,
        [
            "movement",
            "add",
            "--actividad-id",
            "act-1",
            "--year",
            "2026",
            "--movement-id",
            "mov-1",
            "--date",
            "2026-03-15",
            "--kind",
            "purchase",
            "--quantity",
            "10",
            "--unit-cost",
            "5.50",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "movements\t1" in result.output
