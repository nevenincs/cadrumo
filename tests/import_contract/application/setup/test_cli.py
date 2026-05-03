"""Smoke tests for the user-facing ``aeat setup`` surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.entrypoints.cli import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_runner = CliRunner()


def _env(tmp_path: Path) -> dict[str, str]:
    return {
        "AEAT_SECRET_STORE_BACKEND": "unsecured",
        "AEAT_ALLOW_UNENCRYPTED": "1",
        "AEAT_RUNS_DIR": str(tmp_path / "runs"),
        "AEAT_FINANCIAL_TXS_DIR": str(tmp_path / "txs"),
        "AEAT_INVOICES_DIR": str(tmp_path / "invoices"),
        "AEAT_DRAFTS_DIR": str(tmp_path / "drafts"),
    }


def test_setup_help_is_user_scaffold() -> None:
    result = _runner.invoke(app, ["setup", "--help"])

    assert result.exit_code == 0
    assert "init" in result.output
    assert "status" in result.output
    assert "profile" in result.output
    assert "auth" in result.output
    assert "env/.env" not in result.output


def test_setup_profile_help_exposes_review_and_validation() -> None:
    result = _runner.invoke(app, ["setup", "profile", "--help"])

    assert result.exit_code == 0
    for command in ("use", "set", "get", "unset", "show", "validate", "list", "keys"):
        assert command in result.output


def test_setup_auth_help_exposes_access_lifecycle() -> None:
    result = _runner.invoke(app, ["setup", "auth", "--help"])

    assert result.exit_code == 0
    for command in ("providers", "configure", "login", "status", "whoami", "logout"):
        assert command in result.output


def test_setup_profile_roundtrip(tmp_path: Path) -> None:
    env = _env(tmp_path)
    init = _runner.invoke(
        app,
        ["--format", "json", "setup", "init", "--name", "kent", "--activity", "design", "--tax-id", "12345678Z"],
        env=env,
    )
    show = _runner.invoke(app, ["--format", "json", "setup", "profile", "show"], env=env)
    validate = _runner.invoke(app, ["--format", "json", "setup", "profile", "validate"], env=env)

    assert init.exit_code == 0, init.output
    assert show.exit_code == 0, show.output
    assert validate.exit_code == 0, validate.output
    payload = json.loads(show.output)
    assert payload["active_profile"] == "kent"
    assert payload["values"]["activity"] == "design"
    assert payload["values"]["tax.id"] == "12345678Z"


def test_setup_status_reports_missing_and_ready_steps(tmp_path: Path) -> None:
    env = _env(tmp_path)
    missing = _runner.invoke(app, ["--format", "json", "setup", "status"], env=env)
    _runner.invoke(
        app,
        ["setup", "init", "--name", "kent", "--activity", "design", "--tax-id", "12345678Z"],
        env=env,
    )
    certificate = tmp_path / "cert.p12"
    certificate.write_bytes(b"fixture")
    _runner.invoke(
        app,
        ["setup", "auth", "configure", "--provider", "certificate", "--file", str(certificate)],
        env=env,
    )
    _runner.invoke(app, ["setup", "auth", "login"], env=env)
    ready = _runner.invoke(app, ["--format", "json", "setup", "status"], env=env)

    assert missing.exit_code == 0, missing.output
    assert json.loads(missing.output)["profile_ready"] is False
    assert ready.exit_code == 0, ready.output
    ready_payload = json.loads(ready.output)
    assert ready_payload["profile_ready"] is True
    assert ready_payload["login_ready"] is True
    assert ready_payload["next_action"] == "aeat app overview status"


def test_setup_auth_rejects_unavailable_provider(tmp_path: Path) -> None:
    result = _runner.invoke(
        app,
        ["setup", "auth", "configure", "--provider", "clave_permanente"],
        env=_env(tmp_path),
    )

    assert result.exit_code != 0
    assert "unavailable-provider" in result.output
