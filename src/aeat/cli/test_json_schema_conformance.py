"""Schema-conformance tests for registered ``--json`` command payloads."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ..deadlines import AutonomoProfile, IVARegime
from . import SCHEMA_REGISTRY
from . import app as root_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


@pytest.fixture(autouse=True)
def _cleanup_master_key_override() -> Iterator[None]:
    """Ensure each test starts with a clean ``override_master_key_provider`` state.

    The workflow tests in this file install an in-process master-key
    provider via ``_prepare_workflow_env``; this fixture clears it
    after each test so unrelated tests do not inherit a stale override.
    """
    yield
    from ..storage import override_master_key_provider, override_secret_store

    override_master_key_provider(None)
    override_secret_store(None)


_RUNNER = CliRunner()
_EXPECTED_REGISTERED_COMMANDS = {
    "auth list-providers",
    "auth login",
    "auth logout",
    "auth status",
    "auth whoami",
    "browser health",
    "data ledgers assets add",
    "data ledgers assets amortization apply",
    "data ledgers assets amortization preview",
    "data ledgers assets classes list",
    "data ledgers assets list",
    "data ledgers assets show",
    "data ledgers anexo-d preview",
    "data ledgers inventory create",
    "data ledgers inventory list",
    "data ledgers inventory movement add",
    "data ledgers inventory valuation preview",
    "financial aggregate",
    "filing reconcile",
    "modelos applicable-to",
    "modelos list",
    "modelos show",
    "modelos year-plan",
    "portals for-modelo",
    "portals list",
    "portals show",
    "profile show",
    "rental anexo-c compute",
    "rental anexo-c verify",
    "rental contract add",
    "rental contract list",
    "rental contract show",
    "rental expense add",
    "rental expense list",
    "rental finca add",
    "rental finca list",
    "rental finca show",
    "rental income list",
    "rental income record",
    "sede list-expedientes",
    "sede notifications",
    "submission check-nif",
    "submission diff",
    "submission schemas",
    "submission verify",
    "workflow list",
    "workflow next",
    "workflow run",
    "workflow show",
}


def _prepare_workflow_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    from ..storage import (
        EncryptedBlobStore,
        Envelope,
        EphemeralMasterKeyProvider,
        SecretStore,
        SensitivityClass,
        override_master_key_provider,
        override_secret_store,
        save_encrypted_envelope,
    )
    from ..storage._encrypted_columns import _resolve_master_key_provider

    # Install an in-process master-key + secret store for the duration
    # of this test so the workflow CLI's
    # ``load_default_filing_profile`` round-trips through the substrate.
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs-secret",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_secret_store(secret_store)

    profile = AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    profile_path = tmp_path / "profile.json"
    envelope = Envelope[AutonomoProfile](
        schema_version=1,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.IDENTITY,
        payload=profile,
    )
    save_encrypted_envelope(
        envelope,
        profile_path,
        master_key_provider=_resolve_master_key_provider(),
        hkdf_context=b"aeat.setup.profile.v1",
    )

    inputs_path = tmp_path / "inputs.json"
    inputs_path.write_text(json.dumps({"01": 12500, "02": 3500, "05": 400, "06": 0}), encoding="utf-8")

    monkeypatch.setenv("AEAT_DEFAULT_PROFILE_PATH", str(profile_path))
    monkeypatch.setenv("AEAT_WORKFLOW_DRAFT_INPUTS_PATH", str(inputs_path))
    monkeypatch.setenv("AEAT_WORKFLOW_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(tmp_path / "submissions"))
    monkeypatch.setenv("AEAT_SUBMISSION_BROWSER_TRACE_DIR", str(tmp_path / "traces"))


def _unwrap_result(output: str, *, command_path: str) -> str:
    payload = json.loads(output)
    assert payload["schema_version"] == "1"
    assert payload["command"] == command_path
    return json.dumps(payload["result"])


def test_schema_registry_contains_current_json_contract_bindings() -> None:
    """The registry should enumerate the current JSON-contract command set."""

    assert set(SCHEMA_REGISTRY) == _EXPECTED_REGISTERED_COMMANDS


@pytest.mark.parametrize(
    ("command_path", "invoke"),
    [
        (
            "auth list-providers",
            lambda tmp_path, monkeypatch: _RUNNER.invoke(root_app, ["auth", "list-providers", "--json"]),
        ),
        (
            "auth status",
            lambda tmp_path, monkeypatch: _RUNNER.invoke(root_app, ["auth", "status", "--json"]),
        ),
        (
            "modelos list",
            lambda tmp_path, monkeypatch: _RUNNER.invoke(root_app, ["modelos", "list", "--json"]),
        ),
        (
            "modelos show",
            lambda tmp_path, monkeypatch: _RUNNER.invoke(root_app, ["modelos", "show", "303", "--json"]),
        ),
        (
            "modelos applicable-to",
            lambda tmp_path, monkeypatch: _RUNNER.invoke(
                root_app, ["modelos", "applicable-to", "autonomo_ed_solo", "--json"]
            ),
        ),
        (
            "modelos year-plan",
            lambda tmp_path, monkeypatch: _RUNNER.invoke(
                root_app,
                ["modelos", "year-plan", "2026", "--tax-id", "X1234567L", "--json"],
            ),
        ),
        (
            "portals list",
            lambda tmp_path, monkeypatch: _RUNNER.invoke(root_app, ["portals", "list", "--json"]),
        ),
        (
            "portals show",
            lambda tmp_path, monkeypatch: _RUNNER.invoke(
                root_app, ["portals", "show", "portal_clave_idp_root", "--json"]
            ),
        ),
        (
            "portals for-modelo",
            lambda tmp_path, monkeypatch: _RUNNER.invoke(root_app, ["portals", "for-modelo", "303", "--json"]),
        ),
        (
            "profile show",
            lambda tmp_path, monkeypatch: (
                monkeypatch.setenv("AEAT_TAX_RESIDENCE_PROFILE_PATH", str(tmp_path / "tax-residence.json")),
                _RUNNER.invoke(root_app, ["profile", "show", "--json"]),
            )[1],
        ),
        (
            "data ledgers assets add",
            lambda tmp_path, monkeypatch: _invoke_data_ledgers_assets_add(tmp_path),
        ),
        (
            "data ledgers assets list",
            lambda tmp_path, monkeypatch: _invoke_data_ledgers_assets_list(tmp_path),
        ),
        (
            "data ledgers assets show",
            lambda tmp_path, monkeypatch: _invoke_data_ledgers_assets_show(tmp_path),
        ),
        (
            "data ledgers assets classes list",
            lambda tmp_path, monkeypatch: _RUNNER.invoke(
                root_app, ["--json", "data", "ledgers", "assets", "classes", "list"]
            ),
        ),
        (
            "data ledgers assets amortization preview",
            lambda tmp_path, monkeypatch: _invoke_data_ledgers_assets_amortization(tmp_path, "preview"),
        ),
        (
            "data ledgers assets amortization apply",
            lambda tmp_path, monkeypatch: _invoke_data_ledgers_assets_amortization(tmp_path, "apply"),
        ),
        (
            "data ledgers inventory create",
            lambda tmp_path, monkeypatch: _invoke_data_ledgers_inventory_create(tmp_path),
        ),
        (
            "data ledgers inventory list",
            lambda tmp_path, monkeypatch: _invoke_data_ledgers_inventory_list(tmp_path),
        ),
        (
            "data ledgers inventory movement add",
            lambda tmp_path, monkeypatch: _invoke_data_ledgers_inventory_movement_add(tmp_path),
        ),
        (
            "data ledgers inventory valuation preview",
            lambda tmp_path, monkeypatch: _invoke_data_ledgers_inventory_valuation_preview(tmp_path),
        ),
        (
            "data ledgers anexo-d preview",
            lambda tmp_path, monkeypatch: _invoke_data_ledgers_anexo_d_preview(tmp_path),
        ),
        (
            "submission check-nif",
            lambda tmp_path, monkeypatch: _RUNNER.invoke(root_app, ["submission", "check-nif", "X1234567L", "--json"]),
        ),
        (
            "submission schemas",
            lambda tmp_path, monkeypatch: _RUNNER.invoke(root_app, ["submission", "schemas", "--json"]),
        ),
        (
            "workflow next",
            lambda tmp_path, monkeypatch: (
                _prepare_workflow_env(tmp_path, monkeypatch),
                _RUNNER.invoke(root_app, ["workflow", "next", "--json", "--no-sync"]),
            )[1],
        ),
        (
            "workflow run",
            lambda tmp_path, monkeypatch: (
                _prepare_workflow_env(tmp_path, monkeypatch),
                _RUNNER.invoke(
                    root_app,
                    ["workflow", "run", "--modelo", "130", "--period", "2026Q2", "--json", "--no-sync"],
                ),
            )[1],
        ),
        (
            "workflow show",
            lambda tmp_path, monkeypatch: _invoke_workflow_show(tmp_path, monkeypatch),
        ),
        (
            "workflow list",
            lambda tmp_path, monkeypatch: _invoke_workflow_list(tmp_path, monkeypatch),
        ),
    ],
)
def test_registered_schema_validates_real_cli_output(
    command_path: str,
    invoke,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each bound schema should validate the real CLI JSON bytes it owns."""

    result = invoke(tmp_path, monkeypatch)
    assert result.exit_code == 0, result.output
    SCHEMA_REGISTRY[command_path].model_validate_json(_unwrap_result(result.output, command_path=command_path))


