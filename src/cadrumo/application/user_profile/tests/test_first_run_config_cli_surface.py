"""Smoke tests for the user-facing first-run configuration surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....core.config import SecretStoreBackend
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import dev_test_database_password, isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile
from .. import register_profile_with_credentials

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _env(tmp_path: Path) -> dict[str, str]:
    return {
        "CADRUMO_SECRET_STORE_BACKEND": SecretStoreBackend.FILE.value,
        "CADRUMO_SECRET_PASSPHRASE": dev_test_database_password(),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
        "CADRUMO_RUNS_DIR": str(tmp_path / "probe-runs"),
        "CADRUMO_FINANCIAL_TXS_DIR": str(tmp_path / "txs"),
        "CADRUMO_INVOICES_DIR": str(tmp_path / "invoices"),
        "CADRUMO_DRAFTS_DIR": str(tmp_path / "probe-drafts"),
    }


def test_setup_help_is_user_scaffold(tmp_path: Path) -> None:
    result = invoke_cached_cli(["config", "--help"], env=_env(tmp_path))

    assert result.exit_code == 0, result.output
    assert "profile create" in result.output
    assert "profile status" in result.output
    assert "profile" in result.output
    assert "auth" in result.output
    assert ("config " + "init") not in result.output
    assert "env/.env" not in result.output


def test_setup_profile_help_exposes_review_and_validation(tmp_path: Path) -> None:
    result = invoke_cached_cli(["config", "profile", "--help"], env=_env(tmp_path))

    assert result.exit_code == 0, result.output
    for command in ("create", "edit", "show", "delete", "status", "list"):
        assert command in result.output
    assert "profile set" not in result.output
    assert "profile get" not in result.output


def test_setup_auth_help_exposes_access_lifecycle(tmp_path: Path) -> None:
    result = invoke_cached_cli(["config", "auth", "--help"], env=_env(tmp_path))

    assert result.exit_code == 0, result.output
    for command in ("providers", "configure", "status", "test", "logout", "reset"):
        assert command in result.output


def test_setup_profile_roundtrip(tmp_path: Path) -> None:
    """A profile created at the credential door is visible to ``profile list``.

    Creation is the credential door's alone: the wizard's ``create`` mode
    refuses outright and tells the operator to register first, so a scripted
    ``config profile create`` no longer makes a profile and asserting it
    succeeded would assert a surface that is gone. What survives from the
    original roundtrip is the part that still has a subject -- a profile that
    exists is reported by the listing verb, under the label it was given.
    """
    label = "operator"
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=label, passphrase=dev_test_database_password())

        show = invoke_cached_cli(["--format", "json", "config", "profile", "list"])

    assert show.exit_code == 0, show.output
    payload = json.loads(show.output)
    assert isinstance(payload, dict)
    assert label in show.output


def test_setup_status_reports_missing_and_ready_steps(tmp_path: Path) -> None:
    env = _env(tmp_path)
    missing = invoke_cached_cli(["--format", "json", "config", "profile", "status"], env=env)
    assert missing.exit_code == 0, missing.output

    invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--name",
            "operator",
            "--activity",
            "design",
            "--tax-id",
            "12345678Z",
            "--entity-type",
            "natural_person",
            "--surnames",
            "Example",
            "--iva-regime",
            "GENERAL",
        ],
        env=env,
    )
    certificate = tmp_path / "cert.p12"
    certificate.write_bytes(b"fixture")
    invoke_cached_cli(
        ["config", "auth", "configure", "--provider", "certificate", "--file", str(certificate)],
        env=env,
    )
    ready = invoke_cached_cli(["--format", "json", "app", "overview", "status"], env=env)

    assert ready.exit_code == 0, ready.output


def test_setup_auth_rejects_unsupported_provider(tmp_path: Path) -> None:
    env = _env(tmp_path)
    register_cli_profile(
        label="operator",
        facts={
            "activities.description": "design",
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Example",
        },
    )

    result = invoke_cached_cli(
        ["config", "auth", "configure", "--provider", "clave_pin"],
        env=env,
    )

    assert result.exit_code != 0
    assert "clave_pin" in result.output
