"""End-to-end verification for the accepted apex CLI roots."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.application.operator_surface import get_operator_surface_contract
from aeat.application.wizard._catalogue import SETUP_FLOW

from . import _config, app, app_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_cli_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    dispose_engine()
    for name in (
        "AEAT_AUTH_PROVIDER",
        "AEAT_CERTIFICATE_PATH",
        "AEAT_CERTIFICATE_PASSWORD_SECRET",
        "AEAT_CLAVE_MOVIL_DNI_NIE",
        "AEAT_CLAVE_MOVIL_DNI_FECHA",
        "AEAT_CLAVE_MOVIL_NIE_SOPORTE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path / "tokens"))
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    try:
        yield tmp_path
    finally:
        dispose_engine()


def _invoke(args: list[str]):
    return _RUNNER.invoke(app, args)


def _json(result) -> dict:
    return json.loads(result.output)


def _registered_command_names(typer_app) -> set[str]:
    return {command.name for command in typer_app.registered_commands}


def _registered_group_names(typer_app) -> set[str]:
    return {group.name for group in typer_app.registered_groups}


def test_backend_declared_command_families_are_mounted_in_cli() -> None:
    """The backend contract must not drift into a detached interface."""

    mounted = {
        "config": _registered_command_names(_config.app) | _registered_group_names(_config.app),
        "app": _registered_command_names(app_app) | _registered_group_names(app_app),
    }

    for family in get_operator_surface_contract().command_families:
        assert family.child in mounted[family.root.value]

    config_children = mounted["config"]
    app_children = mounted["app"]
    assert {"init", "profile", "auth", "doctor"}.issubset(config_children)
    assert {"overview", "ledger", "modelo", "registry", "review"}.issubset(app_children)


def test_config_init_mounts_existing_setup_wizard_flow() -> None:
    """First-run configuration is the wizard flow, not a parallel interface."""

    init_command = next(command for command in _config.app.registered_commands if command.name == "init")
    callback = init_command.callback
    assert callback is not None
    wrapped = getattr(callback, "__wrapped__", callback)
    assert getattr(wrapped, "__wizard_flow__", None) is SETUP_FLOW


def test_rejected_aliases_do_not_reach_apex_workflow_services() -> None:
    for command in (
        ["setup", "--help"],
        ["auth", "--help"],
        ["financial", "--help"],
        ["filing", "--help"],
        ["app", "invoice", "--help"],
        ["app", "declaration", "--help"],
        ["app", "archive", "--help"],
        ["app", "topic", "--help"],
        ["config", "set", "--help"],
        ["config", "status", "--help"],
    ):
        result = _invoke(command)
        assert result.exit_code != 0, command


def test_config_app_real_workflow_round_trip(_isolated_cli_backend: Path) -> None:
    profile = _invoke(
        [
            "--format",
            "json",
            "config",
            "init",
            "--quiet",
            "--accept-defaults",
            "--profile",
            "operator",
            "--tax-id",
            "12345678Z",
            "--name",
            "Operator",
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
        ]
    )
    assert profile.exit_code == 0, profile.output

    status = _invoke(["--format", "json", "config", "profile", "status"])
    assert status.exit_code == 0, status.output
    status_payload = _json(status)
    assert status_payload["active_profile"] == "operator"
    assert status_payload["tax_id_present"] is True
    assert status_payload["activity_present"] is True
    assert status_payload["iva_regime"] == "GENERAL"

    certificate = _isolated_cli_backend / "certificate.p12"
    certificate.write_bytes(b"not-a-real-certificate")
    configured = _invoke(
        ["--format", "json", "config", "auth", "configure", "--provider", "certificate", "--file", str(certificate)]
    )
    auth_status = _invoke(["--format", "json", "config", "auth", "status", "--provider", "certificate"])
    auth_test = _invoke(["--format", "json", "config", "auth", "test", "--provider", "certificate"])

    assert configured.exit_code == 0, configured.output
    assert _json(configured)["provider"] == "certificate"
    assert auth_status.exit_code == 0, auth_status.output
    assert _json(auth_status)["configured"] is True
    assert auth_test.exit_code == 0, auth_test.output
    assert _json(auth_test)["provider"] == "certificate"

    statement = _isolated_cli_backend / "bank.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Payment F-001,121.00,EUR,bank-001\n",
        encoding="utf-8",
    )
    imported = _invoke(["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv"])
    overview = _invoke(["--format", "json", "app", "overview", "status"])
    review = _invoke(["--format", "json", "app", "review", "queue", "--source-kind", "ledger_transaction"])

    assert imported.exit_code == 0, imported.output
    assert _json(imported)["imported"] == 1
    assert overview.exit_code == 0, overview.output
    assert _json(overview)["transactions"] == 1
    assert review.exit_code == 0, review.output
    review_payload = _json(review)
    assert len(review_payload["rows"]) == 1
    row = review_payload["rows"][0]
    assert row["source_kind"] == "ledger_transaction"
    assert row["affected_object_id"]
    assert row["bucket_id"] == "operator"
    assert row["period"] == "2026-04"
