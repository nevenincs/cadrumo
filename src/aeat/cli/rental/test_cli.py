"""End-to-end CLI tests for ``aeat rental`` (#454)."""

from __future__ import annotations

import json
import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ... import cli
from ...storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from ...storage._crypto import KEY_SIZE
from ...storage._orm import Base
from ...storage.engine import create_engine_from_settings, dispose_engine

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


@pytest.fixture(autouse=True)
def _master_key() -> Iterator[None]:
    override_master_key_provider(EphemeralMasterKeyProvider(key=secrets.token_bytes(KEY_SIZE)))
    try:
        yield
    finally:
        override_master_key_provider(None)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Bind every CLI invocation to a tmp_path SQLite database."""
    db_path = tmp_path / "rental-cli.db"
    url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("AEAT_DATABASE_URL", url)
    dispose_engine()
    from ...config import load_settings

    settings = load_settings()
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    engine.dispose()
    try:
        yield db_path
    finally:
        dispose_engine()


def _runner() -> CliRunner:
    return CliRunner()


def _add_finca(runner: CliRunner) -> None:
    result = runner.invoke(
        cli.app,
        [
            "rental",
            "finca",
            "add",
            "--identifier",
            "calle-mayor-12",
            "--address",
            "Calle Mayor 12, Madrid",
            "--valor-catastral-total",
            "120000.00",
            "--valor-catastral-construccion",
            "80000.00",
            "--coste-adquisicion",
            "180000.00",
            "--coste-adquisicion-construccion",
            "100000.00",
            "--acquisition-date",
            "2010-01-01",
            "--use-type",
            "VIVIENDA_ARRENDADA",
        ],
    )
    assert result.exit_code == 0, result.stdout


class TestSubAppRegistration:
    def test_root_cli_help_lists_rental(self) -> None:
        result = _runner().invoke(cli.app, ["--help"])
        assert result.exit_code == 0
        assert "rental" in result.stdout

    def test_rental_help_lists_subgroups(self) -> None:
        result = _runner().invoke(cli.app, ["rental", "--help"])
        assert result.exit_code == 0
        for group in ("finca", "contract", "income", "expense", "anexo-c"):
            assert group in result.stdout


class TestFincaAddListShow:
    def test_add_list_show_round_trip(self) -> None:
        runner = _runner()
        _add_finca(runner)
        list_result = runner.invoke(cli.app, ["rental", "finca", "list"])
        assert list_result.exit_code == 0
        assert "calle-mayor-12" in list_result.stdout

        show_result = runner.invoke(cli.app, ["rental", "finca", "show", "calle-mayor-12"])
        assert show_result.exit_code == 0
        assert "Calle Mayor 12" in show_result.stdout

    def test_show_unknown_finca_returns_error(self) -> None:
        runner = _runner()
        result = runner.invoke(cli.app, ["rental", "finca", "show", "no-such-finca"])
        assert result.exit_code != 0
        assert "no-such-finca" in result.stderr or "not found" in result.stderr.lower()

    def test_list_json_round_trip(self) -> None:
        runner = _runner()
        _add_finca(runner)
        result = runner.invoke(cli.app, ["--json", "rental", "finca", "list"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["command"] == "rental finca list"
        assert payload["schema_version"] == "1"
        assert isinstance(payload["result"], list)
        assert payload["result"][0]["identifier"] == "calle-mayor-12"


class TestAnexoCComputeEndToEnd:
    def test_full_pipeline_with_register_drives_aggregates(self) -> None:
        runner = _runner()
        _add_finca(runner)
        contract_result = runner.invoke(
            cli.app,
            [
                "rental",
                "contract",
                "add",
                "--finca",
                "calle-mayor-12",
                "--celebration-date",
                "2024-01-01",
                "--initial-rent",
                "1000.00",
            ],
        )
        assert contract_result.exit_code == 0, contract_result.stdout
        # Extract the contract id from the human echo: "Registered contract id=N on finca ..."
        for token in contract_result.stdout.split():
            if token.startswith("id="):
                contract_id = int(token[3:])
                break
        else:
            raise AssertionError(contract_result.stdout)
        income_result = runner.invoke(
            cli.app,
            [
                "rental",
                "income",
                "record",
                "--contract",
                str(contract_id),
                "--period",
                "2025",
                "--amount",
                "12000.00",
                "--dias-alquilados",
                "365",
            ],
        )
        assert income_result.exit_code == 0, income_result.stdout

        result = runner.invoke(
            cli.app,
            ["--json", "rental", "anexo-c", "compute", "--year", "2025"],
        )
        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout)
        aggregates = payload["result"]["aggregates"]
        assert aggregates["casilla_0061"] == "12000.00"
        # 0072: basis = max(100000, 80000) = 100000 * 0.03 = 3000.
        assert aggregates["casilla_0072"] == "3000.00"
        # No expenses → 0066 = 0; rendimiento = 12000 - 0 - 3000 = 9000;
        # tier 50 → reducción 4500.
        assert aggregates["casilla_0066"] == "0.00"
        assert aggregates["casilla_0078"] == "4500.00"
