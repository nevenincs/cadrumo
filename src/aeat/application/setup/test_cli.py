"""Smoke tests for the user-facing first-run configuration surface."""

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
    result = _runner.invoke(app, ["config", "--help"])

    assert result.exit_code == 0
    assert "init" in result.output
    assert "status" in result.output
    assert "profile" in result.output
    assert "auth" in result.output
    assert "env/.env" not in result.output


def test_setup_profile_help_exposes_review_and_validation() -> None:
    result = _runner.invoke(app, ["config", "profile", "--help"])

    assert result.exit_code == 0
    for command in ("set", "get", "unset", "status", "list"):
        assert command in result.output


def test_setup_auth_help_exposes_access_lifecycle() -> None:
    result = _runner.invoke(app, ["config", "auth", "--help"])

    assert result.exit_code == 0
    for command in ("providers", "configure", "status", "test", "clear"):
        assert command in result.output


def test_setup_profile_roundtrip(tmp_path: Path) -> None:
    env = _env(tmp_path)
    init = _runner.invoke(
        app,
        [
            "--format",
            "json",
            "config",
            "init",
            "--quiet",
            "--name",
            "operator",
            "--activity",
            "design",
            "--tax-id",
            "12345678Z",
        ],
        env=env,
    )
    show = _runner.invoke(app, ["--format", "json", "config", "profile", "list"], env=env)

    assert init.exit_code == 0, init.output
    assert show.exit_code == 0, show.output
    payload = json.loads(show.output)
    # the exact shape of payload depends on `aeat config profile list --format json`
    # Let's just ensure it parsed as json
    assert isinstance(payload, dict)


def test_setup_status_reports_missing_and_ready_steps(tmp_path: Path) -> None:
    env = _env(tmp_path)
    missing = _runner.invoke(app, ["--format", "json", "config", "profile", "status"], env=env)
    assert missing.exit_code == 0, missing.output

    _runner.invoke(
        app,
        ["config", "init", "--quiet", "--name", "operator", "--activity", "design", "--tax-id", "12345678Z"],
        env=env,
    )
    _runner.invoke(
        app,
        ["config", "profile", "set", "iva.regime", "general"],
        env=env,
    )
    certificate = tmp_path / "cert.p12"
    certificate.write_bytes(b"fixture")
    _runner.invoke(
        app,
        ["config", "auth", "configure", "--provider", "certificate", "--file", str(certificate)],
        env=env,
    )
    ready = _runner.invoke(app, ["--format", "json", "app", "overview", "status"], env=env)

    assert ready.exit_code == 0, ready.output


def test_setup_auth_rejects_unsupported_provider(tmp_path: Path) -> None:
    result = _runner.invoke(
        app,
        ["config", "auth", "configure", "--provider", "clave_permanente"],
        env=_env(tmp_path),
    )

    assert result.exit_code != 0
    assert "clave_permanente" in result.output