def _invoke_workflow_show(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _prepare_workflow_env(tmp_path, monkeypatch)
    seed = _RUNNER.invoke(root_app, ["workflow", "next", "--json", "--no-sync"])
    assert seed.exit_code == 0, seed.output
    run_id = json.loads(seed.output)["result"]["run_id"]
    return _RUNNER.invoke(root_app, ["workflow", "show", run_id, "--json"])


def _invoke_workflow_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _prepare_workflow_env(tmp_path, monkeypatch)
    seed = _RUNNER.invoke(root_app, ["workflow", "next", "--json", "--no-sync"])
    assert seed.exit_code == 0, seed.output
    return _RUNNER.invoke(root_app, ["workflow", "list", "--json"])


def _prepare_ledgers_env() -> None:
    from ..storage import EphemeralMasterKeyProvider, override_master_key_provider

    override_master_key_provider(EphemeralMasterKeyProvider())


def _seed_data_ledger_asset(tmp_path: Path) -> None:
    _prepare_ledgers_env()
    result = _RUNNER.invoke(
        root_app,
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
            "--storage-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output


def _invoke_data_ledgers_assets_add(tmp_path: Path):
    _prepare_ledgers_env()
    return _RUNNER.invoke(
        root_app,
        [
            "--json",
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
            str(tmp_path),
        ],
    )


def _invoke_data_ledgers_assets_list(tmp_path: Path):
    _seed_data_ledger_asset(tmp_path)
    return _RUNNER.invoke(root_app, ["--json", "data", "ledgers", "assets", "list", "--storage-dir", str(tmp_path)])


def _invoke_data_ledgers_assets_show(tmp_path: Path):
    _seed_data_ledger_asset(tmp_path)
    return _RUNNER.invoke(
        root_app,
        ["--json", "data", "ledgers", "assets", "show", "pc", "--storage-dir", str(tmp_path)],
    )


def _invoke_data_ledgers_assets_amortization(tmp_path: Path, command: str):
    _seed_data_ledger_asset(tmp_path)
    return _RUNNER.invoke(
        root_app,
        [
            "--json",
            "data",
            "ledgers",
            "assets",
            "amortization",
            command,
            "--asset",
            "pc",
            "--year",
            "2025",
            "--storage-dir",
            str(tmp_path),
        ],
    )


def _seed_data_ledger_inventory(tmp_path: Path) -> None:
    _prepare_ledgers_env()
    result = _RUNNER.invoke(
        root_app,
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
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output


def _invoke_data_ledgers_inventory_create(tmp_path: Path):
    _prepare_ledgers_env()
    return _RUNNER.invoke(
        root_app,
        [
            "--json",
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
            str(tmp_path),
        ],
    )


def _invoke_data_ledgers_inventory_list(tmp_path: Path):
    _seed_data_ledger_inventory(tmp_path)
    return _RUNNER.invoke(root_app, ["--json", "data", "ledgers", "inventory", "list", "--storage-dir", str(tmp_path)])


def _invoke_data_ledgers_inventory_movement_add(tmp_path: Path):
    _seed_data_ledger_inventory(tmp_path)
    return _RUNNER.invoke(
        root_app,
        [
            "--json",
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
            "2025-01-02",
            "--kind",
            "purchase",
            "--quantity",
            "2",
            "--unit-cost",
            "10",
            "--storage-dir",
            str(tmp_path),
        ],
    )


def _invoke_data_ledgers_inventory_valuation_preview(tmp_path: Path):
    movement = _invoke_data_ledgers_inventory_movement_add(tmp_path)
    assert movement.exit_code == 0, movement.output
    return _RUNNER.invoke(
        root_app,
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
            str(tmp_path),
        ],
    )


def _invoke_data_ledgers_anexo_d_preview(tmp_path: Path):
    _prepare_ledgers_env()
    asset = _RUNNER.invoke(
        root_app,
        [
            "--json",
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
            str(tmp_path),
        ],
    )
    assert asset.exit_code == 0, asset.output
    inventory = _RUNNER.invoke(
        root_app,
        [
            "--json",
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
            str(tmp_path),
        ],
    )
    assert inventory.exit_code == 0, inventory.output
    return _RUNNER.invoke(
        root_app,
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
            str(tmp_path),
        ],
    )
