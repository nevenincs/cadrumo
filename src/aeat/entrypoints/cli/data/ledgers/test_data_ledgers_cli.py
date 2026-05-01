"""CLI tests for the clean data-ledgers command surface."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from typer.testing import CliRunner

from .....adapters.persistence.storage import EphemeralMasterKeyProvider, override_master_key_provider
from ... import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]

_RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def _ephemeral_master_key() -> Iterator[None]:
    override_master_key_provider(EphemeralMasterKeyProvider())
    try:
        yield
    finally:
        override_master_key_provider(None)


def test_data_ledgers_assets_vat_add_list_show_and_amortization_json(tmp_path) -> None:
    storage = str(tmp_path)
    add = _RUNNER.invoke(
        app,
        [
            "--json",
            "data",
            "ledgers",
            "assets",
            "add",
            "pc-2024",
            "--description",
            "work pc",
            "--asset-class",
            "electronica.equipos_tratamiento_informacion",
            "--taxable-base",
            "1000.00",
            "--vat-rate",
            "21.00",
            "--deductible-vat-ratio",
            "0.50",
            "--acquisition-date",
            "2025-01-01",
            "--storage-dir",
            storage,
        ],
    )
    assert add.exit_code == 0, add.output
    add_payload = json.loads(add.output)
    assert add_payload["command"] == "data ledgers assets add"
    assert add_payload["result"]["asset"]["cost_basis"] == "1105.00"

    listed = _RUNNER.invoke(app, ["--json", "data", "ledgers", "assets", "list", "--storage-dir", storage])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)["result"][0]["identifier"] == "pc-2024"

    shown = _RUNNER.invoke(app, ["--json", "data", "ledgers", "assets", "show", "pc-2024", "--storage-dir", storage])
    assert shown.exit_code == 0, shown.output
    assert json.loads(shown.output)["result"]["asset"]["vat_amount"] == "210.00"

    preview = _RUNNER.invoke(
        app,
        [
            "--json",
            "data",
            "ledgers",
            "assets",
            "amortization",
            "preview",
            "--asset",
            "pc-2024",
            "--year",
            "2025",
            "--storage-dir",
            storage,
        ],
    )
    assert preview.exit_code == 0, preview.output
    assert json.loads(preview.output)["result"]["amount"] == "276.25"

    applied = _RUNNER.invoke(
        app,
        [
            "--json",
            "data",
            "ledgers",
            "assets",
            "amortization",
            "apply",
            "--asset",
            "pc-2024",
            "--year",
            "2025",
            "--storage-dir",
            storage,
        ],
    )
    assert applied.exit_code == 0, applied.output
    assert json.loads(applied.output)["result"]["stored"] is True

    repeated = _RUNNER.invoke(
        app,
        [
            "--json",
            "data",
            "ledgers",
            "assets",
            "amortization",
            "apply",
            "--asset",
            "pc-2024",
            "--year",
            "2025",
            "--storage-dir",
            storage,
        ],
    )
    assert repeated.exit_code == 0, repeated.output
    assert json.loads(repeated.output)["result"]["stored"] is False


def test_data_ledgers_refuses_duplicate_assets(tmp_path) -> None:
    storage = str(tmp_path)
    args = [
        "data",
        "ledgers",
        "assets",
        "add",
        "pc",
        "--description",
        "work pc",
        "--asset-class",
        "electronica.equipos_tratamiento_informacion",
        "--taxable-base",
        "1000.00",
        "--acquisition-date",
        "2025-01-01",
        "--storage-dir",
        storage,
    ]
    assert _RUNNER.invoke(app, args).exit_code == 0
    duplicate = _RUNNER.invoke(app, args)

    assert duplicate.exit_code == 1
    assert "already exists" in duplicate.output


def test_data_ledgers_inventory_fifo_pmp_and_lifo_refusal(tmp_path) -> None:
    storage = str(tmp_path)
    create = _RUNNER.invoke(
        app,
        [
            "data",
            "ledgers",
            "inventory",
            "create",
            "retail",
            "--year",
            "2025",
            "--valuation-method",
            "fifo",
            "--opening-stock",
            "100.00",
            "--opening-quantity",
            "10",
            "--opening-unit-cost",
            "10.00",
            "--sku",
            "ssd",
            "--storage-dir",
            storage,
        ],
    )
    assert create.exit_code == 0, create.output

    purchase = _RUNNER.invoke(
        app,
        [
            "data",
            "ledgers",
            "inventory",
            "movement",
            "add",
            "--actividad",
            "retail",
            "--year",
            "2025",
            "--movement-id",
            "buy-1",
            "--date",
            "2025-02-01",
            "--kind",
            "purchase",
            "--sku",
            "ssd",
            "--quantity",
            "10",
            "--unit-cost",
            "20.00",
            "--vat-rate",
            "21.00",
            "--storage-dir",
            storage,
        ],
    )
    assert purchase.exit_code == 0, purchase.output

    sale = _RUNNER.invoke(
        app,
        [
            "data",
            "ledgers",
            "inventory",
            "movement",
            "add",
            "--actividad",
            "retail",
            "--year",
            "2025",
            "--movement-id",
            "sale-1",
            "--date",
            "2025-03-01",
            "--kind",
            "cogs",
            "--sku",
            "ssd",
            "--quantity",
            "12",
            "--storage-dir",
            storage,
        ],
    )
    assert sale.exit_code == 0, sale.output

    preview = _RUNNER.invoke(
        app,
        [
            "--json",
            "data",
            "ledgers",
            "inventory",
            "valuation",
            "preview",
            "--actividad",
            "retail",
            "--year",
            "2025",
            "--storage-dir",
            storage,
        ],
    )
    assert preview.exit_code == 0, preview.output
    payload = json.loads(preview.output)
    assert payload["command"] == "data ledgers inventory valuation preview"
    assert payload["result"]["cogs_value"] == "140.00"
    assert payload["result"]["closing_stock"] == "160.00"

    lifo = _RUNNER.invoke(
        app,
        [
            "data",
            "ledgers",
            "inventory",
            "create",
            "bad",
            "--year",
            "2025",
            "--valuation-method",
            "lifo",
            "--storage-dir",
            storage,
        ],
    )
    assert lifo.exit_code == 2
    assert "LIFO" in lifo.output


def test_data_ledgers_inventory_refuses_inconsistent_opening_layers(tmp_path) -> None:
    result = _RUNNER.invoke(
        app,
        [
            "data",
            "ledgers",
            "inventory",
            "create",
            "retail",
            "--year",
            "2025",
            "--valuation-method",
            "fifo",
            "--opening-stock",
            "100.00",
            "--opening-quantity",
            "10",
            "--opening-unit-cost",
            "20.00",
            "--storage-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "opening_stock" in result.output


def test_data_ledgers_anexo_d_preview_uses_ledgers(tmp_path) -> None:
    storage = str(tmp_path)
    asset = _RUNNER.invoke(
        app,
        [
            "data",
            "ledgers",
            "assets",
            "add",
            "pc",
            "--description",
            "work pc",
            "--asset-class",
            "electronica.equipos_tratamiento_informacion",
            "--taxable-base",
            "1000.00",
            "--acquisition-date",
            "2025-01-01",
            "--actividad",
            "retail",
            "--storage-dir",
            storage,
        ],
    )
    assert asset.exit_code == 0, asset.output
    inventory = _RUNNER.invoke(
        app,
        [
            "data",
            "ledgers",
            "inventory",
            "create",
            "retail",
            "--year",
            "2025",
            "--valuation-method",
            "fifo",
            "--opening-stock",
            "100.00",
            "--opening-quantity",
            "10",
            "--opening-unit-cost",
            "10.00",
            "--storage-dir",
            storage,
        ],
    )
    assert inventory.exit_code == 0, inventory.output

    preview = _RUNNER.invoke(
        app,
        [
            "--json",
            "data",
            "ledgers",
            "anexo-d",
            "preview",
            "--modelo",
            "100",
            "--year",
            "2025",
            "--actividad",
            "retail",
            "--storage-dir",
            storage,
        ],
    )

    assert preview.exit_code == 0, preview.output
    payload = json.loads(preview.output)
    assert payload["command"] == "data ledgers anexo-d preview"
    assert payload["result"]["casillas"]["0155"] == "0.00"
    assert payload["result"]["casillas"]["0173"] == "250.00"


def test_old_profile_ledger_namespace_is_not_public() -> None:
    result = _RUNNER.invoke(app, ["profile", "assets", "list"])

    assert result.exit_code != 0
